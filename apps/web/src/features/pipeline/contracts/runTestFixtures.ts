import type {
  FrozenCoverAssetBinding,
  FrozenProviderConfig,
  FrozenProviderTemplate,
  FrozenTextProviderBinding,
  GraphRunDefinition,
  ProviderStageId,
} from './run';

const DIGEST = 'a'.repeat(64);
const PROVIDER_STAGES: readonly ProviderStageId[] = [
  'brief',
  'spine',
  'cast',
  'volumes',
  'detail',
  'text',
  'cover',
];

function providerConfig(
  providerProfileId: string,
  kind: FrozenProviderConfig['kind'],
  templateId: string,
): FrozenProviderConfig {
  return {
    provider_profile_id: providerProfileId,
    kind,
    template_id: templateId,
    base_url: `https://${providerProfileId}.invalid/v1`,
    secret_ref: providerProfileId,
    model_supported_parameters: {},
  };
}

function providerTemplate(
  id: string,
  kind: FrozenProviderTemplate['kind'],
): FrozenProviderTemplate {
  return {
    id,
    kind,
    supports_response_format: kind === 'openai-compatible',
    structured_output_mode: kind === 'openai-compatible' ? 'json_object' : 'prompt_only',
    supports_json_schema: false,
    schema_transform: 'none',
    json_schema_strict: false,
    requires_json_keyword: kind === 'openai-compatible',
    requires_json_example: kind === 'openai-compatible',
    requires_schema_definition: false,
    omit_max_tokens_in_structured: false,
    empty_content_policy: 'standard',
    assistant_prefill_mode: 'none',
    assistant_prefill_base_url: '',
    assistant_prefill_tasks: [],
    assistant_prefill_model_patterns: [],
    supports_prompt_cache_key: false,
    prompt_cache_key_header: '',
    sampling_parameter_mode: 'both',
    omit_sampling_when_thinking: false,
    image_size_separator: 'x',
    image_size_field: 'size',
    image_count_field: 'n',
    image_response_field: 'data',
    image_endpoint_path: '/images/generations',
    models_endpoint_path: '/models',
    image_static_parameters: {},
    supports_image_quality: true,
    max_retries: 0,
    auth_header: 'authorization',
    max_tokens_field: 'max_tokens',
    request_parameters: {},
    extra_body_parameters: {},
    stage_request_parameters: {},
    stage_extra_body_parameters: {},
    model_capabilities: [],
    image_model_capabilities: [],
    schema_max_chars: 15_000,
    schema_max_depth: 5,
    schema_max_properties: 100,
    schema_max_enum_values: 10_000,
  };
}

function textBinding(stageId: ProviderStageId): FrozenTextProviderBinding {
  const providerProfileId = 'text-provider';
  const templateId = 'deepseek-text';
  return {
    provider_profile_id: providerProfileId,
    provider_config: providerConfig(providerProfileId, 'openai-compatible', templateId),
    template_id: templateId,
    provider_template: providerTemplate(templateId, 'openai-compatible'),
    provider_config_digest: DIGEST,
    provider_template_digest: DIGEST,
    model: 'deepseek-v4-pro',
    temperature: 0.3,
    max_tokens: 12_000,
    top_p: 0.8,
    timeout_seconds: 30,
    prompt_template_id: `prompt-${stageId}`,
    prompt_template: `Phase 27 ${stageId} prompt`,
    prompt_digest: DIGEST,
    structured_tasks: {},
  };
}

export function frozenProviderBindingsFixture(): GraphRunDefinition['provider_bindings'] {
  return Object.fromEntries(
    PROVIDER_STAGES.map((stageId) => [stageId, textBinding(stageId)]),
  ) as GraphRunDefinition['provider_bindings'];
}

export function frozenCoverAssetBindingFixture(): FrozenCoverAssetBinding {
  const providerProfileId = 'image-provider';
  const templateId = 'openai-compatible-image';
  return {
    provider_profile_id: providerProfileId,
    provider_config: providerConfig(providerProfileId, 'openai-compatible-image', templateId),
    template_id: templateId,
    provider_template: providerTemplate(templateId, 'openai-compatible-image'),
    provider_config_digest: DIGEST,
    provider_template_digest: DIGEST,
    model: 'gpt-image-2',
    candidate_count: 3,
    size: '1024x1536',
    quality: 'medium',
    timeout_seconds: 180,
    failure_policy: 'fail_run',
  };
}
