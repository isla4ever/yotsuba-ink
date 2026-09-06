import type { Phase32RunEvent } from "../../contracts/run"

const EVENT_LABELS: Record<string, string> = {
  "stage.started": "阶段开始",
  "candidate.created": "候选内容生成",
  "decision.required": "等待作者决策",
  "decision.resolved": "决策已执行",
  "artifact.committed": "Artifact 已提交",
  "stage.failed": "阶段失败",
  "unit.failed": "单元失败",
  "review.completed": "审阅完成",
  "review.unavailable": "审阅不可用",
  "evidence.completed": "证据处理完成",
  "evidence.recovery_required": "证据需要恢复",
  "writeback.committed": "写回完成",
  "writeback.failed": "写回失败",
  "checkpoint.saved": "Checkpoint 已保存",
  "run.branched": "修订分支已创建",
  "export.ready": "交付物已就绪",
  "image.deferred": "图片验收暂缓",
}

export function phase32RunEventLabel(type: string) {
  return EVENT_LABELS[type] ?? type
}

export function phase32RunEventDetail(event: Phase32RunEvent) {
  const detail = [
    event.unit_ref,
    stringValue(event.payload?.artifact_ref),
    stringValue(event.payload?.target_run_id),
    stringValue(event.payload?.source_run_id),
    stringValue(event.payload?.action),
    event.node_id,
  ].find(Boolean)
  return detail || `sequence ${event.sequence}`
}

export function phase32RunEventArtifactRef(event: Phase32RunEvent) {
  return stringValue(event.payload?.artifact_ref)
}

export function formatPhase32RunEventClock(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : ""
}
