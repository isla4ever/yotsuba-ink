import {
  parsePhase32Screenplay,
  shortSceneRef,
  type ScreenplayDraft,
} from "./phase32Screenplay"
import { parsePhase32DeliveryEnvelopeMetadata } from "./phase32Delivery"
import type { Phase32DeliveryEnvelopeMetadata } from "../contracts/phase32Delivery"

export type ScriptDeliveryFormat = "fountain" | "pdf" | "markdown"

export type ScriptDeliveryArtifact = {
  title: string
  author: string
  version_note: string
  formats: ScriptDeliveryFormat[]
  scene_refs: string[]
  scene_version_refs: string[]
}

export type ScriptDeliveryReceipt = {
  export_id: string
  run_id: string
  artifact_ref: string
  artifact_digest: string
  format: ScriptDeliveryFormat
  scene_refs: string[]
  scene_version_refs: string[]
  title: string
  author: string
  version_note: string
  filename: string
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export type ScriptDeliveryEnvelope = {
  runId: string
  artifactRef: string
  artifactDigest: string
  receipts: ScriptDeliveryReceipt[]
} & Phase32DeliveryEnvelopeMetadata

export type ScriptDeliverySceneRow = {
  ordinal: number
  sceneRef: string
  versionRef: string
  heading: string
  blockCount: number
  actionBlocks: number
  dialogueBlocks: number
  valid: boolean
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/
const VERSION_PATTERN = /^p32-script-committed-[a-f0-9]{64}$/
const DIGEST_PATTERN = /^[a-f0-9]{64}$/
const FORMATS = new Set<ScriptDeliveryFormat>(["fountain", "pdf", "markdown"])

export function parseScriptDeliveryArtifact(
  payload: Record<string, unknown> | null,
): ScriptDeliveryArtifact {
  if (!payload) throw new Error("交付 Artifact 尚未生成")
  const title = text(payload.title)
  const author = stringValue(payload.author)
  const versionNote = stringValue(payload.version_note)
  const formats = array(payload.formats).filter(isDeliveryFormat)
  const sceneRefs = array(payload.scene_refs).filter(isRef)
  const sceneVersionRefs = array(payload.scene_version_refs).filter(
    isVersionRef,
  )
  if (
    !title ||
    formats.length !== array(payload.formats).length ||
    sceneRefs.length !== array(payload.scene_refs).length ||
    sceneVersionRefs.length !== array(payload.scene_version_refs).length ||
    formats.length === 0 ||
    new Set(formats).size !== formats.length ||
    sceneRefs.length === 0 ||
    new Set(sceneRefs).size !== sceneRefs.length ||
    sceneRefs.length !== sceneVersionRefs.length ||
    new Set(sceneVersionRefs).size !== sceneVersionRefs.length
  )
    throw new Error("剧本交付 Artifact 的格式或 Scene 版本绑定无效")
  return {
    title,
    author,
    version_note: versionNote,
    formats,
    scene_refs: sceneRefs,
    scene_version_refs: sceneVersionRefs,
  }
}

export function parseScriptDeliveryEnvelope(
  value: unknown,
  expectedRunId: string,
): ScriptDeliveryEnvelope {
  if (
    !isRecord(value) ||
    value.run_id !== expectedRunId ||
    !Array.isArray(value.items)
  )
    throw new Error("交付文件接口返回了无法识别的数据")
  const metadata = parsePhase32DeliveryEnvelopeMetadata(
    value,
    "script_delivery",
  )
  const artifactRef = stringValue(value.artifact_ref)
  const artifactDigest = stringValue(value.artifact_digest)
  const receipts = value.items.map(parseReceipt)
  if (receipts.length) {
    if (!artifactRef || !DIGEST_PATTERN.test(artifactDigest))
      throw new Error("交付文件缺少冻结 Artifact 身份")
    if (
      receipts.some(
        (receipt) =>
          receipt.run_id !== expectedRunId ||
          receipt.artifact_ref !== artifactRef ||
          receipt.artifact_digest !== artifactDigest,
      )
    )
      throw new Error("交付文件回执不属于当前冻结 Artifact")
  }
  return {
    runId: expectedRunId,
    artifactRef,
    artifactDigest,
    receipts,
    ...metadata,
  }
}

export function verifyScriptDeliveryBinding(
  artifact: ScriptDeliveryArtifact,
  envelope: ScriptDeliveryEnvelope,
  artifactRef: string,
  artifactDigest: string,
) {
  if (
    envelope.artifactRef !== artifactRef ||
    envelope.artifactDigest !== artifactDigest
  )
    return "交付文件回执与当前 Export Artifact 不一致"
  if (
    envelope.receipts.length !== artifact.formats.length ||
    artifact.formats.some(
      (format) =>
        !envelope.receipts.some((receipt) => receipt.format === format),
    )
  )
    return "冻结格式尚未全部物化"
  if (
    envelope.receipts.some(
      (receipt) =>
        receipt.title !== artifact.title ||
        receipt.author !== artifact.author ||
        receipt.version_note !== artifact.version_note,
    )
  )
    return "交付文件元数据与冻结 Artifact 不一致"
  if (
    envelope.receipts.some(
      (receipt) =>
        !sameOrder(receipt.scene_refs, artifact.scene_refs) ||
        !sameOrder(receipt.scene_version_refs, artifact.scene_version_refs),
    )
  )
    return "交付文件 Scene 清单与冻结版本顺序不一致"
  return ""
}

export function buildScriptDeliveryManifest(
  artifact: ScriptDeliveryArtifact,
  scenes: Record<string, Record<string, unknown>>,
): ScriptDeliverySceneRow[] {
  return artifact.scene_refs.map((sceneRef, index) => {
    const parsed = parsePhase32Screenplay(scenes[sceneRef] ?? null)
    const screenplay = parsed.artifact
    return {
      ordinal: index + 1,
      sceneRef,
      versionRef: artifact.scene_version_refs[index] ?? "",
      heading: screenplay?.blocks[0]?.text || shortSceneRef(sceneRef),
      blockCount: screenplay?.blocks.length ?? 0,
      actionBlocks: blockCount(screenplay, "action"),
      dialogueBlocks: blockCount(screenplay, "dialogue"),
      valid: Boolean(
        screenplay && screenplay.scene_ref === sceneRef && !parsed.error,
      ),
    }
  })
}

export function formatDeliveryBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function deliveryFormatLabel(format: ScriptDeliveryFormat) {
  if (format === "fountain") return "Fountain"
  if (format === "markdown") return "Markdown"
  return "PDF"
}

function parseReceipt(value: unknown): ScriptDeliveryReceipt {
  if (!isRecord(value)) throw new Error("交付文件回执不是对象")
  const format = value.format
  const sceneRefs = array(value.scene_refs).filter(isRef)
  const versionRefs = array(value.scene_version_refs).filter(isVersionRef)
  if (
    !requiredStrings(value, [
      "export_id",
      "run_id",
      "artifact_ref",
      "artifact_digest",
      "title",
      "filename",
      "media_type",
      "sha256",
      "created_at",
    ]) ||
    !isDeliveryFormat(format) ||
    !DIGEST_PATTERN.test(String(value.artifact_digest)) ||
    !DIGEST_PATTERN.test(String(value.sha256)) ||
    typeof value.size_bytes !== "number" ||
    value.size_bytes < 0 ||
    sceneRefs.length !== array(value.scene_refs).length ||
    versionRefs.length !== array(value.scene_version_refs).length ||
    sceneRefs.length !== versionRefs.length
  )
    throw new Error("交付文件回执字段无效")
  return {
    export_id: String(value.export_id),
    run_id: String(value.run_id),
    artifact_ref: String(value.artifact_ref),
    artifact_digest: String(value.artifact_digest),
    format,
    scene_refs: sceneRefs,
    scene_version_refs: versionRefs,
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

function blockCount(screenplay: ScreenplayDraft | null, kind: string) {
  return screenplay?.blocks.filter((block) => block.kind === kind).length ?? 0
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

function isDeliveryFormat(value: unknown): value is ScriptDeliveryFormat {
  return typeof value === "string" && FORMATS.has(value as ScriptDeliveryFormat)
}

function requiredStrings(value: Record<string, unknown>, keys: string[]) {
  return keys.every(
    (key) => typeof value[key] === "string" && String(value[key]).length > 0,
  )
}
