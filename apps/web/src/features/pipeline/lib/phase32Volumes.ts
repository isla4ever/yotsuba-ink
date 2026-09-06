export type VolumeContractDraft = {
  volume_ref: string
  ordinal: number
  part_ref: string
  promise: string
  conflict: string
  climax: string
  closure: string
  cast_subject_refs: string[]
  length_hint: number
}

export type VolumeArchitectureDraft = {
  volumes: VolumeContractDraft[]
}

export type VolumeReferenceLabel = {
  label: string
  ref: string
}

export type VolumeReferenceContext = {
  cast: Record<string, VolumeReferenceLabel>
  parts: Record<string, VolumeReferenceLabel>
}

export type VolumeArchitectureDiagnostics = {
  partCoverage: Array<{
    lengthHint: number
    partRef: string
    volumeRefs: string[]
  }>
  totalLengthHint: number
  uniqueCastCount: number
  volumeCount: number
}

type VolumeArchitectureParseResult = {
  artifact: VolumeArchitectureDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32Volumes(
  payload: Record<string, unknown> | null,
): VolumeArchitectureParseResult {
  if (!payload)
    return {
      artifact: null,
      error: "当前阶段尚无 Volume Architecture Artifact",
    }
  if (!Array.isArray(payload.volumes))
    return { artifact: null, error: "卷册聚合字段不完整" }

  const volumes = payload.volumes.map(parseVolume)
  if (volumes.some((volume) => volume === null))
    return { artifact: null, error: "卷合同字段不完整" }

  const artifact = { volumes: volumes as VolumeContractDraft[] }
  const refs = artifact.volumes.map((volume) => volume.volume_ref)
  const invalid =
    artifact.volumes.length === 0 ||
    artifact.volumes.length > 24 ||
    new Set(refs).size !== refs.length ||
    artifact.volumes.some(
      (volume, index) =>
        !REF_PATTERN.test(volume.volume_ref) ||
        volume.ordinal !== index + 1 ||
        !REF_PATTERN.test(volume.part_ref) ||
        !nonEmpty(volume.promise) ||
        !nonEmpty(volume.conflict) ||
        !nonEmpty(volume.climax) ||
        !nonEmpty(volume.closure) ||
        volume.cast_subject_refs.length === 0 ||
        volume.cast_subject_refs.length > 120 ||
        new Set(volume.cast_subject_refs).size !==
          volume.cast_subject_refs.length ||
        volume.cast_subject_refs.some((ref) => !REF_PATTERN.test(ref)) ||
        !Number.isInteger(volume.length_hint) ||
        volume.length_hint < 2_000 ||
        volume.length_hint > 300_000,
    )

  return {
    artifact,
    error: invalid ? "卷册架构存在空字段、无效引用、重复卷或顺序漂移" : "",
  }
}

export function extractVolumeReferenceContext(
  architecturePayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): VolumeReferenceContext {
  const parts: VolumeReferenceContext["parts"] = {}
  const cast: VolumeReferenceContext["cast"] = {}
  const partValues = Array.isArray(architecturePayload.parts)
    ? architecturePayload.parts
    : []
  const characterValues = Array.isArray(castPayload.characters)
    ? castPayload.characters
    : []

  for (const [index, value] of partValues.entries()) {
    if (!isRecord(value) || typeof value.part_ref !== "string") continue
    const question =
      typeof value.dramatic_question === "string"
        ? value.dramatic_question.trim()
        : ""
    parts[value.part_ref] = {
      ref: value.part_ref,
      label: `Part ${String(index + 1).padStart(2, "0")}${
        question ? ` · ${question}` : ""
      }`,
    }
  }
  for (const value of characterValues) {
    if (
      !isRecord(value) ||
      typeof value.subject_ref !== "string" ||
      typeof value.display_name !== "string"
    )
      continue
    cast[value.subject_ref] = {
      ref: value.subject_ref,
      label: value.display_name,
    }
  }
  return { cast, parts }
}

export function volumeArchitectureDiagnostics(
  artifact: VolumeArchitectureDraft,
): VolumeArchitectureDiagnostics {
  const coverage = new Map<string, {
    lengthHint: number
    volumeRefs: string[]
  }>()
  const castRefs = new Set<string>()
  for (const volume of artifact.volumes) {
    const current = coverage.get(volume.part_ref) ?? {
      lengthHint: 0,
      volumeRefs: [],
    }
    current.lengthHint += volume.length_hint
    current.volumeRefs.push(volume.volume_ref)
    coverage.set(volume.part_ref, current)
    volume.cast_subject_refs.forEach((ref) => castRefs.add(ref))
  }
  return {
    partCoverage: Array.from(coverage, ([partRef, value]) => ({
      partRef,
      ...value,
    })),
    totalLengthHint: artifact.volumes.reduce(
      (total, volume) => total + volume.length_hint,
      0,
    ),
    uniqueCastCount: castRefs.size,
    volumeCount: artifact.volumes.length,
  }
}

export function reorderVolumeContracts(
  volumes: VolumeContractDraft[],
  index: number,
  offset: -1 | 1,
) {
  const target = index + offset
  if (target < 0 || target >= volumes.length) return volumes
  const reordered = [...volumes]
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  return reordered.map((volume, volumeIndex) => ({
    ...volume,
    ordinal: volumeIndex + 1,
  }))
}

export function formatCharacterCount(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

function parseVolume(value: unknown): VolumeContractDraft | null {
  if (!isRecord(value)) return null
  const textFields = [
    "volume_ref",
    "part_ref",
    "promise",
    "conflict",
    "climax",
    "closure",
  ] as const
  if (
    !textFields.every((field) => typeof value[field] === "string") ||
    !Number.isInteger(value.ordinal) ||
    !Number.isInteger(value.length_hint) ||
    !Array.isArray(value.cast_subject_refs) ||
    !value.cast_subject_refs.every((item) => typeof item === "string")
  )
    return null
  return value as VolumeContractDraft
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}
