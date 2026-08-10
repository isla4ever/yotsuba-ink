import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { resetStageProviderException, stageHasProviderException } from './stageProviderException';

describe('stage provider exceptions', () => {
  it('restores the explicit stage Provider binding to the configured default', () => {
    const stage = {
      ...defaultWorkflow.nodes[0],
      provider_profile_id: 'stage-provider',
    };

    const restored = resetStageProviderException(stage, defaultWorkflow.provider_profiles);
    expect(stageHasProviderException(stage, defaultWorkflow.provider_profiles)).toBe(true);
    expect(restored.provider_profile_id).toBe(defaultWorkflow.provider_profiles[0].id);
  });

  it('does not infer a default from the first Provider of a kind', () => {
    const providers = defaultWorkflow.provider_profiles.map((provider) => ({
      ...provider,
      is_global_default: false,
    }));
    const stage = defaultWorkflow.nodes[0];

    expect(stageHasProviderException(stage, providers)).toBe(true);
    expect(resetStageProviderException(stage, providers)).toBe(stage);
  });
});
