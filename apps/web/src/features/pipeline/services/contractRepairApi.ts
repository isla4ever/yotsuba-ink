import type {
  Phase32ContractQuarantine,
  Phase32ContractRepairRecord,
  Phase32ContractRepairResponse,
} from "../contracts/contractRepair"
import type { Phase32PendingDecision } from "../contracts/run"
import { parseRunEnvelope, RunApiError } from "./runApi"

export async function getCurrentContractQuarantine(
  runId: string,
  signal?: AbortSignal,
): Promise<Phase32ContractQuarantine> {
  const url = `/api/runs/${encodeURIComponent(runId)}/contract-quarantine`
  const response = await fetch(url, { signal })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (!isRecord(value) || !isQuarantine(value.quarantine))
    throw invalidContract(url)
  return value.quarantine
}

export async function repairContractCandidate(
  runId: string,
  command: {
    repairId: string
    quarantine: Phase32ContractQuarantine
    payload: Record<string, unknown>
  },
): Promise<Phase32ContractRepairResponse> {
  const url = `/api/runs/${encodeURIComponent(runId)}/contract-repairs`
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repair_id: command.repairId,
      provider_receipt_ref: command.quarantine.provider_receipt_ref,
      provider_request_signature: command.quarantine.provider_request_signature,
      definition_digest: command.quarantine.definition_digest,
      domain_revision: command.quarantine.domain_revision,
      source_payload_digest: command.quarantine.source_payload_digest,
      payload: command.payload,
    }),
  })
  if (!response.ok) throw await responseError(response, url)
  const value: unknown = await response.json()
  if (
    !isRecord(value) ||
    typeof value.reused !== "boolean" ||
    !isRepairRecord(value.repair) ||
    !(value.decision === null || isPendingDecision(value.decision))
  )
    throw invalidContract(url)
  const repair = value.repair
  const run = parseRunEnvelope(value.run, url)
  const decision =
    value.decision ??
    run.read_model.pending_decisions.find(
      (item) =>
        item.stage_id === command.quarantine.stage_id &&
        item.artifact_ref === repair.candidate_ref,
    ) ??
    null
  if (
    repair.run_id !== run.definition.run_id ||
    repair.stage_id !== command.quarantine.stage_id ||
    repair.provider_receipt_ref !== command.quarantine.provider_receipt_ref ||
    repair.status !== "succeeded" ||
    !decision ||
    decision.decision_id !== repair.decision_id ||
    decision.artifact_ref !== repair.candidate_ref
  )
    throw invalidContract(url)
  return {
    reused: value.reused,
    repair,
    run,
    decision,
  }
}

function isQuarantine(value: unknown): value is Phase32ContractQuarantine {
  return (
    isRecord(value) &&
    isRoute(value.creation_route_id) &&
    requiredStrings(value, [
      "run_id",
      "stage_id",
      "definition_digest",
      "provider_receipt_ref",
      "provider_request_signature",
      "source_payload_digest",
    ]) &&
    Number.isInteger(value.domain_revision) &&
    Number(value.domain_revision) >= 0 &&
    isRecord(value.source_payload) &&
    typeof value.eligible === "boolean" &&
    Array.isArray(value.findings) &&
    value.findings.length > 0 &&
    value.findings.every(
      (finding) =>
        isRecord(finding) && requiredStrings(finding, ["code", "message"]),
    )
  )
}

function isRepairRecord(value: unknown): value is Phase32ContractRepairRecord {
  return (
    isRecord(value) &&
    value.architecture_version === "phase32-routes-v1" &&
    requiredStrings(value, [
      "repair_ref",
      "repair_id",
      "run_id",
      "definition_digest",
      "stage_id",
      "provider_receipt_ref",
      "provider_request_signature",
      "source_payload_digest",
      "repaired_payload_digest",
      "candidate_ref",
      "status",
      "decision_id",
      "created_at",
      "updated_at",
    ]) &&
    ["pending", "succeeded"].includes(String(value.status)) &&
    Number.isInteger(value.domain_revision) &&
    (value.result === null || isRecord(value.result))
  )
}

function isPendingDecision(value: unknown): value is Phase32PendingDecision {
  return (
    isRecord(value) &&
    requiredStrings(value, [
      "decision_id",
      "stage_id",
      "unit_ref",
      "artifact_ref",
      "kind",
    ]) &&
    Number.isInteger(value.domain_revision) &&
    Array.isArray(value.allowed_actions) &&
    value.allowed_actions.every((action) => typeof action === "string")
  )
}

function isRoute(value: unknown) {
  return ["screenplay_sample", "short_novel", "long_novel"].includes(
    String(value),
  )
}

function requiredStrings(value: Record<string, unknown>, fields: string[]) {
  return fields.every((field) => typeof value[field] === "string")
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

async function responseError(response: Response, url: string) {
  let code: string | undefined
  let message = ""
  try {
    const value = (await response.json()) as { detail?: unknown }
    if (typeof value.detail === "string") message = value.detail
    if (isRecord(value.detail)) {
      code =
        typeof value.detail.code === "string" ? value.detail.code : undefined
      message =
        typeof value.detail.message === "string" ? value.detail.message : ""
    }
  } catch {
    message = ""
  }
  return new RunApiError(
    message || `合同修复请求失败：${url} (${response.status})`,
    response.status,
    code,
  )
}

function invalidContract(url: string) {
  return new RunApiError(`合同修复接口返回了无法识别的数据：${url}`, 502)
}
