import { useCallback, useEffect, useRef, useState } from 'react';
import type { ExportReceipt } from '../contracts';
import { listRunExports } from '../services/runHistoryApi';

export type RunExportHistoryState = {
  error: string;
  items: ExportReceipt[];
  loading: boolean;
  refresh: () => Promise<void>;
};

export function useRunExportHistory(
  runId: string,
  expectedCount: number,
): RunExportHistoryState {
  const requestSequence = useRef(0);
  const [state, setState] = useState({
    error: '',
    items: [] as ExportReceipt[],
    loading: false,
    runId: '',
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!runId) return;
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    setState((current) => ({
      error: '',
      items: current.runId === runId ? current.items : [],
      loading: true,
      runId,
    }));
    try {
      const items = await listRunExports(runId, signal);
      if (signal?.aborted || requestSequence.current !== sequence) return;
      setState({ error: '', items, loading: false, runId });
    } catch (error) {
      if (isAbortError(error) || requestSequence.current !== sequence) return;
      setState((current) => ({
        ...current,
        error: error instanceof Error ? error.message : '交付版本暂时不可用',
        loading: false,
        runId,
      }));
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      requestSequence.current += 1;
      setState({ error: '', items: [], loading: false, runId: '' });
      return;
    }
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [expectedCount, load, runId]);

  const refresh = useCallback(async () => {
    await load();
  }, [load]);

  return {
    error: state.error,
    items: state.runId === runId ? state.items : [],
    loading: state.runId === runId && state.loading,
    refresh,
  };
}

function isAbortError(error: unknown) {
  return (error instanceof DOMException && error.name === 'AbortError')
    || (error instanceof Error && error.name === 'AbortError');
}
