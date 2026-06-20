import type { KnowledgeDocument } from './knowledge';
import type { QualityEvent, QualityFinding, QualityReport, RevisionDirective } from './quality';
import type { QualityMode, StageType } from './workflow';

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

export type RunInputs = {
  title: string;
  theme: string;
  quality_mode: QualityMode;
  stage_configs: Record<string, Record<string, unknown>>;
};

export type KnowledgeCollectionState = {
  documents: KnowledgeDocument[];
};
