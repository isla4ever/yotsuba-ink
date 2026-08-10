export type StageType =
  | 'info'
  | 'characters'
  | 'summary'
  | 'outline'
  | 'detail'
  | 'text'
  | 'cover'
  | 'export';

export type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'tags' | 'boolean';

export type InputField = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  default?: unknown;
  help?: string;
  /** Phase 12 A3: small-print guidance rendered under the field label. */
  hint?: string;
  /** Phase 12 A3: placeholder copy for the empty control. */
  placeholder?: string;
  options?: string[];
};

export type ModelSettings = {
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  timeout_seconds: number;
};

export type QualityMode = 'fast' | 'balanced' | 'deep';

export type ProviderProfile = {
  id: string;
  name: string;
  kind: 'openai-compatible' | 'openai-compatible-image';
  template_id: ProviderTemplateId;
  base_url: string;
  api_key_env: string;
  default_model: string;
  model_options?: string[];
  model_supported_parameters?: Record<string, string[]>;
  estimated_cost_per_output_usd?: number | null;
  is_global_default?: boolean;
  has_saved_secret?: boolean;
  has_env_secret?: boolean;
  enabled: boolean;
};

export type ProviderTemplateId = string;

export type ProviderTemplate = {
  id: ProviderTemplateId;
  label: string;
  kind: ProviderProfile['kind'];
  base_url: string;
  default_model: string;
  model_options: string[];
  api_key_env: string;
  docs_url: string;
  capability_docs?: string[];
  integration_tier: 'official' | 'compatibility' | 'gateway' | 'custom';
  description: string;
  supports_response_format: boolean;
  structured_output_mode?: 'json_schema' | 'json_object' | 'prompt_only';
  supports_json_schema?: boolean;
  schema_transform?: 'none' | 'openai_subset';
  json_schema_strict?: boolean;
  requires_json_keyword?: boolean;
  requires_json_example?: boolean;
  requires_schema_definition?: boolean;
  omit_max_tokens_in_structured?: boolean;
  empty_content_policy?: 'standard' | 'documented_structured_empty';
  assistant_prefill_mode?: 'none' | 'assistant_prefix' | 'deepseek_prefix_beta' | 'kimi_partial';
  assistant_prefill_base_url?: string;
  assistant_prefill_tasks?: string[];
  supports_prompt_cache_key?: boolean;
  prompt_cache_key_header?: '' | 'x-grok-conv-id';
  sampling_parameter_mode?: 'both' | 'temperature' | 'top_p' | 'none';
  omit_sampling_when_thinking?: boolean;
  thinking_parameter?: string;
  structured_output_notes?: string;
  image_size_separator: 'x' | ':';
  image_size_field: 'size' | 'image_size' | 'resolution' | 'aspect_ratio' | 'width_height';
  image_count_field: 'n' | 'images' | 'batch_size' | 'none';
  image_response_field: 'data' | 'images';
  image_endpoint_path: string;
  models_endpoint_path: string;
  models_auth_header?: 'inherit' | 'authorization' | 'api-key' | 'x-portkey-api-key';
  models_query_parameters?: Record<string, string>;
  discovers_model_parameters?: boolean;
  required_model_parameter_any_of?: string[];
  image_static_parameters: Record<string, string | number | boolean>;
  supports_image_quality: boolean;
  max_retries: number;
  auth_header?: 'authorization' | 'api-key';
  max_tokens_field?: 'max_tokens' | 'max_completion_tokens';
  request_parameters?: Record<string, unknown>;
  extra_body_parameters?: Record<string, unknown>;
  stage_request_parameters?: Record<string, Record<string, unknown>>;
  stage_extra_body_parameters?: Record<string, Record<string, unknown>>;
  schema_max_chars?: number;
  schema_max_depth?: number;
  schema_max_properties?: number;
  schema_max_enum_values?: number;
  model_capabilities?: Array<{
    model_pattern: string;
    capability_docs?: string[];
    evidence_status?: 'verified' | 'conservative' | 'experimental';
    evidence_note?: string;
    structured_output_mode?: 'json_schema' | 'json_object' | 'prompt_only' | null;
    supports_json_schema?: boolean | null;
    schema_transform?: 'none' | 'openai_subset' | null;
    json_schema_strict?: boolean | null;
    max_tokens_field?: 'max_tokens' | 'max_completion_tokens' | null;
    sampling_parameter_mode?: 'both' | 'temperature' | 'top_p' | 'none' | null;
    requires_json_keyword?: boolean | null;
    requires_json_example?: boolean | null;
    requires_schema_definition?: boolean | null;
    omit_max_tokens_in_structured?: boolean | null;
    request_parameters?: Record<string, unknown>;
    extra_body_parameters?: Record<string, unknown>;
    stage_request_parameters?: Record<string, Record<string, unknown>>;
    stage_extra_body_parameters?: Record<string, Record<string, unknown>>;
  }>;
  image_model_capabilities?: Array<{
    model_pattern: string;
    capability_docs?: string[];
    evidence_status?: 'verified' | 'conservative' | 'experimental';
    evidence_note?: string;
    image_size_field?: 'size' | 'image_size' | 'resolution' | 'aspect_ratio' | 'width_height' | null;
    image_static_parameters?: Record<string, string | number | boolean>;
  }>;
  execution_allowed?: boolean;
  execution_policy_note?: string;
  workflow_execution_allowed?: boolean;
  workflow_execution_policy_note?: string;
};

export type PromptTemplate = {
  id: string;
  name: string;
  stage_type: StageType;
  content: string;
  variables: string[];
};

export type WorkflowStage = {
  id: string;
  type: StageType;
  label: string;
  provider_profile_id: string;
  image_provider_profile_id?: string;
  model_settings: ModelSettings;
  prompt_template_id: string;
  input_schema: InputField[];
  generation_budget?: {
    target_chars: number;
    min_chars: number;
    max_chars: number;
    max_tokens: number;
    description?: string;
  } | null;
};

export type CanvasLayout = {
  nodes: Record<string, { x: number; y: number }>;
  viewport?: { x: number; y: number; zoom: number };
  crosscutting_visible: boolean;
  locked?: boolean;
};

export type WorkflowDefinition = {
  id: string;
  name: string;
  version: string;
  /** Phase 11: reusable template flag (templates are copied per project on creation). */
  is_template?: boolean;
  global_inputs: InputField[];
  provider_profiles: ProviderProfile[];
  prompt_templates: PromptTemplate[];
  quality_mode: QualityMode;
  canvas_layout?: CanvasLayout;
  nodes: WorkflowStage[];
  edges: Array<{ id: string; source: string; target: string }>;
};

export type InspectorTarget =
  | { kind: 'stage'; id: string }
  | { kind: 'wiki'; id: 'wiki-layer' }
  | { kind: 'quality'; id: 'quality-layer' };

export type WorkspaceKey =
  | 'pipeline'
  | 'providers'
  | 'prompts'
  | 'wiki'
  | 'characters'
  | 'quality'
  | 'chapters'
  | 'history';
