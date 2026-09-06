import type {
  AmendmentApplyReceipt,
  AmendmentApplyResponse,
  AmendmentApplyScope,
  AmendmentBranchReceipt,
  AmendmentBranchResponse,
  AmendmentBranchStatusResponse,
  AmendmentCreateResponse,
  AmendmentImpactTarget,
  ArtifactAmendment,
  ArtifactImpactAnalysis,
} from "../contracts/artifactAmendment"
import { parseRunEnvelope, RunApiError } from "./runApi"

type ApplyArtifactAmendmentCommand = {
  scope: AmendmentApplyScope
  idempotencyKey: string
}

export async function createArtifactAmendment(
  runId: string,
  stageId: string,
  command: {
    sourceArtifactRef: string
    proposedPayload: Record<string, unknown>
    idempotencyKey: string
    authorNote: string
  },
): Promise<AmendmentCreateResponse> {
  const url = amendmentCollectionUrl(runId, stageId)
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_artifact_ref: command.sourceArtifactRef,
      proposed_payload: command.proposedPayload,
      idempotency_key: command.idempotencyKey,
      author_note: command.authorNote.trim(),
    }),
  })
  if (!response.ok) throw await responseError(response, url)
  return parseCreateResponse(await response.json(), url)
}

export async function getArtifactAmendmentImpact(
  runId: string,
  amendmentId: string,
  signal?: AbortSignal,
): Promise<ArtifactImpactAnalysis> {
  const url = `${amendmentUrl(runId, amendmentId)}/impact`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (!isRecord(value) || !isImpact(value.impact)) throw invalidContract(url)
  return value.impact
}

export async function applyArtifactAmendment(
  runId: string,
  amendmentId: string,
  command: ApplyArtifactAmendmentCommand,
): Promise<AmendmentApplyResponse> {
  const url = `${amendmentUrl(runId, amendmentId)}/apply`
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scope: command.scope,
      idempotency_key: command.idempotencyKey,
    }),
  })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (
    !isRecord(value) ||
    typeof value.reused !== "boolean" ||
    !isApplyReceipt(value.receipt)
  )
    throw invalidContract(url)
  return {
    reused: value.reused,
    receipt: value.receipt,
    run: parseRunEnvelope(value.run, url),
  }
}

export async function getArtifactAmendmentBranch(
  runId: string,
  amendmentId: string,
  signal?: AbortSignal,
): Promise<AmendmentBranchStatusResponse> {
  const url = `${amendmentUrl(runId, amendmentId)}/branch`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  return parseBranchStatus(await response.json(), url)
}

export async function createArtifactAmendmentBranch(
  runId: string,
  amendmentId: string,
  command: {
    applyReceiptId: string
    sourceDomainRevision: number
    idempotencyKey: string
  },
): Promise<AmendmentBranchResponse> {
  const url = `${amendmentUrl(runId, amendmentId)}/branch`
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      apply_receipt_id: command.applyReceiptId,
      source_domain_revision: command.sourceDomainRevision,
      idempotency_key: command.idempotencyKey,
    }),
  })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (
    !isRecord(value) ||
    typeof value.reused !== "boolean" ||
    !isBranchReceipt(value.receipt)
  )
    throw invalidContract(url)
  const sourceRun = parseRunEnvelope(value.source_run, url)
  const targetRun = parseRunEnvelope(value.target_run, url)
  if (
    value.receipt.source_run_id !== sourceRun.definition.run_id ||
    value.receipt.target_run_id !== targetRun.definition.run_id
  )
    throw invalidContract(url)
  return {
    reused: value.reused,
    apply_receipt: null,
    receipt: value.receipt,
    source_run: sourceRun,
    target_run: targetRun,
  }
}

export function parseCreateResponse(
  value: unknown,
  url: string,
): AmendmentCreateResponse {
  if (
    !isRecord(value) ||
    typeof value.reused !== "boolean" ||
    !isAmendment(value.amendment) ||
    !isImpact(value.impact) ||
    value.amendment.impact_id !== value.impact.impact_id ||
    value.amendment.amendment_id !== value.impact.amendment_id
  )
    throw invalidContract(url)
  return value as AmendmentCreateResponse
}

export function parseBranchStatus(
  value: unknown,
  url: string,
): AmendmentBranchStatusResponse {
  if (
    !isRecord(value) ||
    !(value.apply_receipt === null || isApplyReceipt(value.apply_receipt)) ||
    !(value.receipt === null || isBranchReceipt(value.receipt)) ||
    !(value.target_run === null || isRecord(value.target_run))
  )
    throw invalidContract(url)
  const targetRun = value.target_run
    ? parseRunEnvelope(value.target_run, url)
    : null
  if (
    (value.receipt === null) !== (targetRun === null) ||
    (value.receipt &&
      targetRun &&
      value.receipt.target_run_id !== targetRun.definition.run_id) ||
    (value.receipt &&
      value.apply_receipt &&
      value.receipt.apply_receipt_id !== value.apply_receipt.receipt_id)
  )
    throw invalidContract(url)
  return {
    apply_receipt: value.apply_receipt,
    receipt: value.receipt,
    target_run: targetRun,
  }
}

function amendmentCollectionUrl(runId: string, stageId: string) {
  return `/api/runs/${encodeURIComponent(runId)}/planning/${encodeURIComponent(stageId)}/amendments`
}

function amendmentUrl(runId: string, amendmentId: string) {
  return `/api/runs/${encodeURIComponent(runId)}/planning/amendments/${encodeURIComponent(amendmentId)}`
}

function isAmendment(value: unknown): value is ArtifactAmendment {
  return (
    isRecord(value) &&
    value.architecture_version === "phase32-routes-v1" &&
    isRoute(value.creation_route_id) &&
    requiredStrings(value, [
      "amendment_id",
      "command_digest",
      "idempotency_key_digest",
      "run_id",
      "route_revision",
      "definition_digest",
      "source_stage_id",
      "artifact_kind",
      "source_artifact_ref",
      "source_payload_digest",
      "proposed_payload_digest",
      "impact_id",
      "author_note",
      "created_at",
    ]) &&
    Number.isInteger(value.source_domain_revision) &&
    isRecord(value.proposed_payload)
  )
}

function isImpact(value: unknown): value is ArtifactImpactAnalysis {
  return (
    isRecord(value) &&
    value.architecture_version === "phase32-routes-v1" &&
    isRoute(value.creation_route_id) &&
    requiredStrings(value, [
      "impact_id",
      "amendment_id",
      "run_id",
      "route_revision",
      "definition_digest",
      "source_stage_id",
      "source_artifact_ref",
      "source_payload_digest",
      "proposed_payload_digest",
      "impact_digest",
    ]) &&
    Number.isInteger(value.source_domain_revision) &&
    targetList(value.preserved) &&
    targetList(value.stale) &&
    targetList(value.historical_frozen) &&
    Array.isArray(value.blocked_references) &&
    value.blocked_references.every(isBlockedReference) &&
    stringList(value.affected_only_scope) &&
    stringList(value.restart_from_stage_scope)
  )
}

function isImpactTarget(value: unknown): value is AmendmentImpactTarget {
  return (
    isRecord(value) &&
    requiredStrings(value, [
      "stage_id",
      "artifact_kind",
      "artifact_ref",
      "unit_ref",
      "reason",
    ])
  )
}

function isBlockedReference(value: unknown) {
  return (
    isRecord(value) &&
    requiredStrings(value, [
      "reference",
      "referenced_stage_id",
      "referenced_artifact_ref",
      "unit_ref",
    ])
  )
}

function isApplyReceipt(value: unknown): value is AmendmentApplyReceipt {
  return (
    isRecord(value) &&
    value.architecture_version === "phase32-routes-v1" &&
    ["affected_only", "restart_from_stage"].includes(String(value.scope)) &&
    requiredStrings(value, [
      "receipt_id",
      "plan_id",
      "run_id",
      "amendment_id",
      "previous_artifact_ref",
      "committed_artifact_ref",
      "event_id",
      "applied_at",
    ]) &&
    Number.isInteger(value.domain_revision_before) &&
    Number.isInteger(value.domain_revision_after) &&
    value.domain_revision_after === Number(value.domain_revision_before) + 1
  )
}

function isBranchReceipt(value: unknown): value is AmendmentBranchReceipt {
  return (
    isRecord(value) &&
    value.architecture_version === "phase32-routes-v1" &&
    requiredStrings(value, [
      "receipt_id",
      "plan_id",
      "source_run_id",
      "target_run_id",
      "project_id",
      "amendment_id",
      "apply_receipt_id",
      "target_definition_digest",
      "frontier_stage_id",
      "source_event_id",
      "target_event_id",
      "branched_at",
    ]) &&
    Number.isInteger(value.source_domain_revision) &&
    isRecord(value.imported_artifact_refs) &&
    Object.values(value.imported_artifact_refs).every(
      (item) => typeof item === "string" && item.length > 0,
    )
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function requiredStrings(value: Record<string, unknown>, fields: string[]) {
  return fields.every((field) => typeof value[field] === "string")
}

function stringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string")
}

function targetList(value: unknown): value is AmendmentImpactTarget[] {
  return Array.isArray(value) && value.every(isImpactTarget)
}

function isRoute(value: unknown) {
  return ["screenplay_sample", "short_novel", "long_novel"].includes(
    String(value),
  )
}

function invalidContract(url: string) {
  return new RunApiError(`修订接口返回了无法识别的数据：${url}`, 502)
}

async function responseError(response: Response, url: string) {
  let message = ""
  let code: string | undefined
  try {
    const value: unknown = await response.json()
    if (isRecord(value)) {
      if (typeof value.detail === "string") message = value.detail
      else if (isRecord(value.detail)) {
        code =
          typeof value.detail.code === "string" ? value.detail.code : undefined
        message =
          typeof value.detail.message === "string" ? value.detail.message : ""
      }
    }
  } catch {
    message = ""
  }
  return new RunApiError(
    message || `修订请求失败：${url} (${response.status})`,
    response.status,
    code,
  )
}
