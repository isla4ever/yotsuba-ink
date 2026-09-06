import type { CreationRouteId } from "../contracts/run"
import { parsePhase32DeliveryEnvelopeMetadata } from "./phase32Delivery"
import type { Phase32DeliveryEnvelopeMetadata } from "../contracts/phase32Delivery"

export type BookDeliveryFormat = "epub" | "docx" | "markdown"

export type BookDeliveryArtifact = {
  title: string
  author: string
  version_note: string
  formats: BookDeliveryFormat[]
  chapter_refs: string[]
  chapter_version_refs: string[]
  volume_refs: string[]
  cover_asset_ref: string
}

export type BookDeliveryChapterRow = {
  ordinal: number
  chapter_ref: string
  version_ref: string
  title: string
  unit_kind: "section" | "chapter"
  volume_ref: string
  character_count: number
}

export type BookDeliveryReceipt = {
  export_id: string
  run_id: string
  creation_route_id: Exclude<CreationRouteId, "screenplay_sample">
  artifact_ref: string
  artifact_digest: string
  format: BookDeliveryFormat
  chapter_refs: string[]
  chapter_version_refs: string[]
  chapter_manifest: BookDeliveryChapterRow[]
  volume_refs: string[]
  cover_asset_ref: string
  cover_sha256: string
  title: string
  author: string
  version_note: string
  filename: string
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export type BookDeliveryEnvelope = {
  runId: string
  artifactRef: string
  artifactDigest: string
  receipts: BookDeliveryReceipt[]
} & Phase32DeliveryEnvelopeMetadata

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,127}$/
const VERSION_PATTERN = /^p32-text-committed-[a-f0-9]{64}$/
const DIGEST_PATTERN = /^[a-f0-9]{64}$/
const FORMATS = new Set<BookDeliveryFormat>(["epub", "docx", "markdown"])

export function parseBookDeliveryArtifact(
  payload: Record<string, unknown> | null,
): BookDeliveryArtifact {
  if (!payload) throw new Error("成书交付 Artifact 尚未生成")
  const title = text(payload.title)
  const author = stringValue(payload.author)
  const versionNote = stringValue(payload.version_note)
  const formats = array(payload.formats).filter(isDeliveryFormat)
  const chapterRefs = array(payload.chapter_refs).filter(isRef)
  const chapterVersionRefs = array(payload.chapter_version_refs).filter(
    isVersionRef,
  )
  const volumeRefs = array(payload.volume_refs).filter(isRef)
  const coverAssetRef = text(payload.cover_asset_ref)
  if (
    !title ||
    !isRef(coverAssetRef) ||
    formats.length === 0 ||
    formats.length !== array(payload.formats).length ||
    new Set(formats).size !== formats.length ||
    chapterRefs.length === 0 ||
    chapterRefs.length !== array(payload.chapter_refs).length ||
    chapterVersionRefs.length !== array(payload.chapter_version_refs).length ||
    chapterRefs.length !== chapterVersionRefs.length ||
    new Set(chapterRefs).size !== chapterRefs.length ||
    new Set(chapterVersionRefs).size !== chapterVersionRefs.length ||
    volumeRefs.length !== array(payload.volume_refs).length ||
    new Set(volumeRefs).size !== volumeRefs.length
  )
    throw new Error("成书交付 Artifact 的格式、正文版本或封面绑定无效")
  return {
    title,
    author,
    version_note: versionNote,
    formats,
    chapter_refs: chapterRefs,
    chapter_version_refs: chapterVersionRefs,
    volume_refs: volumeRefs,
    cover_asset_ref: coverAssetRef,
  }
}

export function parseBookDeliveryEnvelope(
  value: unknown,
  expectedRunId: string,
): BookDeliveryEnvelope {
  if (
    !isRecord(value) ||
    value.run_id !== expectedRunId ||
    !Array.isArray(value.items)
  )
    throw new Error("小说交付文件接口返回了无法识别的数据")
  const metadata = parsePhase32DeliveryEnvelopeMetadata(value, "book_delivery")
  const artifactRef = stringValue(value.artifact_ref)
  const artifactDigest = stringValue(value.artifact_digest)
  const receipts = value.items.map(parseReceipt)
  if (receipts.length) {
    if (!artifactRef || !DIGEST_PATTERN.test(artifactDigest))
      throw new Error("小说交付文件缺少冻结 Artifact 身份")
    if (
      receipts.some(
        (receipt) =>
          receipt.run_id !== expectedRunId ||
          receipt.artifact_ref !== artifactRef ||
          receipt.artifact_digest !== artifactDigest,
      )
    )
      throw new Error("小说交付回执不属于当前冻结 Artifact")
  }
  return {
    runId: expectedRunId,
    artifactRef,
    artifactDigest,
    receipts,
    ...metadata,
  }
}

export function verifyBookDeliveryBinding(
  artifact: BookDeliveryArtifact,
  envelope: BookDeliveryEnvelope,
  artifactRef: string,
  artifactDigest: string,
) {
  if (
    envelope.artifactRef !== artifactRef ||
    envelope.artifactDigest !== artifactDigest
  )
    return "成书文件回执与当前 Export Artifact 不一致"
  if (
    envelope.receipts.length !== artifact.formats.length ||
    artifact.formats.some(
      (format) =>
        !envelope.receipts.some((receipt) => receipt.format === format),
    )
  )
    return "冻结的成书格式尚未全部物化"
  const firstManifest = envelope.receipts[0]?.chapter_manifest ?? []
  if (!firstManifest.length) return "成书回执缺少正文版本清单"
  for (const receipt of envelope.receipts) {
    if (
      receipt.title !== artifact.title ||
      receipt.author !== artifact.author ||
      receipt.version_note !== artifact.version_note ||
      receipt.cover_asset_ref !== artifact.cover_asset_ref ||
      !sameOrder(receipt.chapter_refs, artifact.chapter_refs) ||
      !sameOrder(receipt.chapter_version_refs, artifact.chapter_version_refs) ||
      !sameOrder(receipt.volume_refs, artifact.volume_refs)
    )
      return "成书文件元数据或冻结来源与 Export Artifact 不一致"
    if (!sameManifest(receipt.chapter_manifest, firstManifest))
      return "不同格式的正文版本清单不一致"
  }
  return ""
}

export function bookDeliveryFormatLabel(format: BookDeliveryFormat) {
  if (format === "epub") return "EPUB 3"
  if (format === "docx") return "DOCX"
  return "Markdown"
}

export function formatBookDeliveryBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function parseReceipt(value: unknown): BookDeliveryReceipt {
  if (!isRecord(value)) throw new Error("小说交付文件回执不是对象")
  const format = value.format
  const creationRouteId = value.creation_route_id
  const chapterRefs = array(value.chapter_refs).filter(isRef)
  const versionRefs = array(value.chapter_version_refs).filter(isVersionRef)
  const volumeRefs = array(value.volume_refs).filter(isRef)
  const manifest = array(value.chapter_manifest).map(parseManifestRow)
  if (
    !requiredStrings(value, [
      "export_id",
      "run_id",
      "artifact_ref",
      "artifact_digest",
      "cover_asset_ref",
      "cover_sha256",
      "title",
      "filename",
      "media_type",
      "sha256",
      "created_at",
    ]) ||
    !(creationRouteId === "short_novel" || creationRouteId === "long_novel") ||
    !isDeliveryFormat(format) ||
    !DIGEST_PATTERN.test(String(value.artifact_digest)) ||
    !DIGEST_PATTERN.test(String(value.cover_sha256)) ||
    !DIGEST_PATTERN.test(String(value.sha256)) ||
    typeof value.size_bytes !== "number" ||
    value.size_bytes < 0 ||
    chapterRefs.length !== array(value.chapter_refs).length ||
    versionRefs.length !== array(value.chapter_version_refs).length ||
    chapterRefs.length !== versionRefs.length ||
    manifest.length !== chapterRefs.length ||
    volumeRefs.length !== array(value.volume_refs).length
  )
    throw new Error("小说交付文件回执字段无效")
  for (const [index, row] of manifest.entries()) {
    if (
      row.ordinal !== index + 1 ||
      row.chapter_ref !== chapterRefs[index] ||
      row.version_ref !== versionRefs[index] ||
      (creationRouteId === "short_novel" && row.volume_ref) ||
      (creationRouteId === "long_novel" && !volumeRefs.includes(row.volume_ref))
    )
      throw new Error("小说交付正文清单与冻结顺序不一致")
  }
  return {
    export_id: String(value.export_id),
    run_id: String(value.run_id),
    creation_route_id: creationRouteId,
    artifact_ref: String(value.artifact_ref),
    artifact_digest: String(value.artifact_digest),
    format,
    chapter_refs: chapterRefs,
    chapter_version_refs: versionRefs,
    chapter_manifest: manifest,
    volume_refs: volumeRefs,
    cover_asset_ref: String(value.cover_asset_ref),
    cover_sha256: String(value.cover_sha256),
    title: String(value.title),
    author: stringValue(value.author),
    version_note: stringValue(value.version_note),
    filename: String(value.filename),
    media_type: String(value.media_type),
    size_bytes: value.size_bytes,
    sha256: String(value.sha256),
    created_at: String(value.created_at),
  }
}

function parseManifestRow(value: unknown): BookDeliveryChapterRow {
  if (!isRecord(value)) throw new Error("正文清单行不是对象")
  const unitKind = value.unit_kind
  if (
    !Number.isInteger(value.ordinal) ||
    Number(value.ordinal) < 1 ||
    !isRef(value.chapter_ref) ||
    !isVersionRef(value.version_ref) ||
    !text(value.title) ||
    !(unitKind === "section" || unitKind === "chapter") ||
    typeof value.volume_ref !== "string" ||
    !(value.volume_ref === "" || isRef(value.volume_ref)) ||
    !Number.isInteger(value.character_count) ||
    Number(value.character_count) < 1
  )
    throw new Error("正文清单行字段无效")
  return {
    ordinal: Number(value.ordinal),
    chapter_ref: value.chapter_ref,
    version_ref: value.version_ref,
    title: text(value.title),
    unit_kind: unitKind,
    volume_ref: value.volume_ref,
    character_count: Number(value.character_count),
  }
}

function sameManifest(
  left: BookDeliveryChapterRow[],
  right: BookDeliveryChapterRow[],
) {
  return (
    left.length === right.length &&
    left.every(
      (row, index) => JSON.stringify(row) === JSON.stringify(right[index]),
    )
  )
}

function sameOrder(left: string[], right: string[]) {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  )
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown) {
  return stringValue(value).trim()
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : ""
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function isRef(value: unknown): value is string {
  return typeof value === "string" && REF_PATTERN.test(value)
}

function isVersionRef(value: unknown): value is string {
  return typeof value === "string" && VERSION_PATTERN.test(value)
}

function isDeliveryFormat(value: unknown): value is BookDeliveryFormat {
  return typeof value === "string" && FORMATS.has(value as BookDeliveryFormat)
}

function requiredStrings(value: Record<string, unknown>, keys: string[]) {
  return keys.every(
    (key) => typeof value[key] === "string" && String(value[key]).length > 0,
  )
}
