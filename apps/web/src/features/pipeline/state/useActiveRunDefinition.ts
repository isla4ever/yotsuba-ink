import { useEffect, useState } from 'react';
import type { GraphRunDefinition } from '../contracts';
import { getRun } from '../services/runApi';

type ActiveRunDefinitionState = {
  definition: GraphRunDefinition | null;
  error: boolean;
  loading: boolean;
};

const idle: ActiveRunDefinitionState = { definition: null, error: false, loading: false };

export function useActiveRunDefinition(runId: string): ActiveRunDefinitionState {
  const [state, setState] = useState<{ runId: string; value: ActiveRunDefinitionState }>({ runId: '', value: idle });

  useEffect(() => {
    if (!runId) {
      setState({ runId: '', value: idle });
      return undefined;
    }
    const controller = new AbortController();
    setState({ runId, value: { definition: null, error: false, loading: true } });
    void getRun(runId, controller.signal)
      .then((envelope) => setState({ runId, value: { definition: envelope.definition, error: false, loading: false } }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setState({ runId, value: { definition: null, error: true, loading: false } });
      });
    return () => controller.abort();
  }, [runId]);

  return state.runId === runId ? state.value : { definition: null, error: false, loading: Boolean(runId) };
}
