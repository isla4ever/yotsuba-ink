import type {
  GraphRunEnvelope,
  GraphRunStatus,
  NarrativeStageId,
  ProviderUsageSummary,
  RunEvent,
} from "../contracts/run"

const terminalEventStatus: Record<string, GraphRunStatus> = {
  "run.completed": "completed",
  "run.failed": "failed",
}

const stageEvents = new Set([
  "node.started",
  "node.completed",
  "node.failed",
  "artifact.candidate_ready",
  "artifact.committed",
  "decision.required",
  "decision.resolved",
  "review.started",
  "review.completed",
  "review.unavailable",
  "evidence.proposed",
  "evidence.recovery_required",
  "writeback.queued",
  "writeback.committed",
  "writeback.failed",
])

export function projectLiveRun(
  envelope: GraphRunEnvelope | null,
  events: RunEvent[],
): GraphRunEnvelope | null {
  if (!envelope || events.length === 0) return envelope

  const ordered = [...events].sort((left, right) => left.sequence - right.sequence)
  const latest = ordered[ordered.length - 1]
  const latestStageEvent = [...ordered]
    .reverse()
    .find((event) => event.stage_id && stageEvents.has(event.type))
  const latestUsage = [...ordered]
    .reverse()
    .map((event) => providerUsage(event.payload?.provider_usage))
    .find((usage): usage is ProviderUsageSummary => usage !== null)
  const terminalStatus = latest ? terminalEventStatus[latest.type] : undefined
  const activeStage = latestStageEvent?.stage_id ?? envelope.read_model.active_stage_id
  const activeChapterNumber = chapterNumber(
    latestStageEvent?.chapter_id,
    envelope.read_model.active_chapter_number,
  )
  const status = terminalStatus ?? liveStatus(envelope.read_model.status, latest)
  const stageStatus = {
    ...envelope.read_model.stage_status,
  }
  if (activeStage && status === "running") stageStatus[activeStage] = "running"
  if (activeStage && status === "awaiting_decision") {
    stageStatus[activeStage] = "awaiting_decision"
  }
  if (activeStage && status === "failed") stageStatus[activeStage] = "failed"

  return {
    ...envelope,
    read_model: {
      ...envelope.read_model,
      status,
      active_stage_id: activeStage,
      active_chapter_number: activeChapterNumber,
      stage_status: stageStatus,
      provider_usage: latestUsage ?? envelope.read_model.provider_usage,
      checkpoint_id: latest?.checkpoint_id || envelope.read_model.checkpoint_id,
    },
  }
}

function liveStatus(
  current: GraphRunStatus,
  latest: RunEvent | undefined,
): GraphRunStatus {
  if (latest?.type === "decision.required") return "awaiting_decision"
  if (latest?.type === "decision.resolved" && current === "awaiting_decision") {
    return "running"
  }
  return current === "created" ? "running" : current
}

function chapterNumber(chapterId: string | undefined, fallback: number) {
  const match = chapterId?.match(/^chapter-(\d+)$/)
  return match ? Number(match[1]) : fallback
}

function providerUsage(value: unknown): ProviderUsageSummary | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  const keys: Array<keyof ProviderUsageSummary> = [
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
  ]
  if (!keys.every((key) => Number.isInteger(record[key]) && Number(record[key]) >= 0)) {
    return null
  }
  return Object.fromEntries(keys.map((key) => [key, Number(record[key])])) as ProviderUsageSummary
}
