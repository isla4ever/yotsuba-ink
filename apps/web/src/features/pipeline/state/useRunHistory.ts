import { useCallback, useEffect, useState } from 'react';
import type { RunEvent, RunHistoryItem, WorkflowDefinition } from '../contracts';
import { listRunHistory } from '../services/runHistoryApi';
import {
  historyItemFromEvents,
  loadLocalRunHistory,
  saveLocalRunHistory,
} from './storage';

export function useRunHistory() {
  const [items, setItems] = useState<RunHistoryItem[]>(() => loadLocalRunHistory());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const response = await listRunHistory({ limit: 24 }, signal);
      setItems(response.items);
      saveLocalRunHistory(response.items);
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

  const record = useCallback((events: RunEvent[], workflow: WorkflowDefinition) => {
    const item = historyItemFromEvents(events, workflow);
    if (!item) return;
    setItems((current) => {
      const next = mergeRunHistory(current, item);
      saveLocalRunHistory(next);
      return next;
    });
    void refresh();
  }, [refresh]);

  return { error, items, loading, record, refresh };
}

export function mergeRunHistory(
  current: RunHistoryItem[],
  item: RunHistoryItem,
) {
  return [item, ...current.filter((entry) => entry.run_id !== item.run_id)].slice(0, 24);
}

export type RunHistoryController = ReturnType<typeof useRunHistory>;

function isAbortError(error: unknown) {
  return (error instanceof DOMException && error.name === 'AbortError')
    || (error instanceof Error && error.name === 'AbortError');
}
