import type { QualityMode } from "./workflow"

export type ExportFormat = "md" | "json" | "zip"

export type ExportReceipt = {
  export_id: string
  run_id: string
  artifact_id: string
  artifact_signature: string
  format: ExportFormat
  chapter_version_ids: string[]
  cover_asset_id: string
  metadata: { author: string; title: string; version_note: string }
  filename: string
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export type RunHistoryStatus = "created" | "running" | "awaiting_decision" | "failed" | "completed" | "cancelled"

export type RunHistoryItem = {
  run_id: string
  project_id: string
  title: string
  quality_mode: QualityMode
  status: RunHistoryStatus
  current_stage: { id: string; label: string; type: string }
  completed_stage_ids: string[]
  created_at: string
  updated_at: string
  completed_at: string
  words: number
  total_tokens: number
  estimated_cost_usd: number | null
  summary: string
  can_branch: boolean
  checkpoint_id: string
  export_ready: boolean
  export_count: number
  latest_export: ExportReceipt | null
}

export type RunHistoryResponse = { items: RunHistoryItem[]; next_cursor: string }
