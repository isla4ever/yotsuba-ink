import { useCallback, useRef } from 'react';
import type { RunControlState, RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
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
        onEvent: async (event) => {
          const resolved = await resolvePayloadRef(event, stream.signal);
          const sequence = resolved.sequence ?? 0;
          const previous = sequenceByRunRef.current.get(resolved.run_id) ?? 0;
          if (sequence && sequence <= previous) return;
          if (sequence) sequenceByRunRef.current.set(resolved.run_id, sequence);
          if (session.isCurrent(stream.id)) onEventRef.current(resolved);
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

async function resolvePayloadRef(event: RunEvent, signal: AbortSignal): Promise<RunEvent> {
  if (!event.payload_ref || event.payload) return event;
  if (event.type === 'artifact.candidate_ready' || (event.type === 'artifact.committed' && event.stage_id !== 'text')) {
    const record = await getArtifactRecord(event.run_id, event.payload_ref, signal);
    return { ...event, payload: record.payload };
  }
  if (event.stage_id === 'text' && event.chapter_id && ['artifact.candidate_ready', 'artifact.committed'].includes(event.type)) {
    const record = await getChapterVersion(event.run_id, event.chapter_id, event.payload_ref, signal);
    return { ...event, payload: record.artifact };
  }
  return event;
}

export type RunStreamController = ReturnType<typeof useRunStreamController>;
