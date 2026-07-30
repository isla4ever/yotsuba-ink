import type { KnowledgeDocument } from './knowledge';
import type { QualityEvent, QualityFinding, QualityReport, RevisionDirective } from './quality';
import type { QualityMode, StageType } from './workflow';
import type { ChapterModelReview, ChapterWritebackProposal } from './chapterReview';

export type ChapterContextPacket = {
  chapter: string;
  chapter_index: number;
  chapter_kind: 'first' | 'normal' | 'volume_start' | 'volume_end' | 'finale';
  story_brief: string;
  summary: string;
  volume_goal: string;
  volume_title?: string;
  volume_chapter_range?: string;
  next_volume_goal?: string;
  chapter_outline: string;
  previous_chapter_summary: string;
  previous_volume_ending: string;
  transition_directive?: string;
  character_state: Record<string, unknown>;
  open_foreshadows: Array<Record<string, unknown>>;
  world_rules: string[];
};

/** Phase 10.4a: per-chapter entry in `story_bible.tension_track[]` (upserted by chapter). */
export type TensionTrackEntry = {
  chapter: string;
  score: number;
  basis: string;
  source?: string;
};

export type ChapterProgressItem = {
  volume: string;
  chapter: string;
  status: 'planned' | 'running' | 'completed' | 'failed';
  words: number;
  quality_score: number;
  node_id: string;
};

export type CharacterTier = 'protagonist' | 'major' | 'supporting' | 'minor' | 'npc';

export type FactionStance = 'protagonist_side' | 'antagonist_side' | 'neutral' | 'hidden';

export type RelationKind = 'kinship' | 'romance' | 'ally' | 'rival' | 'superior' | 'trade' | 'secret' | 'other';

export type RelationPolarity = 'positive' | 'negative' | 'complex' | 'neutral';

export type FactionInfo = {
  id: string;
  name: string;
  stance?: FactionStance;
  description?: string;
  first_appearance_stage?: string;
};

export type CharacterNode = {
  id: string;
  name: string;
  role: string;
  faction: string;
  status: string;
  tier?: CharacterTier;
  faction_id?: string;
  first_appearance_stage?: string;
  first_appearance_chapter?: string;
  avatar_seed?: string;
  voice_ref?: string;
};

export type CharacterEdgeHistoryEntry = {
  stage?: string;
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
  valid_from_stage?: string;
  valid_from_chapter?: string;
  history?: CharacterEdgeHistoryEntry[];
};

export type CharacterGraph = {
  nodes: CharacterNode[];
  edges: CharacterEdge[];
  factions?: FactionInfo[];
  updated_by: string;
};

export type ChapterDraft = {
  chapter: string;
  volume: string;
  content: string;
  status: 'drafting' | 'completed' | 'selected';
  words: number;
  variant_id: string;
  score: number;
  artifact?: Record<string, unknown>;
};

export type SelectedVariant = {
  node_id: string;
  chapter?: string;
  variant_id: string;
  score: number;
  reason: string;
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

export type StageUsageSummary = {
  stage_key: string;
  node_id: string;
  label: string;
  stage_type: string;
  provider_profile_id?: string;
  model?: string;
  usage: UsageSnapshot;
};

export type RunControlState = 'idle' | 'starting' | 'running' | 'stop_requested' | 'paused' | 'completed' | 'failed';

export type StageTransitionSummary = {
  node_id: string;
  label: string;
  status: 'started' | 'completed';
  elapsed_ms?: number;
  estimated_tokens?: number;
  cached_tokens?: number;
  estimated_cost_usd?: number | null;
  words?: number;
  quality_action?: string;
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

export type ParallelDeliveryState = {
  status?: 'idle' | 'running' | 'ready' | 'degraded' | 'cancelled';
  unlocked_after?: string;
  tracks?: string[];
  ready_count?: number;
  total?: number;
  message?: string;
};

export type RunEvent = {
  type: string;
  run_id: string;
  created_at?: string;
  node_id?: string;
  node_type?: StageType;
  label?: string;
  output_key?: string;
  result?: unknown;
  error?: string;
  errors?: string[];
  schema_name?: string;
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
  usage?: UsageSnapshot;
  usage_summary?: StageUsageSummary;
  next_step?: string;
  execution_mode?: 'live' | 'demo';
  artifact_source?: 'live' | 'fixture';
  message?: string;
  source?: string;
  target?: string;
  title?: string;
  url?: string;
  section?: string;
  candidate_id?: string;
  candidate_index?: number;
  candidate_count?: number;
  /** Provider execution events (10.4a): 1-based attempt along the fallback route. */
  attempt?: number;
  is_fallback?: boolean;
  failure_code?: string;
  asset_status?: 'planned' | 'generating' | 'ready' | 'failed' | 'blocked';
  ready_count?: number;
  failed_count?: number;
  total?: number;
  generation_key?: string;
  error_code?: string;
  provider_profile_id?: string;
  model?: string;
  candidate_signature?: string;
  chapter_id?: string;
  operation?: string;
  request_id?: string;
  score?: number;
  /** `chapter_tension_scored`: the model-review basis text behind the 0-10 tension score. */
  basis?: string;
  /** `model_review_completed`: the full structured review report for the chapter. */
  model_review?: ChapterModelReview;
  step?: number;
  step_key?: string;
  step_label?: string;
  step_status?: string;
  elapsed_ms?: number;
  version_id?: string;
  proposal?: ChapterWritebackProposal;
  committed?: Array<Record<string, unknown>>;
  resolved?: Array<Record<string, unknown>>;
  pending_conflicts?: Array<Record<string, unknown>>;
  failure?: Record<string, unknown>;
  recovery_state?: {
    status?: 'closed' | 'degraded' | 'open';
    needs_recovery?: boolean;
    consecutive_failures?: number;
    max_consecutive_failures?: number;
    last_failure?: Record<string, unknown>;
    last_stable_checkpoint?: Record<string, unknown>;
  };
  budget_state?: Record<string, unknown>;
  scope_key?: string;
  used_tokens?: number;
  max_tokens?: number;
  checkpoint?: Record<string, unknown>;
  event_seq?: number;
  snapshot_id?: string;
  quality_mode?: QualityMode;
  source_stage_id?: string;
  tracks?: string[];
  parallel_delivery?: ParallelDeliveryState;
};

export type RunInputs = {
  title: string;
  theme: string;
  /** Phase 11.2: owning project id; empty for unarchived sessions (backend falls back to run_id). */
  project_id?: string;
  quality_mode: QualityMode;
  execution_mode?: 'live';
  run_intent?: {
    project_brief: Record<string, unknown>;
    knowledge_strategy: Record<string, unknown>;
    mode_policy: {
      quality_mode: QualityMode;
      control_mode: 'auto' | 'step' | 'info_step';
      checkpoint_stages: string[];
    };
    variant_strategy: Record<string, unknown>;
    export_preferences: Record<string, unknown>;
  };
  stage_configs: Record<string, Record<string, unknown>>;
};

export type KnowledgeCollectionState = {
  documents: KnowledgeDocument[];
};
