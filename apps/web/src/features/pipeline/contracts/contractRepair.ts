import type {
  CreationRouteId,
  Phase32PendingDecision,
  Phase32RunEnvelope,
} from "./run"

export type Phase32ContractFinding = {
  code: string
  message: string
}

export type Phase32ContractQuarantine = {
  run_id: string
  creation_route_id: CreationRouteId
  stage_id: string
  definition_digest: string
  domain_revision: number
  provider_receipt_ref: string
  provider_request_signature: string
  source_payload_digest: string
  source_payload: Record<string, unknown>
  eligible: boolean
  findings: Phase32ContractFinding[]
}

export type Phase32ContractRepairRecord = {
  architecture_version: "phase32-routes-v1"
  repair_ref: string
  repair_id: string
  run_id: string
  definition_digest: string
  domain_revision: number
  stage_id: string
  provider_receipt_ref: string
  provider_request_signature: string
  source_payload_digest: string
  repaired_payload_digest: string
  candidate_ref: string
  status: "pending" | "succeeded"
  decision_id: string
  result: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type Phase32ContractRepairResponse = {
  reused: boolean
  repair: Phase32ContractRepairRecord
  run: Phase32RunEnvelope
  decision: Phase32PendingDecision | null
}
