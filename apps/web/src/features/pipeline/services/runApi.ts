import type {
  Phase32ArtifactDraft,
  Phase32CurrentArtifact,
  Phase32DecisionAction,
  Phase32PendingDecision,
  Phase32RouteStageManifest,
  Phase32RunEnvelope,
} from "../contracts/run"

export class RunApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message)
    this.name = "RunApiError"
  }
}

export async function getRun(
  runId: string,
  signal?: AbortSignal,
): Promise<Phase32RunEnvelope> {
  const url = `/api/runs/${encodeURIComponent(runId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  return parseRunEnvelope(await response.json(), url)
}

export function streamRunEvents(
  runId: string,
  signal?: AbortSignal,
  after = 0,
) {
  return fetch(`/api/runs/${encodeURIComponent(runId)}/events?after=${after}`, {
    method: "GET",
    signal,
  })
}

export async function startRun(runId: string): Promise<Phase32RunEnvelope> {
  const url = `/api/runs/${encodeURIComponent(runId)}/start`
  const response = await fetch(url, { method: "POST" })
  if (!response.ok) throw await responseError(response, url)
  const result: unknown = await response.json()
  if (!isRecord(result)) throw invalidRunContract(url)
  return parseRunEnvelope(result.run, url)
}

export async function resolvePhase32RunDecision(
  runId: string,
  command: {
    decisionId: string
    action: Phase32DecisionAction
    domainRevision: number
    direction?: string
    draftRef?: string
  },
): Promise<Phase32RunEnvelope> {
  const url = `/api/runs/${encodeURIComponent(runId)}/decisions`
  const payload: Record<string, unknown> = {
    decision_id: command.decisionId,
    action: command.action,
    domain_revision: command.domainRevision,
    direction: command.direction?.trim() ?? "",
  }
  if (command.draftRef?.trim()) payload.draft_ref = command.draftRef.trim()
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw await responseError(response, url)
  const result: unknown = await response.json()
  if (!isRecord(result)) throw invalidRunContract(url)
  return parseRunEnvelope(result.run, url)
}

export async function getPhase32CurrentArtifact(
  runId: string,
  stageId: string,
  signal?: AbortSignal,
  unitRef = "",
): Promise<Phase32CurrentArtifact> {
  const query = unitRef ? `?unit_ref=${encodeURIComponent(unitRef)}` : ""
  const url = `/api/runs/${encodeURIComponent(runId)}/stages/${encodeURIComponent(stageId)}/artifacts/current${query}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (!isPhase32CurrentArtifact(value))
    throw new RunApiError(`Artifact 接口返回了无法识别的数据：${url}`, 502)
  return value
}

export async function getPhase32ArtifactDraft(
  runId: string,
  decisionId: string,
  signal?: AbortSignal,
): Promise<Phase32ArtifactDraft | null> {
  const url = `/api/runs/${encodeURIComponent(runId)}/stage-drafts/${encodeURIComponent(decisionId)}`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (
    !isRecord(value) ||
    !(value.draft === null || isPhase32ArtifactDraft(value.draft))
  )
    throw new RunApiError(`草稿接口返回了无法识别的数据：${url}`, 502)
  return value.draft
}

export async function savePhase32ArtifactDraft(
  runId: string,
  decisionId: string,
  domainRevision: number,
  sourceArtifactRef: string,
  payload: Record<string, unknown>,
): Promise<Phase32ArtifactDraft> {
  const url = `/api/runs/${encodeURIComponent(runId)}/stage-drafts/${encodeURIComponent(decisionId)}`
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      domain_revision: domainRevision,
      source_artifact_ref: sourceArtifactRef,
      payload,
    }),
  })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (!isRecord(value) || !isPhase32ArtifactDraft(value.draft))
    throw new RunApiError(`草稿接口返回了无法识别的数据：${url}`, 502)
  return value.draft
}

export function parseRunEnvelope(
  value: unknown,
  url: string,
): Phase32RunEnvelope {
  if (!isRecord(value)) throw invalidRunContract(url)
  const definition = value.definition
  const readModel = value.read_model
  const summary = value.summary
  if (
    !isRecord(definition) ||
    definition.architecture_version !== "phase32-routes-v1" ||
    !requiredStrings(definition, [
      "run_id",
      "project_id",
      "workflow_id",
      "workflow_revision",
      "workflow_digest",
      "export_profile",
      "created_at",
      "definition_digest",
    ]) ||
    !isRecord(definition.route_contract) ||
    !isCreationRouteId(definition.route_contract.creation_route_id) ||
    !requiredStrings(definition.route_contract, [
      "route_revision",
      "route_manifest_digest",
    ]) ||
    !isRecord(definition.route_contract.route_manifest) ||
    !Array.isArray(definition.route_contract.route_manifest.stages) ||
    !isRecord(readModel) ||
    !isRecord(summary)
  )
    throw invalidRunContract(url)
  const manifest = definition.route_contract.route_manifest.stages
  if (!manifest.every(isRouteStageManifest)) throw invalidRunContract(url)
  const stageIds = manifest.map((stage) => stage.stage_id)
  if (stageIds.length === 0 || new Set(stageIds).size !== stageIds.length)
    throw invalidRunContract(url)
  if (
    !requiredStrings(readModel, [
      "run_id",
      "project_id",
      "thread_id",
      "route_revision",
      "route_manifest_digest",
      "definition_digest",
      "active_stage_id",
      "active_unit_ref",
      "active_amendment_id",
      "checkpoint_id",
      "updated_at",
    ]) ||
    readModel.run_id !== definition.run_id ||
    readModel.project_id !== definition.project_id ||
    readModel.thread_id !== definition.run_id ||
    readModel.definition_digest !== definition.definition_digest ||
    readModel.creation_route_id !==
      definition.route_contract.creation_route_id ||
    readModel.route_revision !== definition.route_contract.route_revision ||
    readModel.route_manifest_digest !==
      definition.route_contract.route_manifest_digest ||
    !isRunStatus(readModel.status) ||
    !stageIds.includes(String(readModel.active_stage_id)) ||
    !Array.isArray(readModel.stage_manifest) ||
    !readModel.stage_manifest.every(isRouteStageManifest) ||
    readModel.stage_manifest.map((stage) => stage.stage_id).join("|") !==
      stageIds.join("|") ||
    !isStageStatusMap(readModel.stage_status, stageIds) ||
    !isRecord(readModel.artifact_refs) ||
    !isSequentialStageProgressMap(readModel.sequential_stage_progress) ||
    !Array.isArray(readModel.pending_decisions) ||
    !readModel.pending_decisions.every(isPhase32PendingDecision) ||
    !isAmendmentProjection(readModel, stageIds) ||
    !isProviderUsage(readModel.provider_usage) ||
    summary.run_id !== definition.run_id ||
    summary.project_id !== definition.project_id ||
    summary.status !== readModel.status ||
    !isRecord(summary.active_stage)
  )
    throw invalidRunContract(url)
  return value as Phase32RunEnvelope
}

function invalidRunContract(url: string) {
  return new RunApiError(`Run 接口返回了无法识别的数据：${url}`, 502)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function requiredStrings(value: Record<string, unknown>, fields: string[]) {
  return fields.every((field) => typeof value[field] === "string")
}

function isCreationRouteId(value: unknown) {
  return ["screenplay_sample", "short_novel", "long_novel"].includes(
    String(value),
  )
}

function isRunStatus(value: unknown) {
  return [
    "created",
    "running",
    "awaiting_decision",
    "image_deferred",
    "needs_action",
    "completed",
    "failed",
    "cancelled",
  ].includes(String(value))
}

function isRouteStageManifest(
  value: unknown,
): value is Phase32RouteStageManifest {
  if (!isRecord(value)) return false
  return (
    Number.isInteger(value.ordinal) &&
    requiredStrings(value, [
      "stage_id",
      "label",
      "artifact_kind",
      "workbench_kind",
      "unitization",
      "decision_policy_ref",
      "context_policy_ref",
    ]) &&
    (value.provider_task_kind === null ||
      typeof value.provider_task_kind === "string") &&
    Array.isArray(value.upstream_stage_ids) &&
    Array.isArray(value.downstream_stage_ids) &&
    typeof value.collaboration_enabled === "boolean"
  )
}

function isStageStatusMap(value: unknown, stageIds: string[]) {
  if (!isRecord(value) || Object.keys(value).length !== stageIds.length)
    return false
  return stageIds.every((stageId) =>
    [
      "locked",
      "available",
      "running",
      "awaiting_decision",
      "stale",
      "completed",
      "failed",
    ].includes(String(value[stageId])),
  )
}

function isStageIdList(value: unknown, stageIds: string[]): value is string[] {
  return (
    Array.isArray(value) &&
    value.every(
      (stageId) => typeof stageId === "string" && stageIds.includes(stageId),
    ) &&
    new Set(value).size === value.length
  )
}

function isAmendmentProjection(
  readModel: Record<string, unknown>,
  stageIds: string[],
) {
  const activeAmendmentId = readModel.active_amendment_id
  const staleStageIds = readModel.stale_stage_ids
  const historicalFrozenStageIds = readModel.historical_frozen_stage_ids
  const stageStatus = readModel.stage_status
  if (
    typeof activeAmendmentId !== "string" ||
    !isStageIdList(staleStageIds, stageIds) ||
    !isStageIdList(historicalFrozenStageIds, stageIds) ||
    !isRecord(stageStatus)
  )
    return false
  if (
    !historicalFrozenStageIds.every((stageId) =>
      staleStageIds.includes(stageId),
    ) ||
    !staleStageIds.every((stageId) => stageStatus[stageId] === "stale")
  )
    return false
  if (staleStageIds.length > 0 && readModel.status !== "needs_action")
    return false
  return !(
    readModel.status === "needs_action" &&
    (!activeAmendmentId || staleStageIds.length === 0)
  )
}

function isProviderUsage(value: unknown) {
  if (!isRecord(value)) return false
  return [
    "provider_operations",
    "returned_operations",
    "succeeded_operations",
    "contract_rejected_operations",
    "failed_operations",
    "pending_operations",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "reasoning_tokens",
  ].every((field) => Number.isFinite(value[field]))
}

function isNonNegativeInteger(value: unknown) {
  return Number.isInteger(value) && Number(value) >= 0
}

function isSequentialStageProgressMap(value: unknown) {
  if (!isRecord(value)) return false
  return Object.values(value).every(
    (progress) =>
      isRecord(progress) &&
      Array.isArray(progress.ordered_unit_refs) &&
      progress.ordered_unit_refs.every((ref) => typeof ref === "string") &&
      isRecord(progress.committed_artifact_refs) &&
      Object.values(progress.committed_artifact_refs).every(
        (ref) => typeof ref === "string",
      ),
  )
}

function isPhase32PendingDecision(
  value: unknown,
): value is Phase32PendingDecision {
  if (
    !isRecord(value) ||
    !requiredStrings(value, [
      "decision_id",
      "stage_id",
      "unit_ref",
      "artifact_ref",
      "kind",
    ]) ||
    !Array.isArray(value.allowed_actions)
  )
    return false
  const authorityMissing =
    value.domain_revision === null &&
    value.redraft_limit === null &&
    value.redraft_used === null &&
    value.allowed_actions.length === 0
  if (authorityMissing) return true
  const actions = value.allowed_actions.map(String)
  const actionsAreUnique = new Set(actions).size === actions.length
  if (value.kind === "writeback_recovery") {
    return (
      isNonNegativeInteger(value.domain_revision) &&
      value.redraft_limit === null &&
      value.redraft_used === null &&
      actionsAreUnique &&
      actions.length === 2 &&
      actions.includes("retry_writeback") &&
      actions.includes("cancel")
    )
  }
  return (
    isNonNegativeInteger(value.domain_revision) &&
    isNonNegativeInteger(value.redraft_limit) &&
    isNonNegativeInteger(value.redraft_used) &&
    Number(value.redraft_used) <= Number(value.redraft_limit) &&
    actionsAreUnique &&
    actions.length > 0 &&
    actions.every((action) =>
      ["accept", "regenerate", "retry_writeback", "cancel"].includes(action),
    ) &&
    actions.includes("accept") &&
    actions.includes("cancel")
  )
}

function isPhase32CurrentArtifact(
  value: unknown,
): value is Phase32CurrentArtifact {
  if (
    !isRecord(value) ||
    !isCreationRouteId(value.creation_route_id) ||
    !requiredStrings(value, [
      "run_id",
      "stage_id",
      "artifact_kind",
      "artifact_ref",
      "unit_ref",
      "status",
      "payload_digest",
    ]) ||
    !["candidate", "committed"].includes(String(value.status)) ||
    !isRecord(value.payload) ||
    typeof value.editable !== "boolean" ||
    !(
      value.pending_decision === null ||
      isPhase32PendingDecision(value.pending_decision)
    )
  )
    return false
  if (
    value.pending_decision?.kind === "writeback_recovery" &&
    (value.status !== "committed" || value.editable)
  )
    return false
  return true
}

function isPhase32ArtifactDraft(value: unknown): value is Phase32ArtifactDraft {
  return (
    isRecord(value) &&
    value.architecture_version === "phase32-routes-v1" &&
    isCreationRouteId(value.creation_route_id) &&
    requiredStrings(value, [
      "draft_ref",
      "run_id",
      "decision_id",
      "stage_id",
      "source_artifact_ref",
      "payload_digest",
      "created_at",
    ]) &&
    Number.isInteger(value.domain_revision) &&
    isRecord(value.payload)
  )
}

async function responseError(response: Response, url: string) {
  let detail = ""
  let code: string | undefined
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === "string") detail = payload.detail
    else if (payload.detail && typeof payload.detail === "object") {
      const structured = payload.detail as {
        code?: unknown
        message?: unknown
      }
      code = typeof structured.code === "string" ? structured.code : undefined
      detail = typeof structured.message === "string" ? structured.message : ""
    }
  } catch {
    detail = ""
  }
  return new RunApiError(
    detail || `Run 请求失败：${url} (${response.status})`,
    response.status,
    code,
  )
}
