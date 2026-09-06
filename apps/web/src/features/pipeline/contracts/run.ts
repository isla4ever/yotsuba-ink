export type RunStatus = "created" | "running" | "awaiting_decision" | "image_deferred" | "needs_action" | "completed" | "failed" | "cancelled"

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

export type CreationRouteId = "screenplay_sample" | "short_novel" | "long_novel"

export type Phase32StageStatus = "locked" | "available" | "running" | "awaiting_decision" | "stale" | "completed" | "failed"

export type Phase32RouteStageManifest = {
  ordinal: number
  stage_id: string
  label: string
  artifact_kind: string
  workbench_kind: string
  provider_task_kind: string | null
  upstream_stage_ids: string[]
  downstream_stage_ids: string[]
  unitization: "aggregate" | "bounded_units" | "sequential_units" | "deterministic"
  decision_policy_ref: string
  context_policy_ref: string
  collaboration_enabled: boolean
}

export type FrozenContractPayload = {
  contract_id: string
  contract_revision: string
  payload: Record<string, unknown>
  payload_digest: string
}

export type Phase32RunDefinition = {
  architecture_version: "phase32-routes-v1"
  run_id: string
  project_id: string
  workflow_id: string
  workflow_revision: string
  workflow_digest: string
  route_contract: {
    architecture_version: "phase32-routes-v1"
    creation_route_id: CreationRouteId
    route_revision: string
    route_manifest: {
      route_id: CreationRouteId
      route_revision: string
      deliverable_kind: string
      start_stage_id: string
      terminal_stage_id: "export"
      stages: Phase32RouteStageManifest[]
      capabilities: string[]
      export_profiles: string[]
    }
    route_manifest_digest: string
  }
  scale_profile: FrozenContractPayload
  inputs: FrozenContractPayload
  provider_bindings_by_stage: Array<{
    stage_id: string
    binding: FrozenContractPayload
  }>
  export_profile: string
  created_at: string
  definition_digest: string
}

export type Phase32ProviderUsageSummary = ProviderUsageSummary & {
  estimated_cost_usd: number | null
  cost_status: "known" | "unknown" | "unavailable"
  balance_status: "unknown" | "available" | "insufficient" | "unavailable"
  by_provider: Array<{
    provider_profile_id: string
    provider_template_id: string
    model_id: string
    operations: number
    estimated_cost_usd: number | null
    cost_status: "known" | "unknown" | "unavailable"
    balance_status: "unknown" | "available" | "insufficient" | "unavailable"
  }>
}

export type Phase32DecisionAction = "accept" | "regenerate" | "retry_writeback" | "cancel"

export type Phase32PendingDecision = {
  decision_id: string
  stage_id: string
  unit_ref: string
  artifact_ref: string
  kind: string
  domain_revision: number | null
  allowed_actions: Phase32DecisionAction[]
  redraft_limit: number | null
  redraft_used: number | null
}

export type Phase32CurrentArtifact = {
  run_id: string
  creation_route_id: CreationRouteId
  stage_id: string
  artifact_kind: string
  artifact_ref: string
  unit_ref: string
  status: "candidate" | "committed"
  payload: Record<string, unknown>
  payload_digest: string
  editable: boolean
  pending_decision: Phase32PendingDecision | null
}

export type Phase32ArtifactDraft = {
  architecture_version: "phase32-routes-v1"
  draft_ref: string
  run_id: string
  decision_id: string
  domain_revision: number
  creation_route_id: CreationRouteId
  stage_id: string
  source_artifact_ref: string
  payload: Record<string, unknown>
  payload_digest: string
  created_at: string
}

export type Phase32RunReadModel = {
  run_id: string
  project_id: string
  thread_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  route_manifest_digest: string
  definition_digest: string
  stage_manifest: Phase32RouteStageManifest[]
  review_policy_summary: {
    policy_id: string
    revision: string
    checkpoint_policy: string
    warning_policy: string
    auto_continue_stages: string[]
    mandatory_decision_stages: string[]
  }
  status: RunStatus
  active_stage_id: string
  active_unit_ref: string
  stage_status: Record<string, Phase32StageStatus>
  artifact_refs: Record<string, {
    artifact_kind: string
    artifact_ref: string
  }>
  sequential_stage_progress: Record<string, {
    ordered_unit_refs: string[]
    committed_artifact_refs: Record<string, string>
  }>
  pending_decisions: Phase32PendingDecision[]
  active_amendment_id: string
  stale_stage_ids: string[]
  historical_frozen_stage_ids: string[]
  provider_usage: Phase32ProviderUsageSummary
  failure: {
    code: string
    stage_id: string
    unit_ref: string
    retryable: boolean
    message: string
  } | null
  checkpoint_id: string
  updated_at: string
}

export type Phase32RunSummary = {
  run_id: string
  project_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  route_label: string
  deliverable_kind: string
  status: RunStatus
  active_stage: {
    stage_id: string
    label: string
    ordinal: number
    total: number
  }
  completed_stage_ids: string[]
  progress: {
    completed: number
    total: number
    ratio: number
  }
  active_unit_ref: string
  pending_decisions: Phase32PendingDecision[]
  provider_usage: Phase32ProviderUsageSummary
  failure: Phase32RunReadModel["failure"]
  checkpoint_id: string
  can_branch: boolean
  export_ready: boolean
  created_at: string
  updated_at: string
}

export type Phase32RunEnvelope = {
  definition: Phase32RunDefinition
  read_model: Phase32RunReadModel
  summary: Phase32RunSummary
}

export type Phase32RunEvent = {
  event_id: string
  sequence: number
  occurred_at: string
  run_id: string
  thread_id: string
  creation_route_id: CreationRouteId
  route_revision: string
  route_manifest_digest: string
  definition_digest: string
  type: string
  stage_id: string
  unit_ref: string
  artifact_kind: string | null
  node_id: string
  status: string
  payload: Record<string, unknown> | null
  payload_ref: string
  checkpoint_id: string
}
