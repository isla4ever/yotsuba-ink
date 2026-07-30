import type { QualityMode, StageType } from './workflow';

export type ExportFormat = 'md' | 'json' | 'zip';

export type ExportMetadata = {
  author: string;
  bundle_name: string;
  title: string;
  version_note: string;
};

export type ExportCoverAsset = {
  candidate_id: string;
  asset_id: string;
  sha256: string;
  mime_type: string;
  width: number;
  height: number;
  size_bytes: number;
  image_url: string;
};

export type ExportReceiptFile = {
  path: string;
  scope: 'package' | 'archive';
  media_type: string;
  size_bytes: number;
  sha256: string;
};

export type ExportSelectionReceipt = {
  schema_version: number;
  format: ExportFormat;
  chapter_ids: string[];
  chapters: Array<{ id: string; title: string; words: number; content_sha256: string }>;
  metadata: ExportMetadata;
  cover_asset: ExportCoverAsset;
  validation: Record<string, string>;
  source_artifact_digests: Record<string, string>;
  quality_digest: string;
  canon_digest: string;
};

export type RunHistoryStatus =
  | 'created'
  | 'running'
  | 'paused'
  | 'awaiting_confirmation'
  | 'recovery_required'
  | 'failed'
  | 'completed';

export type ExportReceipt = {
  export_id: string;
  run_id: string;
  request_id: string;
  schema_version: number;
  version: number;
  snapshot_id: string;
  artifact_signature: string;
  selection_digest: string;
  selection_snapshot: ExportSelectionReceipt | null;
  source_state_revision?: number;
  source_state_digest?: string;
  format: ExportFormat;
  chapter_ids: string[];
  metadata: ExportMetadata;
  filename: string;
  size_bytes: number;
  sha256: string;
  files: ExportReceiptFile[];
  cover_asset: ExportCoverAsset | null;
  created_at: string;
};

export type RunHistoryItem = {
  run_id: string;
  project_id: string;
  title: string;
  quality_mode: QualityMode;
  status: RunHistoryStatus;
  current_stage: {
    id: string;
    label: string;
    type: StageType | '';
  };
  completed_stage_ids: string[];
  created_at: string;
  updated_at: string;
  completed_at: string;
  words: number;
  total_tokens: number;
  estimated_cost_usd: number;
  summary: string;
  can_resume: boolean;
  recovery_required: boolean;
  latest_snapshot_id: string;
  export_ready: boolean;
  export_count: number;
  latest_export: ExportReceipt | null;
  state_revision: number;
  source?: 'server' | 'local';
};

export type RunSnapshotItem = {
  snapshot_id: string;
  schema_version: number;
  kind: 'stable_checkpoint' | 'run_state';
  restorable: boolean;
  state_revision: number;
  event_seq: number;
  event_type: string;
  created_at: string;
  node_id: string;
  node_type: StageType | '';
  stage_label: string;
  phase: string;
  current_checkpoint_stage_id: string;
  pending_export_return: boolean;
  state_digest: string;
  artifact_digests: Record<string, string>;
};

export type RunHistoryResponse = {
  items: RunHistoryItem[];
  next_cursor: string;
};

export type RunSnapshotsResponse = {
  run_id: string;
  state_revision: number;
  items: RunSnapshotItem[];
  latest_restorable_snapshot_id: string;
};
