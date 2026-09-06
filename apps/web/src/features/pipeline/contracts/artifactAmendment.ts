import type { CreationRouteId, Phase32RunEnvelope } from "./run"

export type AmendmentApplyScope = "affected_only" | "restart_from_stage"

export type AmendmentImpactTarget = {
  stage_id: string
  artifact_kind: string
  artifact_ref: string
  unit_ref: string
  reason: string
}

export type AmendmentBlockedReference = {
  reference: string
  referenced_stage_id: string
  referenced_artifact_ref: string
  unit_ref: string
}

export type ArtifactImpactAnalysis = {
  architecture_version: "phase32-routes-v1"
  impact_id: string
  amendment_id: string
  run_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  definition_digest: string
  source_stage_id: string
  source_artifact_ref: string
  source_payload_digest: string
  proposed_payload_digest: string
  source_domain_revision: number
  preserved: AmendmentImpactTarget[]
  stale: AmendmentImpactTarget[]
  historical_frozen: AmendmentImpactTarget[]
  blocked_references: AmendmentBlockedReference[]
  affected_only_scope: string[]
  restart_from_stage_scope: string[]
  impact_digest: string
}

export type ArtifactAmendment = {
  architecture_version: "phase32-routes-v1"
  amendment_id: string
  command_digest: string
  idempotency_key_digest: string
  run_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  definition_digest: string
  source_stage_id: string
  artifact_kind: string
  source_artifact_ref: string
  source_payload_digest: string
  source_domain_revision: number
  proposed_payload: Record<string, unknown>
  proposed_payload_digest: string
  impact_id: string
  author_note: string
  created_at: string
}

export type AmendmentApplyReceipt = {
  architecture_version: "phase32-routes-v1"
  receipt_id: string
  plan_id: string
  run_id: string
  amendment_id: string
  scope: AmendmentApplyScope
  previous_artifact_ref: string
  committed_artifact_ref: string
  domain_revision_before: number
  domain_revision_after: number
  event_id: string
  applied_at: string
}

export type AmendmentBranchReceipt = {
  architecture_version: "phase32-routes-v1"
  receipt_id: string
  plan_id: string
  source_run_id: string
  target_run_id: string
  project_id: string
  amendment_id: string
  apply_receipt_id: string
  source_domain_revision: number
  target_definition_digest: string
  frontier_stage_id: string
  imported_artifact_refs: Record<string, string>
  source_event_id: string
  target_event_id: string
  branched_at: string
}

export type AmendmentCreateResponse = {
  reused: boolean
  amendment: ArtifactAmendment
  impact: ArtifactImpactAnalysis
}

export type AmendmentApplyResponse = {
  reused: boolean
  receipt: AmendmentApplyReceipt
  run: Phase32RunEnvelope
}

export type AmendmentBranchStatusResponse = {
  apply_receipt: AmendmentApplyReceipt | null
  receipt: AmendmentBranchReceipt | null
  target_run: Phase32RunEnvelope | null
}

export type AmendmentBranchResponse = AmendmentBranchStatusResponse & {
  reused: boolean
  source_run: Phase32RunEnvelope
  receipt: AmendmentBranchReceipt
  target_run: Phase32RunEnvelope
}
