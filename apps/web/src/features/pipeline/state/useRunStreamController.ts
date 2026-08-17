import { useCallback, useRef } from 'react';
import type { RunControlState, RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
import { runPayloadAuthority } from '../lib/runPayloadRef';
import { createRunStream, getArtifactRecord, getChapterVersion, streamExistingRun } from '../services/runApi';
import { consumeRunEventStream } from '../services/runStream';
import { isRunAbortError, useRunSession } from './useRunSession';

type RunStreamRequest = {
  inputs: RunInputs;
  kind: 'existing' | 'new';
  runId: string;
  replayFromStart?: boolean;
  workflow: WorkflowDefinition;
};

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_DELAYS_MS = [0, 250, 750] as const;

export function useRunStreamController(onEvent: (event: RunEvent) => void) {
  const onEventRef = useRef(onEvent);
  const sequenceByRunRef = useRef(new Map<string, number>());
  onEventRef.current = onEvent;
  const session = useRunSession();

  const consume = useCallback(async ({
    inputs,
    kind,
    replayFromStart = false,
    runId,
    workflow,
  }: RunStreamRequest): Promise<RunControlState | null> => {
    const stream = session.begin();
    try {
      if (kind === 'existing' && replayFromStart) sequenceByRunRef.current.delete(runId);
      let response = kind === 'new'
        ? await createRunStream(workflow, inputs, stream.signal, runId)
        : null;
      let reconnectAttempts = 0;

      while (session.isCurrent(stream.id) && !stream.signal.aborted) {
        try {
          response ??= await streamExistingRun(
            runId,
            stream.signal,
            sequenceByRunRef.current.get(runId) ?? 0,
          );
          const terminal = await consumeRunEventStream({
            onEvents: async (batch) => {
              const fresh = batch.filter((event) => {
                const previous = sequenceByRunRef.current.get(event.run_id) ?? 0;
                return event.sequence > previous;
              });
              const resolved = await resolveBatchPayloadRefs(fresh, stream.signal);
              if (!session.isCurrent(stream.id)) return;
              // Dispatched without awaiting between events so React folds one chunk
              // into a single render instead of animating the backlog into place.
              for (const event of resolved) {
                const previous = sequenceByRunRef.current.get(event.run_id) ?? 0;
                if (event.sequence <= previous) continue;
                onEventRef.current(event);
                sequenceByRunRef.current.set(event.run_id, event.sequence);
              }
            },
            response,
            signal: stream.signal,
          });
          if (terminal) return session.release(stream.id) ? terminal : null;
        } catch (error) {
          if (isRunAbortError(error) || !isTransientStreamError(error)) throw error;
        }

        if (!session.isCurrent(stream.id) || stream.signal.aborted) return null;
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          throw new Error('Run event stream disconnected before a terminal event');
        }
        await waitForReconnect(RECONNECT_DELAYS_MS[reconnectAttempts], stream.signal);
        reconnectAttempts += 1;
        response = null;
      }
      return null;
    } catch (error) {
      session.release(stream.id);
      throw error;
    }
  }, [session]);

  return {
    consume,
    invalidate: session.invalidate,
    isInFlight: session.isInFlight,
  };
}

function isTransientStreamError(error: unknown) {
  return error instanceof TypeError
    || (error instanceof DOMException && error.name === 'NetworkError');
}

function waitForReconnect(delayMs: number, signal: AbortSignal) {
  if (signal.aborted) {
    return Promise.reject(new DOMException('Run stream aborted', 'AbortError'));
  }
  if (!delayMs) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      signal.removeEventListener('abort', abort);
      resolve();
    }, delayMs);
    const abort = () => {
      window.clearTimeout(timer);
      reject(new DOMException('Run stream aborted', 'AbortError'));
    };
    signal.addEventListener('abort', abort, { once: true });
  });
}

/** Payload refs fetch one record each; a replayed run has hundreds, so they go out
 *  in bounded parallel waves instead of one blocking round-trip per event. */
const PAYLOAD_FETCH_CONCURRENCY = 8;

async function resolveBatchPayloadRefs(events: RunEvent[], signal: AbortSignal): Promise<RunEvent[]> {
  const resolved: RunEvent[] = new Array(events.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.min(PAYLOAD_FETCH_CONCURRENCY, events.length) }, async () => {
    while (cursor < events.length) {
      const index = cursor;
      cursor += 1;
      resolved[index] = await resolvePayloadRef(events[index], signal);
    }
  });
  await Promise.all(workers);
  return resolved;
}

async function resolvePayloadRef(event: RunEvent, signal: AbortSignal): Promise<RunEvent> {
  const authority = runPayloadAuthority(event);
  if (authority === 'chapter-version') {
    const record = await getChapterVersion(event.run_id, event.chapter_id, event.payload_ref, signal);
    return { ...event, payload: record.artifact };
  }
  if (authority === 'artifact-record') {
    const record = await getArtifactRecord(event.run_id, event.payload_ref, signal);
    return { ...event, payload: record.payload };
  }
  return event;
}

export type RunStreamController = ReturnType<typeof useRunStreamController>;
