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

export type CanvasLayout = {
  nodes: Record<string, { x: number; y: number }>;
  viewport?: { x: number; y: number; zoom: number };
  crosscutting_visible: boolean;
  locked?: boolean;
};

export type InspectorTarget =
  | { kind: 'stage'; id: string }
  | { kind: 'wiki'; id: 'wiki-layer' }
  | { kind: 'quality'; id: 'quality-layer' };

export type RunEvent = {
  type: string;
  run_id: string;
  node_id?: string;
  node_type?: StageType;
  label?: string;
  output_key?: string;
  result?: unknown;
  error?: string;
  phase?: 'planning' | 'writing' | string;
  memory?: Record<string, unknown>;
  written?: Array<Record<string, unknown>>;
  status?: Record<string, unknown>;
  state?: Record<string, unknown>;
  quality?: QualityEvent;
  quality_report?: QualityReport;
  directive?: RevisionDirective;
  context_packet?: ChapterContextPacket;
  story_bible?: Record<string, unknown>;
  findings?: QualityFinding[];
  chapters?: ChapterProgressItem[];
  chapter?: string;
  delta?: string;
  content?: string;
  words?: number;
  variant?: ChapterDraft | Record<string, unknown>;
  variants?: Array<ChapterDraft | Record<string, unknown>>;
  selected?: SelectedVariant;
  preview?: unknown;
  token_estimates?: Record<string, unknown>;
  worldbuilding?: Record<string, unknown>;
  wiki_state?: Record<string, unknown>;
  character_graph?: CharacterGraph;
  reason?: string;
  blocker?: string;
  query_rewrite?: string;
  results?: Array<Record<string, unknown>>;
  artifact?: unknown;
  message?: string;
  source?: string;
  target?: string;
  title?: string;
  url?: string;
  section?: string;
  score?: number;
};

export type WorkspaceKey =
  | 'pipeline'
  | 'providers'
  | 'prompts'
  | 'wiki'
  | 'characters'
  | 'quality'
  | 'chapters'
  | 'history';

export type QualityEvent = {
  node_id: string;
  node_type: StageType;
  label: string;
  score: number;
  min_score: number;
  passed: boolean;
  checks: Record<string, boolean | number | string>;
  warnings: string[];
};

export type QualityFinding = {
  id: string;
  dimension: string;
  severity: 'info' | 'warning' | 'blocking';
  message: string;
  evidence?: string;
  target?: string;
  blocking: boolean;
};

export type QualityReport = {
  node_id: string;
  node_type: StageType;
  label: string;
  chapter?: string;
  score: number;
  passed: boolean;
  mode: QualityMode;
  findings: QualityFinding[];
  constraint_hits: string[];
  revision_required: boolean;
};

export type RevisionDirective = {
  id: string;
  node_id: string;
  chapter?: string;
  severity: 'info' | 'warning' | 'blocking';
  issue: string;
  evidence?: string;
  target?: string;
  instruction: string;
  status: 'pending' | 'applied' | 'failed' | 'skipped';
  attempts: number;
};

export type ChapterContextPacket = {
  chapter: string;
  chapter_index: number;
  chapter_kind: 'first' | 'normal' | 'volume_start' | 'volume_end' | 'finale';
  story_brief: string;
  summary: string;
  volume_goal: string;
  chapter_outline: string;
  previous_chapter_summary: string;
  previous_volume_ending: string;
  character_state: Record<string, unknown>;
  open_foreshadows: Array<Record<string, unknown>>;
  world_rules: string[];
};

export type ChapterProgressItem = {
  volume: string;
  chapter: string;
  status: 'planned' | 'running' | 'completed' | 'failed';
  words: number;
  quality_score: number;
  node_id: string;
};

export type CharacterNode = {
  id: string;
  name: string;
  role: string;
  faction: string;
  status: string;
};

export type CharacterEdge = {
  source: string;
  target: string;
  relation: string;
  strength: number;
};

export type CharacterGraph = {
  nodes: CharacterNode[];
  edges: CharacterEdge[];
  updated_by: string;
};

export type KnowledgeDocument = {
  doc_id: string;
  project_id?: string;
  title: string;
  filename: string;
  content_type?: string;
  char_count?: number;
  chunk_count: number;
  status: string;
  parser: string;
  backend?: string;
  capability_note?: string;
  preview: string;
  created_at?: string;
};

export type KnowledgeDeleteResponse = {
  ok: boolean;
  doc_id: string;
  deleted_chunks?: number;
  backend?: string;
  backend_synced?: boolean;
  message?: string;
};

export type ChapterDraft = {
  chapter: string;
  volume: string;
  content: string;
  status: 'drafting' | 'completed' | 'selected';
  words: number;
  variant_id: string;
  score: number;
};

export type SelectedVariant = {
  node_id: string;
  chapter?: string;
  variant_id: string;
  score: number;
  reason: string;
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
