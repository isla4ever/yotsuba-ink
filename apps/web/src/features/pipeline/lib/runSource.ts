import type { RunInputs } from '../contracts';

export type RunSource = 'backend';

const STORAGE_KEY = 'novel-workflow-run-source';

export function getPreferredRunSource(): RunSource {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
  const envSource = normalizeRunSource(env?.VITE_NOVEL_RUN_SOURCE);
  if (envSource) return envSource;
  if (typeof window === 'undefined') return 'backend';
  return normalizeRunSource(window.localStorage.getItem(STORAGE_KEY)) ?? 'backend';
}

export function executionModeForRunSource(source: RunSource): NonNullable<RunInputs['execution_mode']> {
  void source;
  return 'live';
}

export function isBackendRunSource(source: RunSource) {
  return source === 'backend';
}

function normalizeRunSource(value: string | null | undefined): RunSource | null {
  if (value === 'backend' || value === 'real' || value === 'live') return 'backend';
  if (value === 'frontend-mock' || value === 'mock' || value === 'demo') return 'backend';
  return null;
}
