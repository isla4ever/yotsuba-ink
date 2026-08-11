import type { KnowledgeDocument } from './knowledge';
import type { BookScalePlan, BookScaleTarget } from './bookScale';
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

export type NarrativeStageId = 'info' | 'characters' | 'summary' | 'outline' | 'detail' | 'text' | 'cover' | 'export';

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

export type GraphRunDefinition = {
  architecture_version: 'phase26-vnext';
  run_id: string;
  project_id: string;
  workflow_revision: string;
  quality_mode: QualityMode;
  inputs: Record<string, unknown>;
  book_scale_plan: BookScalePlan;
  provider_bindings: Partial<Record<NarrativeStageId, {
    provider_profile_id: string;
    model: string;
    temperature: number;
    max_tokens: number;
    top_p: number;
    timeout_seconds: number;
    prompt_template: string;
  }>>;
  cover_asset_binding: {
    provider_profile_id: string;
    model: string;
    candidate_count: number;
    size: string;
    quality: 'low' | 'medium' | 'high';
    timeout_seconds: number;
    failure_policy: 'fail_run';
  };
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
};

export type GraphRunReadModel = {
  run_id: string;
  project_id: string;
  thread_id: string;
  status: GraphRunStatus;
  active_stage_id: NarrativeStageId;
  active_chapter_number: number;
  stage_status: Record<NarrativeStageId, GraphStageStatus>;
  artifact_refs: Partial<Record<NarrativeStageId, string>>;
  pending_decisions: Array<Record<string, unknown>>;
  provider_usage: ProviderUsageSummary;
  failure: Record<string, unknown> | null;
  checkpoint_id: string;
  updated_at: string;
};

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

export type RunStartInputs = RunInputBase & {
  book_scale_target: BookScaleTarget;
  book_scale_plan?: never;
};

export type FrozenRunInputs = RunInputBase & {
  book_scale_plan: BookScalePlan;
  book_scale_target?: never;
};

export type RunInputs = RunStartInputs | FrozenRunInputs;

export type KnowledgeCollectionState = {
  documents: KnowledgeDocument[];
};
