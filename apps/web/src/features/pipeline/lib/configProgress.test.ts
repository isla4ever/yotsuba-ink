import { describe, expect, it } from 'vitest';
import type { ProviderReadinessReport } from '../contracts';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { buildConfigProgress } from './configProgress';

const readyReport: ProviderReadinessReport = {
  ok: true,
  scope: 'configuration_only',
  checked_provider_count: 2,
  checks: [],
  message: '',
};

describe('header configuration progress', () => {
  it('uses the shared server readiness result for the model step', () => {
    const progress = buildConfigProgress(defaultWorkflow, [], { status: 'ready', report: readyReport });
    expect(progress.completed).toBe(5);
    expect(progress.items.find((item) => item.key === 'model')?.done).toBe(true);
  });

  it('keeps the model step incomplete while readiness is blocked or unresolved', () => {
    const blocked = buildConfigProgress(defaultWorkflow, [], {
      status: 'ready',
      report: { ...readyReport, ok: false },
    });
    const loading = buildConfigProgress(defaultWorkflow, [], { status: 'loading' });

    expect(blocked.completed).toBe(4);
    expect(loading.completed).toBe(4);
  });
});
