import { useCallback, useEffect, useState } from 'react';
import type { RunEvent, RunHistoryItem, WorkflowDefinition } from '../contracts';
import { listRunHistory } from '../services/runHistoryApi';

export function useRunHistory() {
  const [items, setItems] = useState<RunHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const response = await listRunHistory({ limit: 24 }, signal);
      setItems(response.items);
      setError('');
    } catch (reason) {
      if (isAbortError(reason)) return;
      setError(reason instanceof Error ? reason.message : '创作历史暂时不可用');
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const record = useCallback((_events: RunEvent[], _workflow: WorkflowDefinition) => {
    void refresh();
  }, [refresh]);

  return { error, items, loading, record, refresh };
}

export type RunHistoryController = ReturnType<typeof useRunHistory>;

function isAbortError(error: unknown) {
  return (error instanceof DOMException && error.name === 'AbortError')
    || (error instanceof Error && error.name === 'AbortError');
}
