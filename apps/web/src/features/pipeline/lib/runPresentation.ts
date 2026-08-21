import type { GraphRunEnvelope, GraphStageStatus } from "../contracts/run"
import type { StageStatus } from "@/features/pipeline/contracts/app"

export function runStageStatuses(
  envelope: GraphRunEnvelope | null,
  fallback: Record<string, StageStatus>,
) {
  if (!envelope) return fallback
  return Object.fromEntries(
    Object.entries(envelope.read_model.stage_status).map(
      ([stageId, status]) => [
        stageId,
        stageStatus(status, stageId === envelope.read_model.active_stage_id),
      ],
    ),
  ) as Record<string, StageStatus>
}

export function activeRunModel(envelope: GraphRunEnvelope | null) {
  if (!envelope) return ""
  const stageId = envelope.read_model.active_stage_id
  if (stageId === "export") return "系统任务"
  return envelope.definition.provider_bindings[stageId]?.model ?? ""
}

function stageStatus(status: GraphStageStatus, active: boolean): StageStatus {
  if (status === "completed") return "committed"
  if (status === "failed") return "failed"
  if (status === "awaiting_decision") return "warning"
  if (status === "running" || (active && status === "available"))
    return "active"
  return "pending"
}
