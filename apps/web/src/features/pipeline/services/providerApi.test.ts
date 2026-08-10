import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ProviderProfile } from '../contracts';
import { deleteProviderProfile, discoverProviderModels, getProviderReadiness, setDefaultProviderProfile, testProviderConnection } from './providerApi';

const provider: ProviderProfile = {
  id: 'text-provider',
  name: 'Text Provider',
  kind: 'openai-compatible',
  template_id: 'openai-compatible-text',
  base_url: 'https://provider.example/v1',
  api_key_env: '',
  default_model: 'model-a',
  model_options: ['model-a'],
  estimated_cost_per_output_usd: null,
  is_global_default: true,
  enabled: true,
};

describe('provider API', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('preserves the public provider error code and actionable message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false,
      provider_id: provider.id,
      kind: provider.kind,
      model: provider.default_model,
      error_code: 'insufficient_balance',
      message: 'Provider 余额或调用额度不足，请充值后重试。',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

    const result = await testProviderConnection(provider);

    expect(result).toMatchObject({
      ok: false,
      error_code: 'insufficient_balance',
      message: expect.stringContaining('余额'),
    });
  });

  it('requests the server-owned configuration readiness report without starting a run', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false,
      scope: 'configuration_only',
      checked_provider_count: 2,
      checks: [{
        provider_id: 'image-provider',
        provider_name: 'Image Provider',
        expected_kind: 'openai-compatible-image',
        used_by: ['AI 封面图片生成'],
        ready: false,
        issue_codes: ['base_url_missing', 'secret_missing'],
        message: 'Image Provider 缺少 Base URL、缺少 API Key',
      }],
      message: '真实运行 Provider 配置不完整',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await getProviderReadiness('default-novel-workflow');

    expect(result.scope).toBe('configuration_only');
    expect(result.checks[0].issue_codes).toEqual(['base_url_missing', 'secret_missing']);
    expect(fetchMock).toHaveBeenCalledWith('/api/providers/readiness', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ workflow_id: 'default-novel-workflow' }),
    }));
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/api/runs'), expect.anything());
  });

  it('uses dedicated local lifecycle endpoints for defaults and deletion', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([provider]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true, provider_id: provider.id }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(setDefaultProviderProfile(provider.id, provider.kind)).resolves.toEqual([provider]);
    await expect(deleteProviderProfile(provider.id)).resolves.toEqual({ ok: true, provider_id: provider.id });

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/providers/default', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ provider_id: provider.id, kind: provider.kind }),
    }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, `/api/providers/${provider.id}`, { method: 'DELETE' });
  });

  it('discovers model candidates through the provider-scoped read action', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      provider_id: provider.id,
      kind: provider.kind,
      models: ['model-a', 'model-b'],
      added_models: ['model-b'],
      model_supported_parameters: {},
      error_code: '',
      message: '已读取 2 个上游模型，新增 1 个候选；未触发内容生成。',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await discoverProviderModels(provider.id, 'transient-key');

    expect(result.models).toEqual(['model-a', 'model-b']);
    expect(fetchMock).toHaveBeenCalledWith(`/api/providers/${provider.id}/models/discover`, expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ api_key: 'transient-key' }),
    }));
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/api/runs'), expect.anything());
  });
});
