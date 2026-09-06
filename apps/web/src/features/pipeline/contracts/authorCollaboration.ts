import type { CreationRouteId } from "./run"

export type CollaborationStageId = "cast" | "beat_board" | "scene_deck" | "script" | "story_map" | "section_plan" | "text" | "book_architecture" | "volumes" | "rolling_detail"

export type CollaborationMode = "discuss" | "plan" | "revise"
export type CollaborationTurnStatus = "queued" | "streaming" | "completed" | "cancelled" | "failed" | "contract_rejected"

export type CollaborationContextPolicy = {
  policy_id: string
  version: number
  max_input_chars: number
  max_history_turns: number
  include_author_preferences: boolean
  include_craft_mechanisms: boolean
  include_knowledge: boolean
  include_canon_wiki: boolean
  include_foreshadow: boolean
  author_preferences: string
  craft_mechanisms: string[]
  source_pack_refs: string[]
}

export type CollaborationScope = {
  artifact_ref: string
  effective_payload_digest: string
  source_signature: string
  unit_ref: string
  field_path: string
  label: string
}

export type CollaborationProviderExecution = {
  provider_profile_id: string
  provider_template_id: string
  model_id: string
  model_settings: {
    model: string
    temperature: number
    max_tokens: number
    top_p: number
    timeout_seconds: number
  }
  provider_config: Record<string, unknown>
  provider_template: Record<string, unknown>
  provider_config_digest: string
  provider_template_digest: string
  pricing_snapshot: Record<string, unknown>
}

export type CollaborationThread = {
  architecture_version: "phase32-routes-v1"
  thread_id: string
  run_id: string
  project_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  stage_id: CollaborationStageId
  artifact_kind: string
  scope: CollaborationScope
  title: string
  provider_execution: CollaborationProviderExecution
  context_policy_id: string
  status: "active" | "archived" | "deleted"
  turn_count: number
  has_unapplied_patch: boolean
  created_at: string
  updated_at: string
}

export type SelectionAnchor = {
  anchor_id: string
  stage_id: CollaborationStageId
  source_ref: string
  unit_ref: string
  field_path: string
  field_hash: string
  selection_start: number
  selection_end: number
  selected_text_hash: string
  selected_char_count: number
  preview: string
  selected_text: string
  created_at: string
}

export type CollaborationPlan = {
  goal: string
  findings: string[]
  steps: string[]
  impacts: string[]
  risks: string[]
  questions: string[]
}

export type CollaborationMessage = {
  message_id: string
  thread_id: string
  turn_id: string
  role: "user" | "assistant"
  mode: CollaborationMode
  content: string
  status: "complete" | "partial" | "cancelled" | "failed"
  context_receipt_ref: string
  patch_candidate_ref: string
  plan: CollaborationPlan | null
  source_refs: string[]
  created_at: string
}

export type CollaborationTurn = {
  turn_id: string
  client_turn_id: string
  thread_id: string
  run_id: string
  mode: CollaborationMode
  status: CollaborationTurnStatus
  user_message_ref: string
  assistant_message_ref: string
  context_receipt_ref: string
  context_preview_signature: string
  provider_operation_ref: string
  patch_candidate_ref: string
  selection_anchor: SelectionAnchor | null
  error: {
    code?: string
    message?: string
  } | null
  created_at: string
  updated_at: string
}

export type ContextSourceReceipt = {
  category: "selection" | "artifact" | "upstream" | "knowledge" | "craft" | "author_preferences" | "history"
  source_ref: string
  scope_ref: string
  source_version: string
  reason: string
  char_count: number
  token_estimate: number
  disposition: "required" | "optional" | "omitted"
  label: string
}

export type CollaborationContextReceipt = {
  receipt_id: string
  thread_id: string
  turn_id: string
  run_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  stage_id: CollaborationStageId
  artifact_kind: string
  source_artifact_ref: string
  source_signature: string
  effective_payload_digest: string
  sources: ContextSourceReceipt[]
  history_message_refs: string[]
  budget_chars: number
  used_chars: number
  token_estimate: number
  provider_profile_id: string
  model: string
  receipt_hash: string
  created_at: string
}

export type ArtifactPatchOperation = {
  operation: "replace_text"
  field_path: string
  before_hash: string
  selection_anchor_id: string
  replacement: string
  rationale: string
}

export type ArtifactPatchCandidate = {
  patch_id: string
  thread_id: string
  turn_id: string
  run_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  stage_id: CollaborationStageId
  artifact_kind: string
  source_artifact_ref: string
  source_signature: string
  effective_payload_digest: string
  unit_ref: string
  operations: ArtifactPatchOperation[]
  context_receipt_ref: string
  provider_operation_ref: string
  status: "proposed" | "rejected" | "stale"
  created_at: string
  updated_at: string
}

export type CollaborationThreadDetail = {
  thread: CollaborationThread
  turns: CollaborationTurn[]
  messages: CollaborationMessage[]
  patches: ArtifactPatchCandidate[]
}

export type CollaborationStreamEvent = {
  sequence: number
  event_id: string
  thread_id: string
  turn_id: string
  type: "thread.created" | "thread.updated" | "turn.started" | "context.frozen" | "turn.streaming" | "turn.completed" | "turn.cancelled" | "turn.failed" | "patch.ready" | "patch.rejected" | "patch.stale"
  payload: Record<string, unknown>
  created_at: string
}

export type CollaborationProviderCapability = {
  provider_profile_id: string
  provider_name: string
  model: string
  supports_multi_turn: boolean
  supports_streaming: boolean
  supports_structured_patch: boolean
  max_context_tokens: number | null
  capability_checked_at: string
  capability_source: "discovered" | "tested" | "manual"
  ready: boolean
  issue_codes: string[]
}

export type CollaborationSettings = {
  default_mode: CollaborationMode
  default_provider_profile_id: string
  default_model: string
  context_policy: CollaborationContextPolicy
  history_retention_days: number
}

export type CollaborationSettingsEnvelope = {
  settings: CollaborationSettings
  capabilities: CollaborationProviderCapability[]
}

export type CreateCollaborationThreadInput = {
  stage_id: CollaborationStageId
  source_ref?: string
  unit_ref?: string
  field_path?: string
  label?: string
  title?: string
  context_policy?: CollaborationContextPolicy
}

export type CollaborationContextPreviewInput = {
  client_turn_id: string
  mode: CollaborationMode
  message: string
  context_policy?: CollaborationContextPolicy
  selection?: SelectionAnchor
}
