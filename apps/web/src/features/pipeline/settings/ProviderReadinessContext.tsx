import { createContext, useContext, type ReactNode } from 'react';
import { useProviderReadiness } from './useProviderReadiness';

type ProviderReadinessController = ReturnType<typeof useProviderReadiness>;

const ProviderReadinessContext = createContext<ProviderReadinessController | null>(null);

export function ProviderReadinessProvider({ children, enabled = true, workflowId }: { children: ReactNode; enabled?: boolean; workflowId: string }) {
  const readiness = useProviderReadiness(workflowId, enabled);
  return <ProviderReadinessContext.Provider value={readiness}>{children}</ProviderReadinessContext.Provider>;
}

export function useProviderReadinessContext() {
  const readiness = useContext(ProviderReadinessContext);
  if (!readiness) throw new Error('ProviderReadinessProvider is required');
  return readiness;
}
