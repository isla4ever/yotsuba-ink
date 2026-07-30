import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { resetStageProviderException, stageHasProviderException } from './stageProviderException';

describe('stage provider exceptions', () => {
  it('does not classify the shared fallback chain as a stage exception', () => {
    const stage = {
      ...defaultWorkflow.nodes[0],
      fallback_targets: [{ provider_profile_id: 'backup', model: 'backup-model', enabled: true, priority: 1 }],
    };

    expect(stageHasProviderException(stage, defaultWorkflow.provider_profiles)).toBe(false);
  });

  it('preserves shared fallbacks when restoring the stage provider default', () => {
    const fallback = { provider_profile_id: 'backup', model: 'backup-model', enabled: true, priority: 1 };
    const stage = {
      ...defaultWorkflow.nodes[0],
      provider_profile_id: 'stage-provider',
      fallback_targets: [fallback],
    };

    expect(resetStageProviderException(stage, defaultWorkflow.provider_profiles).fallback_targets).toEqual([fallback]);
  });
});
