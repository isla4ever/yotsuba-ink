import type { CoverAssetRecord } from "../contracts/coverAsset"

export type Phase32CoverBrief = {
  concept: string
  image_prompt: string
  palette: string[]
  negative_constraints: string[]
}

export type Phase32CoverCandidate = {
  asset_ref: string
  alt_text: string
  visual_notes: string
}

export type Phase32CoverArtifact = {
  brief: Phase32CoverBrief
  candidates: Phase32CoverCandidate[]
  selected_asset_ref: string | null
  image_acceptance_status: "image_deferred" | "ready"
}

export type Phase32CoverParseResult = {
  artifact: Phase32CoverArtifact | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,127}$/

export function parsePhase32Cover(
  payload: Record<string, unknown> | null,
): Phase32CoverParseResult {
  if (!payload) return invalid("封面 Artifact 尚未生成")
  if (!isRecord(payload.brief)) return invalid("封面视觉 Brief 无效")
  const concept = text(payload.brief.concept)
  const imagePrompt = text(payload.brief.image_prompt)
  const palette = textList(payload.brief.palette)
  const negativeConstraints = textList(payload.brief.negative_constraints)
  if (!concept || !imagePrompt)
    return invalid("封面视觉概念与图片 Prompt 不能为空")
  if (palette.length < 1 || palette.length > 8)
    return invalid("封面色板必须包含 1-8 个有效颜色")
  if (
    !Array.isArray(payload.brief.negative_constraints) ||
    negativeConstraints.length !== payload.brief.negative_constraints.length ||
    negativeConstraints.length > 24
  )
    return invalid("封面排除项不符合当前合同")

  if (!Array.isArray(payload.candidates) || payload.candidates.length > 12)
    return invalid("封面候选资产字段无效")
  const imageAcceptanceStatus =
    payload.image_acceptance_status === undefined
      ? payload.candidates.length > 0
        ? "ready"
        : "image_deferred"
      : payload.image_acceptance_status
  if (
    imageAcceptanceStatus !== "image_deferred" &&
    imageAcceptanceStatus !== "ready"
  )
    return invalid("封面图片验收状态无效")
  if (imageAcceptanceStatus === "ready" && payload.candidates.length < 1)
    return invalid("已启用图片验收时，封面必须包含真实候选资产")
  if (
    imageAcceptanceStatus === "image_deferred" &&
    payload.candidates.length > 0
  )
    return invalid("图片验收暂缓时不得包含候选图片资产")
  const candidates: Phase32CoverCandidate[] = []
  for (const [index, value] of payload.candidates.entries()) {
    if (!isRecord(value)) return invalid(`封面候选 ${index + 1} 无效`)
    const assetRef = text(value.asset_ref)
    const altText = text(value.alt_text)
    const visualNotes = text(value.visual_notes)
    if (!REF_PATTERN.test(assetRef) || !altText || !visualNotes)
      return invalid(`封面候选 ${index + 1} 缺少真实资产或视觉说明`)
    candidates.push({
      asset_ref: assetRef,
      alt_text: altText,
      visual_notes: visualNotes,
    })
  }
  if (
    new Set(candidates.map((candidate) => candidate.asset_ref)).size !==
    candidates.length
  )
    return invalid("封面候选资产引用不能重复")

  const selected = payload.selected_asset_ref
  if (!(selected === null || typeof selected === "string"))
    return invalid("正式封面选择字段无效")
  if (
    typeof selected === "string" &&
    !candidates.some((candidate) => candidate.asset_ref === selected)
  )
    return invalid("正式封面必须来自当前候选资产")
  if (imageAcceptanceStatus === "image_deferred" && selected !== null)
    return invalid("图片验收暂缓时不得选择正式封面资产")

  return {
    artifact: {
      brief: {
        concept,
        image_prompt: imagePrompt,
        palette,
        negative_constraints: negativeConstraints,
      },
      candidates,
      selected_asset_ref: selected,
      image_acceptance_status: imageAcceptanceStatus,
    },
    error: "",
  }
}

export function phase32CoverAssetError(
  artifact: Phase32CoverArtifact | null,
  assets: CoverAssetRecord[],
) {
  if (!artifact) return "封面 Artifact 尚未生成"
  const assetRefs = new Set(assets.map((asset) => asset.asset_id))
  const missing = artifact.candidates.find(
    (candidate) => !assetRefs.has(candidate.asset_ref),
  )
  if (missing) return `候选资产 ${missing.asset_ref} 尚未完成持久化核验`
  return ""
}

export function selectedPhase32CoverAsset(
  artifact: Phase32CoverArtifact | null,
  assets: CoverAssetRecord[],
) {
  if (!artifact?.selected_asset_ref) return null
  return (
    assets.find((asset) => asset.asset_id === artifact.selected_asset_ref) ??
    null
  )
}

export function formatCoverBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function textList(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is string => typeof item === "string" && Boolean(item.trim()),
  )
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function invalid(error: string): Phase32CoverParseResult {
  return { artifact: null, error }
}
