import { useCallback, useRef } from 'react';
import type { RunControlState, RunEvent, RunInputs } from '../contracts';
import { createRunStream, streamExistingRun } from '../services/runApi';
import { consumeRunEventStream } from '../services/runStream';
import { useRunSession } from './useRunSession';

type RunStreamRequest = {
  inputs: RunInputs;
  kind: 'existing' | 'new';
  runId: string;
  workflowId: string;
};

export function useRunStreamController(onEvent: (event: RunEvent) => void) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const session = useRunSession();

  const consume = useCallback(async ({
    inputs,
    kind,
    runId,
    workflowId,
  }: RunStreamRequest): Promise<RunControlState | null> => {
    const stream = session.begin();
    try {
      const response = kind === 'new'
        ? await createRunStream(workflowId, inputs, stream.signal, runId)
        : await streamExistingRun(runId, stream.signal);
      const terminal = await consumeRunEventStream({
        onEvent: (event) => {
          if (session.isCurrent(stream.id)) onEventRef.current(event);
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

export type RunStreamController = ReturnType<typeof useRunStreamController>;
