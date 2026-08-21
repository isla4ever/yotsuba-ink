import type { QualityMode } from "./workflow"

export type NarrativeStageId = "brief" | "spine" | "cast" | "volumes" | "detail" | "text" | "cover" | "export"
export type ProviderStageId = Exclude<NarrativeStageId, "export">
export type GraphRunStatus = "created" | "running" | "awaiting_decision" | "completed" | "failed" | "cancelled"
export type GraphStageStatus = "locked" | "available" | "running" | "awaiting_decision" | "completed" | "failed"

export type FrozenProviderBinding = {
  provider_profile_id: string
  model: string
  temperature: number
  max_tokens: number
  timeout_seconds: number
}

export type FrozenCoverAssetBinding = {
  provider_profile_id: string
  model: string
  candidate_count: number
  size: string
  quality: "low" | "medium" | "high"
  timeout_seconds: number
  failure_policy: "fail_run"
}

export type FrozenExportPreferences = {
  format: "md" | "json" | "zip"
  author: string
  version_note: string
  include_cover_image: boolean
}

export type GraphRunDefinition = {
  architecture_version: "phase27-vnext"
  run_id: string
  project_id: string
  workflow_id: string
  workflow_revision: string
  quality_mode: QualityMode
  inputs: Record<string, unknown>
  provider_bindings: Record<ProviderStageId, FrozenProviderBinding>
  cover_asset_binding: FrozenCoverAssetBinding
  export_preferences: FrozenExportPreferences
  created_at: string
}

export type ProviderUsageSummary = {
  provider_operations: number
  returned_operations: number
  succeeded_operations: number
  contract_rejected_operations: number
  failed_operations: number
  pending_operations: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  reasoning_tokens: number
}

export type GraphRunReadModel = {
  run_id: string
  project_id: string
  thread_id: string
  status: GraphRunStatus
  active_stage_id: NarrativeStageId
  active_chapter_number: number
  context_manifest_ref: string
  stage_status: Record<NarrativeStageId, GraphStageStatus>
  artifact_refs: Partial<Record<NarrativeStageId, string>>
  pending_decisions: Array<Record<string, unknown>>
  provider_usage: ProviderUsageSummary
  failure: Record<string, unknown> | null
  checkpoint_id: string
  updated_at: string
}

export type GraphRunEnvelope = {
  definition: GraphRunDefinition
  read_model: GraphRunReadModel
}

export type RunEvent = {
  event_id: string
  sequence: number
  occurred_at: string
  run_id: string
  thread_id: string
  type: string
  stage_id: NarrativeStageId | null
  node_id: string
  chapter_id: string
  status: string
  payload: Record<string, unknown> | null
  payload_ref: string
  checkpoint_id: string
}

export type RunArtifactRecord = {
  artifact_id: string
  run_id: string
  stage_id: NarrativeStageId
  status: "candidate" | "committed" | "rejected"
  payload: Record<string, unknown>
  signature: string
  created_at: string
  source: string
}

export type ChapterVersionRecord = {
  run_id: string
  chapter_id: string
  version_id: string
  artifact: {
    chapter_id: string
    version_id: string
    title: string
    content: string
    author_status: string
    [key: string]: unknown
  }
  signature: string
  created_at: string
}

export type StageArtifactDraftRecord = {
  run_id: string
  decision_id: string
  domain_revision: number
  source_artifact_id: string
  payload: Record<string, unknown>
  signature: string
  updated_at: string
}
