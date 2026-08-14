import { useCallback, useRef } from 'react';
import type { RunControlState, RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
import { runPayloadAuthority } from '../lib/runPayloadRef';
import { createRunStream, getArtifactRecord, getChapterVersion, streamExistingRun } from '../services/runApi';
import { consumeRunEventStream } from '../services/runStream';
import { useRunSession } from './useRunSession';

type RunStreamRequest = {
  inputs: RunInputs;
  kind: 'existing' | 'new';
  runId: string;
  workflow: WorkflowDefinition;
};

export function useRunStreamController(onEvent: (event: RunEvent) => void) {
  const onEventRef = useRef(onEvent);
  const sequenceByRunRef = useRef(new Map<string, number>());
  onEventRef.current = onEvent;
  const session = useRunSession();

  const consume = useCallback(async ({
    inputs,
    kind,
    runId,
    workflow,
  }: RunStreamRequest): Promise<RunControlState | null> => {
    const stream = session.begin();
    try {
      const response = kind === 'new'
        ? await createRunStream(workflow, inputs, stream.signal, runId)
        : await streamExistingRun(runId, stream.signal, sequenceByRunRef.current.get(runId) ?? 0);
      const terminal = await consumeRunEventStream({
        onEvents: async (batch) => {
          const fresh = batch.filter((event) => {
            const sequence = event.sequence ?? 0;
            const previous = sequenceByRunRef.current.get(event.run_id) ?? 0;
            if (sequence && sequence <= previous) return false;
            if (sequence) sequenceByRunRef.current.set(event.run_id, sequence);
            return true;
          });
          const resolved = await resolveBatchPayloadRefs(fresh, stream.signal);
          if (!session.isCurrent(stream.id)) return;
          // Dispatched without awaiting between events so React folds one chunk
          // into a single render instead of animating the backlog into place.
          for (const event of resolved) onEventRef.current(event);
        },
        response,
        signal: stream.signal,
      });
      return session.release(stream.id) ? terminal : null;
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
