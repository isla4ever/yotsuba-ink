import { describe, expect, it } from 'vitest';
import type { ProviderProfile, WorkflowStage } from '../contracts';
import { addFallbackTarget, moveFallbackTarget, removePrimaryFromFallbacks } from './providerFallback';

const providers: ProviderProfile[] = [
  { id: 'primary', name: '主接口', kind: 'openai-compatible', template_id: 'openai-compatible-text', base_url: '', api_key_env: '', default_model: 'model-a', enabled: true },
  { id: 'backup-a', name: '备用 A', kind: 'openai-compatible', template_id: 'openai-compatible-text', base_url: '', api_key_env: '', default_model: 'model-b', enabled: true },
  { id: 'backup-b', name: '备用 B', kind: 'openai-compatible', template_id: 'openai-compatible-text', base_url: '', api_key_env: '', default_model: 'model-c', enabled: true },
];

const stage = {
  id: 'summary', type: 'summary', label: '梗概', provider_profile_id: 'primary', model_settings: { model: 'model-a' },
} as WorkflowStage;

describe('provider fallback configuration', () => {
  it('adds distinct enabled providers in deterministic priority order', () => {
    const first = addFallbackTarget(stage, providers, 'text');
    const second = addFallbackTarget(first, providers, 'text');
    expect(second.fallback_targets).toEqual([
      { provider_profile_id: 'backup-a', model: 'model-b', enabled: true, priority: 1 },
      { provider_profile_id: 'backup-b', model: 'model-c', enabled: true, priority: 2 },
    ]);
  });

  it('reorders priorities and removes a newly selected primary', () => {
    const configured = addFallbackTarget(addFallbackTarget(stage, providers, 'text'), providers, 'text');
    const moved = moveFallbackTarget(configured, 'text', 2, -1);
    expect(moved.fallback_targets?.map((target) => target.provider_profile_id)).toEqual(['backup-b', 'backup-a']);
    expect(removePrimaryFromFallbacks(moved, 'text', 'backup-b').fallback_targets).toEqual([
      { provider_profile_id: 'backup-a', model: 'model-b', enabled: true, priority: 1 },
    ]);
  });
});
