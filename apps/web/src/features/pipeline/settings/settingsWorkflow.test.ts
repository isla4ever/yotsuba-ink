import { describe, expect, it } from 'vitest';
import type { ProviderProfile, ProviderTemplate } from '../contracts';
import { defaultWorkflow } from '../state/defaultWorkflow';
import { applyProviderTemplate, providerDeletionBlockReason, providerProfileFromTemplate, replaceProviderProfile, withoutProviderProfile, withoutStageProviderExceptions } from './settingsWorkflow';

const provider: ProviderProfile = {
  id: 'image-provider',
  name: 'Custom Image',
  kind: 'openai-compatible-image',
  template_id: 'openai-compatible-image',
  base_url: '',
  api_key_env: 'NOVEL_IMAGE_API_KEY',
  default_model: 'old-model',
  model_options: ['old-model'],
  model_supported_parameters: { 'old-model': ['response_format'] },
  enabled: true,
};

const template: ProviderTemplate = {
  id: 'tokenhub-hunyuan-image',
  label: '腾讯 TokenHub 混元生图',
  kind: 'openai-compatible-image',
  base_url: 'https://tokenhub.tencentmaas.com/v1',
  default_model: 'hy-image-v3.0',
  model_options: ['hy-image-v3.0'],
  api_key_env: 'NOVEL_IMAGE_API_KEY',
  docs_url: 'https://cloud.tencent.com/document/product/1668/129429',
  integration_tier: 'official',
  description: 'TokenHub image contract',
  supports_response_format: true,
  image_size_separator: ':',
  image_size_field: 'size',
  image_count_field: 'images',
  image_response_field: 'data',
  image_endpoint_path: '/images/generations',
  models_endpoint_path: '/models',
  image_static_parameters: {},
  supports_image_quality: false,
  max_retries: 2,
};

describe('provider templates', () => {
  it('applies the authoritative endpoint and replaces incompatible model options', () => {
    expect(applyProviderTemplate(provider, template)).toMatchObject({
      name: template.label,
      template_id: template.id,
      base_url: template.base_url,
      default_model: template.default_model,
      model_options: ['hy-image-v3.0'],
      model_supported_parameters: {},
    });
  });

  it('does not apply a template with a different provider kind', () => {
    expect(applyProviderTemplate(provider, { ...template, kind: 'openai-compatible' })).toBe(provider);
  });

  it('creates additional provider profiles with deterministic unique ids', () => {
    const created = providerProfileFromTemplate(template, ['provider-tokenhub-hunyuan-image']);

    expect(created.id).toBe('provider-tokenhub-hunyuan-image-2');
    expect(created).toMatchObject({
      kind: 'openai-compatible-image',
      template_id: 'tokenhub-hunyuan-image',
      enabled: true,
      is_global_default: false,
    });
  });

  it('updates assigned stage defaults without overwriting explicit stage models', () => {
    const next = applyProviderTemplate(provider, template);
    const workflow = {
      id: 'workflow', name: 'Workflow', version: '1', global_inputs: [], provider_profiles: [provider],
      prompt_templates: [], stage_configs: {}, batch_policy: { enabled: false, count: 1, parallelism: 1 },
      quality_mode: 'balanced' as const, edges: [],
      nodes: [
        {
          id: 'cover', type: 'cover' as const, label: 'Cover',
          provider_profile_id: provider.id, image_provider_profile_id: provider.id,
          model_settings: { model: 'old-model', temperature: 0.2, max_tokens: 100, top_p: 1, timeout_seconds: 30 },
          prompt_template_id: '', input_schema: [],
        },
      ],
    };

    const updated = replaceProviderProfile(workflow, next);

    expect(updated.nodes[0].model_settings.model).toBe('hy-image-v3.0');
  });

  it('blocks deletion for defaults and stage assignments, but removes unused profiles', () => {
    const unused = { ...provider, id: 'unused-provider', is_global_default: false };
    const workflow = {
      id: 'workflow', name: 'Workflow', version: '1', global_inputs: [], provider_profiles: [provider, unused],
      prompt_templates: [], stage_configs: {}, batch_policy: { enabled: false, count: 1, parallelism: 1 },
      quality_mode: 'balanced' as const, edges: [],
      nodes: [{
        id: 'cover', type: 'cover' as const, label: 'Cover',
        provider_profile_id: 'text-provider', image_provider_profile_id: provider.id,
        model_settings: { model: 'old-model', temperature: 0.2, max_tokens: 100, top_p: 1, timeout_seconds: 30 },
        prompt_template_id: '', input_schema: [],
      }],
    };

    expect(providerDeletionBlockReason(workflow, provider.id)).toContain('Cover');
    expect(providerDeletionBlockReason(workflow, unused.id)).toBe('');
    expect(withoutProviderProfile(workflow, unused.id).provider_profiles.map((item) => item.id)).toEqual([provider.id]);
  });

  it('restores stage service exceptions without changing stage policies', () => {
    const text = { ...provider, id: 'text-default', kind: 'openai-compatible' as const, is_global_default: true, default_model: 'text-model' };
    const workflow = {
      id: 'workflow', name: 'Workflow', version: '1', global_inputs: [], provider_profiles: [text, { ...provider, is_global_default: true }],
      prompt_templates: [], stage_configs: {}, batch_policy: { enabled: false, count: 1, parallelism: 1 },
      quality_mode: 'balanced' as const, edges: [],
      nodes: [{
        id: 'cover', type: 'cover' as const, label: 'Cover',
        provider_profile_id: 'other-text', image_provider_profile_id: 'other-image',
        model_settings: { model: 'other-model', temperature: 0.2, max_tokens: 100, top_p: 1, timeout_seconds: 30 },
        prompt_template_id: '', input_schema: [],
      }],
    };

    const updated = withoutStageProviderExceptions(workflow);

    expect(updated.nodes[0]).toMatchObject({
      provider_profile_id: 'text-default', image_provider_profile_id: 'image-provider',
      model_settings: { model: 'text-model', temperature: 0.2 },
    });
  });

  it('does not reset bindings when no explicit global Provider exists', () => {
    const workflow = {
      ...defaultWorkflow,
      provider_profiles: defaultWorkflow.provider_profiles.map((item) => ({
        ...item,
        is_global_default: false,
      })),
    };

    expect(withoutStageProviderExceptions(workflow)).toBe(workflow);
  });
});
