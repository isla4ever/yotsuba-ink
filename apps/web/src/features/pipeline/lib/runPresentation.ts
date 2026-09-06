import type { Phase32RunEnvelope, Phase32StageStatus } from "../contracts/run"
import type { StageStatus } from "@/features/pipeline/contracts/app"

export function runStageStatuses(
  envelope: Phase32RunEnvelope | null,
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

function stageStatus(status: Phase32StageStatus, active: boolean): StageStatus {
  if (status === "completed") return "committed"
  if (status === "failed") return "failed"
  if (status === "stale") return "blocked"
  if (status === "awaiting_decision") return "warning"
  if (status === "running" || (active && status === "available"))
    return "active"
  return "pending"
}
