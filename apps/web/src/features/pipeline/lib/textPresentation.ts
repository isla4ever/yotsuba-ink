import type { ChapterVersionRecord } from "../contracts/run"
import type { TextDecision } from "./textDecision"

export function chapterVersionsFor(
  chapterId: string,
  records: ChapterVersionRecord[],
) {
  return records
    .filter((record) => record.chapter_id === chapterId)
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
}

export function selectedChapterVersion(
  chapterId: string,
  records: ChapterVersionRecord[],
  decision: TextDecision | null,
) {
  const versions = chapterVersionsFor(chapterId, records)
  const decisionVersion =
    decision?.chapterId === chapterId
      ? versions.find(
          (record) => record.version_id === decision.chapterVersionId,
        )
      : undefined
  if (decisionVersion) return decisionVersion
  return (
    versions.find((record) =>
      ["accepted", "edited", "branched"].includes(
        String(record.artifact.author_status),
      ),
    ) ?? versions[0]
  )
}

export function nonWhitespaceCharacters(value: string) {
  return Array.from(value).filter((character) => !/\s/.test(character)).length
}

export function chapterAuthorStatusLabel(status: unknown) {
  const labels: Record<string, string> = {
    accepted: "已接受",
    branched: "分支版本",
    candidate: "候选稿",
    edited: "人工编辑",
  }
  return labels[String(status)] ?? "未知状态"
}
