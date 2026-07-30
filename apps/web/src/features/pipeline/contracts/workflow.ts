export type StageType =
  | 'info_recommend'
  | 'summary'
  | 'outline'
  | 'detail_outline'
  | 'chapter_text'
  | 'cover_image'
  | 'export_artifact';

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

export type MemoryPolicy = {
  read: boolean;
  write: boolean;
  scope: 'project' | 'volume' | 'chapter';
  kinds: string[];
};

export type ModelSettings = {
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  timeout_seconds: number;
};

export type FallbackTarget = {
  provider_profile_id: string;
  model: string;
  enabled: boolean;
  priority: number;
};

export type QualityPolicy = {
  min_score: number;
  retry_on_fail: boolean;
  require_human_review: boolean;
  checks: string[];
};

export type QualityMode = 'fast' | 'balanced' | 'deep';

export type VariantPolicy = {
  enabled: boolean;
  candidate_count: number;
  judge_provider_profile_id: string;
  judge_model: string;
  dimensions: string[];
  retry_on_fail: boolean;
};

export type ProviderProfile = {
  id: string;
  name: string;
  kind: 'openai-compatible' | 'openai-compatible-image';
  template_id: ProviderTemplateId;
  base_url: string;
  api_key_env: string;
  default_model: string;
  model_options?: string[];
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
  integration_tier: 'official' | 'compatibility' | 'gateway' | 'custom';
  description: string;
  supports_response_format: boolean;
  image_size_separator: 'x' | ':';
  image_size_field: 'size' | 'image_size' | 'resolution' | 'aspect_ratio' | 'width_height';
  image_count_field: 'n' | 'images' | 'batch_size' | 'none';
  image_response_field: 'data' | 'images';
  image_endpoint_path: string;
  models_endpoint_path: string;
  image_static_parameters: Record<string, string | number | boolean>;
  supports_image_quality: boolean;
  max_retries: number;
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
  params: Record<string, unknown>;
  input_refs: string[];
  output_key: string;
  memory_policy: MemoryPolicy;
  provider_profile_id: string;
  image_provider_profile_id?: string;
  fallback_targets?: FallbackTarget[];
  image_fallback_targets?: FallbackTarget[];
  model_settings: ModelSettings;
  prompt_template_id: string;
  input_schema: InputField[];
  output_schema: Record<string, unknown>;
  quality_policy: QualityPolicy;
  variant_policy: VariantPolicy;
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
  stage_configs: Record<string, unknown>;
  batch_policy: { enabled: boolean; count: number; parallelism: number };
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
