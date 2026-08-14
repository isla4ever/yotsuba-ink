import { createContext, useContext, useEffect, type ReactNode } from 'react';
import type { SaveStatus } from '../state/useWorkflowAutosave';
import { useProviderReadiness } from './useProviderReadiness';

type ProviderReadinessController = ReturnType<typeof useProviderReadiness>;

const ProviderReadinessContext = createContext<ProviderReadinessController | null>(null);

type Props = {
  children: ReactNode;
  enabled?: boolean;
  /** Readiness is computed from the stored workflow, so it re-runs once each save lands. */
  saveStatus?: SaveStatus;
  workflowId: string;
};

export function ProviderReadinessProvider({ children, enabled = true, saveStatus = 'idle', workflowId }: Props) {
  const readiness = useProviderReadiness(workflowId, enabled);
  const { refresh } = readiness;
  useEffect(() => {
    if (enabled && saveStatus === 'saved') refresh();
  }, [enabled, refresh, saveStatus]);
  return <ProviderReadinessContext.Provider value={readiness}>{children}</ProviderReadinessContext.Provider>;
}

export function useProviderReadinessContext() {
  const readiness = useContext(ProviderReadinessContext);
  if (!readiness) throw new Error('ProviderReadinessProvider is required');
  return readiness;
}
