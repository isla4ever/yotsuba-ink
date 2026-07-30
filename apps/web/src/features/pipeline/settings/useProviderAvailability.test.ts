import { describe, expect, it } from 'vitest';
import type { ProviderProfile } from '../contracts';
import { providerSecretStatus, type ProviderAvailabilityState } from './useProviderAvailability';

const provider: ProviderProfile = {
  id: 'text-provider',
  name: 'Text Provider',
  kind: 'openai-compatible',
  template_id: 'openai-compatible-text',
  base_url: '',
  api_key_env: '',
  default_model: 'model-a',
  enabled: true,
};

describe('provider secret availability', () => {
  it('uses the server secret truth even when the workflow profile is stale', () => {
    const availability: ProviderAvailabilityState = {
      byProvider: { 'text-provider': { has_saved_secret: true, has_env_secret: false } },
      templates: [],
      status: 'ready',
    };

    expect(providerSecretStatus(provider, availability)).toBe('已保存本地密钥');
  });

  it('does not report a missing secret while the server status is unknown', () => {
    expect(providerSecretStatus(provider, { byProvider: {}, templates: [], status: 'loading' })).toBe('正在核验密钥状态');
    expect(providerSecretStatus(provider, { byProvider: {}, templates: [], status: 'failed' })).toBe('密钥状态未确认');
  });
});
