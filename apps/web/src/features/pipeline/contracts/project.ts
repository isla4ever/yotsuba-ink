import type { RunHistoryItem } from './runHistory';

export type ProjectStatus = 'active' | 'archived';

/** Mirrors backend `storage/project_schemas.py::ProjectRecord`. */
export type ProjectRecord = {
  id: string;
  title: string;
  summary: string;
  /** 0-360, allocated by the backend accent palette sequence. */
  accent_hue: number;
  workflow_id: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  latest_run_id: string;
};

/** Mirrors `GET /api/projects/{id}/summary` (aggregated from run history). */
export type ProjectSummary = {
  project: ProjectRecord;
  latest_run: RunHistoryItem | null;
  title: string;
  status: string;
  current_stage: { id?: string; label?: string; type?: string };
  completed_stage_ids: string[];
  words: number;
  updated_at: string;
};
