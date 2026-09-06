import type { RunStatus, Phase32RunSummary } from "./run"

export type ExportFormat = "md" | "json" | "zip"

export type ExportReceipt = {
  export_id: string
  run_id: string
  artifact_id: string
  artifact_signature: string
  format: ExportFormat
  chapter_version_ids: string[]
  cover_asset_id: string
  metadata: {
    author: string
    title: string
    version_note: string
  }
  filename: string
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export type RunHistoryStatus = RunStatus

export type RunHistoryItem = Phase32RunSummary

export type RunHistoryResponse = {
  items: RunHistoryItem[]
  next_cursor: string
}
