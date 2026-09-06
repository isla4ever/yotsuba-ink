export type SectionPlanUnitDraft = {
  unit_ref: string
  ordinal: number
  title: string
  dramatic_job: string
  pov_subject_ref: string
  scene_load: string
  handoff: string
  soft_character_budget: number
  promise_refs: string[]
}

export type SectionPlanDraft = {
  units: SectionPlanUnitDraft[]
}

export type SectionPlanReferenceLabel = {
  label: string
  ref: string
}

export type SectionPlanPromiseOrigin = {
  anchorRefs: string[]
  labels: string[]
  ref: string
}

export type SectionPlanReferenceContext = {
  cast: Record<string, SectionPlanReferenceLabel>
  promises: Record<string, SectionPlanPromiseOrigin>
}

export type SectionPlanDiagnostics = {
  promiseCoverage: Array<{
    promiseRef: string
    unitRefs: string[]
  }>
  totalCharacterBudget: number
  uniquePovCount: number
  unitCount: number
  unitsWithoutPromise: string[]
}

type SectionPlanParseResult = {
  artifact: SectionPlanDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32SectionPlan(
  payload: Record<string, unknown> | null,
): SectionPlanParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Section Plan Artifact" }
  if (!Array.isArray(payload.units))
    return { artifact: null, error: "章节与段落计划字段不完整" }

  const units = payload.units.map(parseUnit)
  if (units.some((unit) => unit === null))
    return { artifact: null, error: "章节或段落单元字段不完整" }

  const artifact = { units: units as SectionPlanUnitDraft[] }
  const refs = artifact.units.map((unit) => unit.unit_ref)
  const invalid =
    artifact.units.length === 0 ||
    artifact.units.length > 400 ||
    new Set(refs).size !== refs.length ||
    artifact.units.some(
      (unit, index) =>
        !REF_PATTERN.test(unit.unit_ref) ||
        unit.ordinal !== index + 1 ||
        !nonEmpty(unit.title) ||
        !nonEmpty(unit.dramatic_job) ||
        !REF_PATTERN.test(unit.pov_subject_ref) ||
        !nonEmpty(unit.scene_load) ||
        !nonEmpty(unit.handoff) ||
        !Number.isInteger(unit.soft_character_budget) ||
        unit.soft_character_budget < 100 ||
        unit.soft_character_budget > 100_000 ||
        unit.promise_refs.length > 24 ||
        unit.promise_refs.some((ref) => !REF_PATTERN.test(ref)) ||
        new Set(unit.promise_refs).size !== unit.promise_refs.length,
    )

  return {
    artifact,
    error: invalid
      ? "章节与段落计划存在空字段、无效引用、重复单元或顺序漂移"
      : "",
  }
}

export function extractSectionPlanReferenceContext(
  storyMapPayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): SectionPlanReferenceContext {
  const cast: SectionPlanReferenceContext["cast"] = {}
  const promises: SectionPlanReferenceContext["promises"] = {}
  const characters = Array.isArray(castPayload.characters)
    ? castPayload.characters
    : []
  const anchors = Array.isArray(storyMapPayload.anchors)
    ? storyMapPayload.anchors
    : []

  for (const character of characters) {
    if (
      !isRecord(character) ||
      typeof character.subject_ref !== "string" ||
      typeof character.display_name !== "string"
    )
      continue
    cast[character.subject_ref] = {
      ref: character.subject_ref,
      label: character.display_name,
    }
  }

  for (const anchor of anchors) {
    if (
      !isRecord(anchor) ||
      typeof anchor.anchor_ref !== "string" ||
      !Array.isArray(anchor.promise_refs)
    )
      continue
    const label =
      typeof anchor.dramatic_job === "string"
        ? anchor.dramatic_job.trim()
        : anchor.anchor_ref
    for (const promiseRef of anchor.promise_refs) {
      if (typeof promiseRef !== "string") continue
      const current = promises[promiseRef] ?? {
        anchorRefs: [],
        labels: [],
        ref: promiseRef,
      }
      if (!current.anchorRefs.includes(anchor.anchor_ref))
        current.anchorRefs.push(anchor.anchor_ref)
      if (label && !current.labels.includes(label)) current.labels.push(label)
      promises[promiseRef] = current
    }
  }
  return { cast, promises }
}

export function sectionPlanDiagnostics(
  artifact: SectionPlanDraft,
): SectionPlanDiagnostics {
  const coverage = new Map<string, string[]>()
  const povRefs = new Set<string>()
  for (const unit of artifact.units) {
    povRefs.add(unit.pov_subject_ref)
    for (const promiseRef of unit.promise_refs) {
      const unitRefs = coverage.get(promiseRef) ?? []
      unitRefs.push(unit.unit_ref)
      coverage.set(promiseRef, unitRefs)
    }
  }
  return {
    promiseCoverage: Array.from(coverage, ([promiseRef, unitRefs]) => ({
      promiseRef,
      unitRefs,
    })),
    totalCharacterBudget: artifact.units.reduce(
      (total, unit) => total + unit.soft_character_budget,
      0,
    ),
    uniquePovCount: povRefs.size,
    unitCount: artifact.units.length,
    unitsWithoutPromise: artifact.units
      .filter((unit) => unit.promise_refs.length === 0)
      .map((unit) => unit.unit_ref),
  }
}

export function reorderSectionPlanUnits(
  units: SectionPlanUnitDraft[],
  index: number,
  offset: -1 | 1,
) {
  const target = index + offset
  if (target < 0 || target >= units.length) return units
  const reordered = [...units]
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  return reordered.map((unit, unitIndex) => ({
    ...unit,
    ordinal: unitIndex + 1,
  }))
}

export function formatSectionPlanBudget(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

function parseUnit(value: unknown): SectionPlanUnitDraft | null {
  if (!isRecord(value)) return null
  const textFields = [
    "unit_ref",
    "title",
    "dramatic_job",
    "pov_subject_ref",
    "scene_load",
    "handoff",
  ] as const
  if (
    !textFields.every((field) => typeof value[field] === "string") ||
    !Number.isInteger(value.ordinal) ||
    !Number.isInteger(value.soft_character_budget) ||
    !Array.isArray(value.promise_refs) ||
    !value.promise_refs.every((item) => typeof item === "string")
  )
    return null
  return value as SectionPlanUnitDraft
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}
