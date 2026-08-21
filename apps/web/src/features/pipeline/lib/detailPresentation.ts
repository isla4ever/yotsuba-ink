import type { ChapterVersionRecord } from "../contracts/run"

export type DetailChapterProgress = {
  className: string
  label: string
}

export function detailChapterProgress(
  chapterId: string,
  versions: ChapterVersionRecord[],
  pendingDecisions: Array<Record<string, unknown>>,
): DetailChapterProgress {
  const chapterVersions = versions.filter(
    (version) => version.chapter_id === chapterId,
  )
  const hasAccepted = chapterVersions.some((version) =>
    ["accepted", "edited", "branched"].includes(
      String(version.artifact.author_status),
    ),
  )
  const hasPendingDecision = pendingDecisions.some(
    (decision) => decision.chapter_id === chapterId,
  )
  if (hasAccepted && hasPendingDecision)
    return { className: "text-amber", label: "证据待处理" }
  if (hasAccepted) return { className: "text-mint", label: "已成稿" }
  if (hasPendingDecision)
    return { className: "text-amber", label: "等待决策" }
  if (chapterVersions.length > 0)
    return { className: "text-action", label: "候选稿" }
  return { className: "text-fog", label: "蓝图" }
}

export function orderedNumber(ref: string) {
  const value = Number(ref.split("-").at(-1))
  return Number.isInteger(value) && value > 0 ? value : 0
}

export function stageDraftStatusLabel(status: string) {
  const labels: Record<string, string> = {
    clean: "尚未修改",
    dirty: "等待保存",
    error: "保存失败",
    loading: "读取草稿",
    saved: "草稿已保存",
    saving: "正在保存",
  }
  return labels[status] ?? ""
}
