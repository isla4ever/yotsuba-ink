import { useCallback, useEffect, useState } from 'react';
import type { ProviderReadinessReport } from '../contracts';
import { getProviderReadiness } from '../services/providerApi';

export type ProviderReadinessState = {
  error: string;
  report?: ProviderReadinessReport;
  status: 'idle' | 'loading' | 'ready' | 'failed';
};

const initialState: ProviderReadinessState = { error: '', status: 'idle' };

export function useProviderReadiness(workflowId: string, enabled = true) {
  const [state, setState] = useState<ProviderReadinessState>(initialState);
  const [revision, setRevision] = useState(0);

  const refresh = useCallback(() => {
    setRevision((current) => current + 1);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setState((current) => ({ ...current, error: '', status: 'loading' }));
    void getProviderReadiness(workflowId)
      .then((report) => {
        if (active) setState({ error: '', report, status: 'ready' });
      })
      .catch((error) => {
        if (!active) return;
        setState((current) => ({
          ...current,
          error: error instanceof Error ? error.message : 'AI 服务状态检查失败',
          status: 'failed',
        }));
      });
    return () => {
      active = false;
    };
  }, [enabled, revision, workflowId]);

  return { ...state, refresh };
}
