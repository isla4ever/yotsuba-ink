import type { QualityMode, StageType } from './workflow';

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
