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
  kind: 'mock' | 'openai-compatible' | 'image-mock';
  base_url: string;
  api_key_env: string;
  default_model: string;
  model_options?: string[];
  is_global_default?: boolean;
  enabled: boolean;
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
  model_settings: ModelSettings;
  prompt_template_id: string;
  input_schema: InputField[];
  output_schema: Record<string, unknown>;
  quality_policy: QualityPolicy;
  variant_policy: VariantPolicy;
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
