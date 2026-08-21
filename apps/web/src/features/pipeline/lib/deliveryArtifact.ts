import type {
  CoverArtifact,
  ExportArtifact,
  ExportVolume,
} from "../contracts/delivery"

export type DeliveryParseResult<T> = {
  artifact: T | null
  error: string
}

export function parseCoverArtifact(
  value: unknown,
): DeliveryParseResult<CoverArtifact> {
  if (!isRecord(value)) return invalid("Cover Artifact 不是有效对象")
  const topLevelError = exactKeyError(
    value,
    ["brief", "selected_asset_id"],
    "Cover Artifact",
  )
  if (topLevelError) return invalid(topLevelError)
  if (!isRecord(value.brief)) return invalid("Cover Brief 不是有效对象")
  const briefError = exactKeyError(
    value.brief,
    ["concept", "image_prompt", "palette", "negative_constraints"],
    "Cover Brief",
  )
  if (briefError) return invalid(briefError)
  if (!nonEmptyText(value.brief.concept))
    return invalid("Cover Brief 的 concept 不能为空")
  if (!nonEmptyText(value.brief.image_prompt))
    return invalid("Cover Brief 的 image_prompt 不能为空")
  if (
    !validTextList(value.brief.palette) ||
    value.brief.palette.length < 1 ||
    value.brief.palette.length > 6
  ) {
    return invalid("Cover Brief 必须包含 1-6 个有效色值")
  }
  if (
    !validTextList(value.brief.negative_constraints) ||
    value.brief.negative_constraints.length > 16
  ) {
    return invalid("Cover Brief 的排除项无效")
  }
  if (typeof value.selected_asset_id !== "string")
    return invalid("selected_asset_id 必须是文本")
  return { artifact: value as CoverArtifact, error: "" }
}

export function parseExportArtifact(
  value: unknown,
): DeliveryParseResult<ExportArtifact> {
  if (!isRecord(value)) return invalid("Export Artifact 不是有效对象")
  const topLevelError = exactKeyError(
    value,
    [
      "format",
      "chapter_version_ids",
      "cover_asset_id",
      "metadata",
      "volumes",
    ],
    "Export Artifact",
  )
  if (topLevelError) return invalid(topLevelError)
  if (value.format !== "md" && value.format !== "json" && value.format !== "zip")
    return invalid("Export format 无效")
  if (
    !validTextList(value.chapter_version_ids) ||
    value.chapter_version_ids.length === 0 ||
    new Set(value.chapter_version_ids).size !== value.chapter_version_ids.length
  ) {
    return invalid("chapter_version_ids 必须是非空且不重复的版本列表")
  }
  if (typeof value.cover_asset_id !== "string")
    return invalid("cover_asset_id 必须是文本")
  if (!isRecord(value.metadata)) return invalid("Export metadata 不是有效对象")
  const metadataError = exactKeyError(
    value.metadata,
    ["title", "author", "version_note"],
    "Export metadata",
  )
  if (metadataError) return invalid(metadataError)
  if (!nonEmptyText(value.metadata.title))
    return invalid("Export metadata 的 title 不能为空")
  if (
    typeof value.metadata.author !== "string" ||
    typeof value.metadata.version_note !== "string"
  ) {
    return invalid("Export metadata 的作者与版本说明必须是文本")
  }
  if (
    !Array.isArray(value.volumes) ||
    value.volumes.length < 1 ||
    value.volumes.length > 24
  ) {
    return invalid("Export volumes 必须包含 1-24 卷")
  }
  const volumes: ExportVolume[] = []
  const titles = new Set<string>()
  for (let index = 0; index < value.volumes.length; index += 1) {
    const volume = value.volumes[index]
    if (!isRecord(volume)) return invalid(`导出分卷 ${index + 1} 不是有效对象`)
    const volumeError = exactKeyError(
      volume,
      ["title", "chapter_count"],
      `导出分卷 ${index + 1}`,
    )
    if (volumeError) return invalid(volumeError)
    if (!nonEmptyText(volume.title))
      return invalid(`导出分卷 ${index + 1} 的 title 不能为空`)
    const titleLength = Array.from(volume.title.trim()).length
    if (titleLength < 2 || titleLength > 12)
      return invalid(`导出分卷 ${index + 1} 的 title 必须为 2-12 字`)
    if (titles.has(volume.title.trim()))
      return invalid(`导出分卷标题重复：${volume.title.trim()}`)
    if (
      typeof volume.chapter_count !== "number" ||
      !Number.isInteger(volume.chapter_count) ||
      volume.chapter_count < 1
    )
      return invalid(`导出分卷 ${index + 1} 的 chapter_count 无效`)
    titles.add(volume.title.trim())
    volumes.push(volume as ExportVolume)
  }
  const volumeChapterCount = volumes.reduce(
    (sum, volume) => sum + volume.chapter_count,
    0,
  )
  if (volumeChapterCount !== value.chapter_version_ids.length)
    return invalid("Export 分卷章数没有完整覆盖已锁定章节版本")
  return { artifact: value as ExportArtifact, error: "" }
}

function invalid<T>(error: string): DeliveryParseResult<T> {
  return { artifact: null, error }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmptyText(value: unknown): value is string {
  return typeof value === "string" && Boolean(value.trim())
}

function validTextList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => nonEmptyText(item))
}

function exactKeyError(
  value: Record<string, unknown>,
  expected: string[],
  label: string,
) {
  const unknown = Object.keys(value).filter((key) => !expected.includes(key))
  const missing = expected.filter((key) => !(key in value))
  if (unknown.length) return `${label} 包含未支持字段：${unknown.join("、")}`
  if (missing.length) return `${label} 缺少字段：${missing.join("、")}`
  return ""
}
