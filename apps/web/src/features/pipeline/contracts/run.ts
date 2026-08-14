import type { KnowledgeDocument } from './knowledge';
import type { LengthEnvelope, NarrativeScaleProfile } from './narrativeScale';
import type { QualityMode } from './workflow';

export type ChapterProgressItem = {
  volume: string;
  chapter: string;
  status: 'planned' | 'running' | 'completed' | 'failed';
  words: number;
  quality_score: number;
  node_id: string;
};

export type CharacterTier = 'protagonist' | 'major' | 'supporting' | 'minor' | 'npc';

export type NarrativeStageId = 'brief' | 'spine' | 'cast' | 'volumes' | 'detail' | 'text' | 'cover' | 'export';

export type ProviderStageId = Exclude<NarrativeStageId, 'export'>;

export type StructuredOutputMode = 'json_schema' | 'json_object' | 'prompt_only';

export type FrozenModelCapability = Readonly<{
  model_pattern: string;
  structured_output_mode: StructuredOutputMode | null;
  supports_json_schema: boolean | null;
  schema_transform: 'none' | 'openai_subset' | null;
  json_schema_strict: boolean | null;
  max_tokens_field: 'max_tokens' | 'max_completion_tokens' | null;
  sampling_parameter_mode: 'both' | 'temperature' | 'top_p' | 'none' | null;
  requires_json_keyword: boolean | null;
  requires_json_example: boolean | null;
  requires_schema_definition: boolean | null;
  omit_max_tokens_in_structured: boolean | null;
  request_parameters: Readonly<Record<string, unknown>>;
  extra_body_parameters: Readonly<Record<string, unknown>>;
  stage_request_parameters: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  stage_extra_body_parameters: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
}>;

export type FrozenImageModelCapability = Readonly<{
  model_pattern: string;
  image_size_field: 'size' | 'image_size' | 'resolution' | 'aspect_ratio' | 'width_height' | null;
  image_static_parameters: Readonly<Record<string, string | number | boolean>>;
}>;

export type FrozenProviderConfig = Readonly<{
  provider_profile_id: string;
  kind: 'openai-compatible' | 'openai-compatible-image';
  template_id: string;
  base_url: string;
  secret_ref: string;
  model_supported_parameters: Readonly<Record<string, readonly string[]>>;
}>;

export type FrozenProviderTemplate = Readonly<{
  id: string;
  kind: 'openai-compatible' | 'openai-compatible-image';
  supports_response_format: boolean;
  structured_output_mode: StructuredOutputMode;
  supports_json_schema: boolean;
  schema_transform: 'none' | 'openai_subset';
  json_schema_strict: boolean;
  requires_json_keyword: boolean;
  requires_json_example: boolean;
  requires_schema_definition: boolean;
  omit_max_tokens_in_structured: boolean;
  empty_content_policy: 'standard' | 'documented_structured_empty';
  assistant_prefill_mode: 'none' | 'assistant_prefix' | 'deepseek_prefix_beta' | 'kimi_partial';
  assistant_prefill_base_url: string;
  assistant_prefill_tasks: readonly string[];
  assistant_prefill_model_patterns: readonly string[];
  supports_prompt_cache_key: boolean;
  prompt_cache_key_header: '' | 'x-grok-conv-id';
  sampling_parameter_mode: 'both' | 'temperature' | 'top_p' | 'none';
  omit_sampling_when_thinking: boolean;
  image_size_separator: 'x' | ':';
  image_size_field: 'size' | 'image_size' | 'resolution' | 'aspect_ratio' | 'width_height';
  image_count_field: 'n' | 'images' | 'batch_size' | 'none';
  image_response_field: 'data' | 'images';
  image_endpoint_path: string;
  models_endpoint_path: string;
  image_static_parameters: Readonly<Record<string, string | number | boolean>>;
  supports_image_quality: boolean;
  max_retries: number;
  auth_header: 'authorization' | 'api-key';
  max_tokens_field: 'max_tokens' | 'max_completion_tokens';
  request_parameters: Readonly<Record<string, unknown>>;
  extra_body_parameters: Readonly<Record<string, unknown>>;
  stage_request_parameters: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  stage_extra_body_parameters: Readonly<Record<string, Readonly<Record<string, unknown>>>>;
  model_capabilities: readonly FrozenModelCapability[];
  image_model_capabilities: readonly FrozenImageModelCapability[];
  schema_max_chars: number;
  schema_max_depth: number;
  schema_max_properties: number;
  schema_max_enum_values: number;
}>;

export type FrozenStructuredTask = Readonly<{
  schema_digest: string;
  effective_mode: StructuredOutputMode;
}>;

export type FrozenTextProviderBinding = Readonly<{
  provider_profile_id: string;
  provider_config: FrozenProviderConfig;
  template_id: string;
  provider_template: FrozenProviderTemplate;
  provider_config_digest: string;
  provider_template_digest: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  timeout_seconds: number;
  prompt_template_id: string;
  prompt_template: string;
  prompt_digest: string;
  structured_tasks: Readonly<Record<string, FrozenStructuredTask>>;
}>;

export type FrozenCoverAssetBinding = Readonly<{
  provider_profile_id: string;
  provider_config: FrozenProviderConfig;
  template_id: string;
  provider_template: FrozenProviderTemplate;
  provider_config_digest: string;
  provider_template_digest: string;
  model: string;
  candidate_count: number;
  size: string;
  quality: 'low' | 'medium' | 'high';
  timeout_seconds: number;
  failure_policy: 'fail_run';
}>;

export type FactionStance = 'protagonist_side' | 'antagonist_side' | 'neutral' | 'hidden';

export type RelationKind = 'kinship' | 'romance' | 'ally' | 'rival' | 'superior' | 'trade' | 'secret' | 'other';

export type RelationPolarity = 'positive' | 'negative' | 'complex' | 'neutral';

export type FactionInfo = {
  id: string;
  name: string;
  stance?: FactionStance;
  description?: string;
  first_appearance_stage?: NarrativeStageId;
};

export type CharacterNode = {
  id: string;
  name: string;
  role: string;
  faction: string;
  status: string;
  tier: CharacterTier;
  faction_id?: string;
  first_appearance_stage: NarrativeStageId;
  first_appearance_chapter?: string;
  avatar_seed?: string;
  voice_ref?: string;
};

export type CharacterEdgeHistoryEntry = {
  stage?: NarrativeStageId;
  chapter?: string;
  change?: string;
};

export type CharacterEdge = {
  source: string;
  target: string;
  relation: string;
  strength: number;
  kind?: RelationKind;
  polarity?: RelationPolarity;
  valid_from_stage: NarrativeStageId;
  valid_from_chapter?: string;
  history?: CharacterEdgeHistoryEntry[];
};

export type CharacterGraph = {
  nodes: CharacterNode[];
  edges: CharacterEdge[];
  factions?: FactionInfo[];
  updated_by: string;
};

export type UsageSnapshot = {
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  actual_input_tokens?: number;
  actual_output_tokens?: number;
  cached_tokens: number;
  reasoning_tokens?: number;
  candidate_count: number;
  revision_count: number;
  estimated_cost_usd?: number | null;
  elapsed_ms: number;
  image_count?: number;
  failed_image_count?: number;
};

export type RunControlState = 'idle' | 'starting' | 'running' | 'stop_requested' | 'paused' | 'completed' | 'failed';

export type GraphRunStatus = 'created' | 'running' | 'awaiting_decision' | 'completed' | 'failed' | 'cancelled';

export type GraphStageStatus = 'locked' | 'available' | 'running' | 'awaiting_decision' | 'completed' | 'failed';

export type GraphRunDefinition = Readonly<{
  architecture_version: 'phase27-vnext';
  run_id: string;
  project_id: string;
  workflow_id: string;
  workflow_revision: string;
  workflow_digest: string;
  quality_mode: QualityMode;
  inputs: Record<string, unknown>;
  scale_profile: NarrativeScaleProfile;
  provider_bindings: Readonly<Record<ProviderStageId, FrozenTextProviderBinding>>;
  cover_asset_binding: FrozenCoverAssetBinding;
  export_preferences: {
    format: 'md' | 'json' | 'zip';
    author: string;
    version_note: string;
  };
  branch_origin?: {
    source_run_id: string;
    source_checkpoint_id: string;
  } | null;
  created_at: string;
}>;

export type GraphRunReadModel = {
  run_id: string;
  project_id: string;
  thread_id: string;
  status: GraphRunStatus;
  active_stage_id: NarrativeStageId;
  active_chapter_number: number;
  context_manifest_ref: string;
  stage_status: Record<NarrativeStageId, GraphStageStatus>;
  artifact_refs: Partial<Record<NarrativeStageId, string>>;
  pending_decisions: Array<Record<string, unknown>>;
  provider_usage: ProviderUsageSummary;
  failure: Record<string, unknown> | null;
  checkpoint_id: string;
  updated_at: string;
};

export type ChapterContextSnippet = Readonly<{
  ref: string;
  purpose: string;
  text: string;
  source_hash: string;
}>;

export type ChapterContextManifestRecord = Readonly<{
  run_id: string;
  manifest_id: string;
  chapter_id: string;
  attempt: number;
  manifest: Readonly<{
    task: string;
    required: readonly string[];
    optional: readonly string[];
    forbidden: readonly string[];
    snippets: readonly ChapterContextSnippet[];
    budget: Readonly<{ input_chars: number; output_tokens: number }>;
    manifest_hash: string;
  }>;
  created_at: string;
}>;

export type ProviderUsageSummary = {
  provider_operations: number;
  succeeded_operations: number;
  failed_operations: number;
  pending_operations: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  reasoning_tokens: number;
};

export type GraphRunEnvelope = {
  definition: GraphRunDefinition;
  read_model: GraphRunReadModel;
};

export type ConfigProgressItem = {
  key: string;
  label: string;
  done: boolean;
};

export type ConfigProgress = {
  completed: number;
  items: ConfigProgressItem[];
};

export type RunEvent = {
  event_id: string;
  sequence: number;
  occurred_at: string;
  run_id: string;
  thread_id: string;
  type: string;
  stage_id: NarrativeStageId | null;
  node_id: string;
  chapter_id: string;
  status: string;
  payload: Record<string, unknown> | null;
  payload_ref: string;
  checkpoint_id: string;
};

type RunInputBase = {
  title: string;
  theme: string;
  /** Required owning project id for the canonical Run repository. */
  project_id: string;
  quality_mode: QualityMode;
  length_envelope: LengthEnvelope;
  /** Deep-mode structural customization; the backend honors it only in deep quality mode. */
  scale_overrides?: {
    volume_target: number | null;
    turn_target: number | null;
    cast_demand_target: number | null;
  };
  run_intent: {
    project_brief: Record<string, unknown>;
    knowledge_strategy: Record<string, unknown>;
  };
  export_preferences: {
    format: 'md' | 'json' | 'zip';
    author: string;
    version_note: string;
  };
};

export type RunStartInputs = RunInputBase;
export type FrozenRunInputs = RunInputBase;
export type RunInputs = RunInputBase;

export type KnowledgeCollectionState = {
  documents: KnowledgeDocument[];
};
