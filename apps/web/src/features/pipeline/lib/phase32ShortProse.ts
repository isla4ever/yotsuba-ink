export type ShortProseUnitKind = "section" | "chapter"

export type ShortProseDraft = {
  unit_ref: string
  unit_kind: ShortProseUnitKind
  title: string
  pov_subject_ref: string
  content: string
}

export type ShortProsePlanUnit = {
  unitRef: string
  ordinal: number
  title: string
  dramaticJob: string
  povSubjectRef: string
  sceneLoad: string
  handoff: string
  softCharacterBudget: number
  promiseRefs: string[]
}

export type ShortProseCastMember = {
  ref: string
  displayName: string
  role: string
  voice: string
}

export type ShortProseStoryAnchor = {
  anchorRef: string
  dramaticJob: string
  pressure: string
  consequence: string
  promiseRefs: string[]
}

export type ShortProseReferenceContext = {
  cast: Record<string, ShortProseCastMember>
  storyQuestion: string
  units: ShortProsePlanUnit[]
  anchors: ShortProseStoryAnchor[]
}

export const EMPTY_SHORT_PROSE_CONTEXT: ShortProseReferenceContext = {
  cast: {},
  storyQuestion: "",
  units: [],
  anchors: [],
}

const REF_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$/

export function parsePhase32ShortProse(
  payload: unknown,
): {
  artifact: ShortProseDraft | null
  error: string
} {
  if (!isRecord(payload))
    return { artifact: null, error: "正文 Artifact 尚未生成" }
  if (
    !isRef(payload.unit_ref) ||
    !["section", "chapter"].includes(String(payload.unit_kind)) ||
    !text(payload.title) ||
    !isRef(payload.pov_subject_ref) ||
    typeof payload.content !== "string" ||
    !payload.content.trim()
  )
    return { artifact: null, error: "正文 Artifact 字段不完整" }
  return {
    artifact: {
      unit_ref: String(payload.unit_ref),
      unit_kind: payload.unit_kind as ShortProseUnitKind,
      title: text(payload.title),
      pov_subject_ref: String(payload.pov_subject_ref),
      content: payload.content,
    },
    error: "",
  }
}

export function extractShortProseReferenceContext(
  sectionPlanPayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
  storyMapPayload: Record<string, unknown>,
): ShortProseReferenceContext {
  const units = (
    Array.isArray(sectionPlanPayload.units) ? sectionPlanPayload.units : []
  ).flatMap((value): ShortProsePlanUnit[] => {
    if (
      !isRecord(value) ||
      !isRef(value.unit_ref) ||
      !Number.isInteger(value.ordinal) ||
      !text(value.title) ||
      !isRef(value.pov_subject_ref) ||
      !Number.isInteger(value.soft_character_budget)
    )
      return []
    return [
      {
        unitRef: String(value.unit_ref),
        ordinal: Number(value.ordinal),
        title: text(value.title),
        dramaticJob: text(value.dramatic_job),
        povSubjectRef: String(value.pov_subject_ref),
        sceneLoad: text(value.scene_load),
        handoff: text(value.handoff),
        softCharacterBudget: Number(value.soft_character_budget),
        promiseRefs: Array.isArray(value.promise_refs)
          ? value.promise_refs.filter(isRef)
          : [],
      },
    ]
  })
  const cast = Object.fromEntries(
    (Array.isArray(castPayload.characters)
      ? castPayload.characters
      : []
    ).flatMap((value): Array<[string, ShortProseCastMember]> => {
      if (!isRecord(value) || !isRef(value.subject_ref)) return []
      const ref = String(value.subject_ref)
      return [
        [
          ref,
          {
            ref,
            displayName: text(value.display_name) || ref,
            role: text(value.role),
            voice: text(value.voice),
          },
        ],
      ]
    }),
  )
  const anchors = (
    Array.isArray(storyMapPayload.anchors) ? storyMapPayload.anchors : []
  ).flatMap((value): ShortProseStoryAnchor[] => {
    if (!isRecord(value) || !isRef(value.anchor_ref)) return []
    return [
      {
        anchorRef: String(value.anchor_ref),
        dramaticJob: text(value.dramatic_job),
        pressure: text(value.pressure),
        consequence: text(value.consequence_or_open_effect),
        promiseRefs: Array.isArray(value.promise_refs)
          ? value.promise_refs.filter(isRef)
          : [],
      },
    ]
  })
  return {
    anchors,
    cast,
    storyQuestion: text(storyMapPayload.story_question),
    units,
  }
}

export function shortProseContractError(
  artifact: ShortProseDraft | null,
  context: ShortProseReferenceContext,
  expectedUnitRef: string,
  expectedUnitKind: ShortProseUnitKind,
) {
  if (!artifact) return "当前单元尚无可确认的正文"
  const plan = context.units.find((unit) => unit.unitRef === artifact.unit_ref)
  if (!plan || artifact.unit_ref !== expectedUnitRef)
    return "当前正文身份不在冻结的单元游标中"
  if (artifact.unit_kind !== expectedUnitKind)
    return "正文单元类型与冻结篇幅投影不一致"
  if (artifact.title !== plan.title) return "正文标题必须与冻结单元计划一致"
  if (artifact.pov_subject_ref !== plan.povSubjectRef)
    return "正文 POV 必须与冻结单元计划一致"
  if (!context.cast[artifact.pov_subject_ref])
    return "正文 POV 必须来自已确认人物名册"
  return ""
}

export function projectShortProseUnitKind(
  scaleProfile: Record<string, unknown>,
): ShortProseUnitKind {
  const target = Number(scaleProfile.target)
  const ceiling = Number(scaleProfile.recommended_ceiling || 30_000)
  return target > ceiling ? "chapter" : "section"
}

export function shortProseDiagnostics(
  artifact: ShortProseDraft,
  context: ShortProseReferenceContext,
) {
  const plan = context.units.find((unit) => unit.unitRef === artifact.unit_ref)
  const characterCount = artifact.content.replace(/\s/g, "").length
  return {
    budgetRatio: plan?.softCharacterBudget
      ? characterCount / plan.softCharacterBudget
      : 0,
    characterCount,
    paragraphCount: shortProseParagraphs(artifact.content).length,
  }
}

export function shortProseParagraphs(content: string) {
  const blocks = content
    .split(/\n\s*\n/g)
    .map((value) => value.trim())
    .filter(Boolean)
  if (blocks.length > 1) return blocks
  return content
    .split(/\n/g)
    .map((value) => value.trim())
    .filter(Boolean)
}

export function relatedShortProseAnchors(
  unit: ShortProsePlanUnit | undefined,
  anchors: ShortProseStoryAnchor[],
) {
  if (!unit?.promiseRefs.length) return []
  const refs = new Set(unit.promiseRefs)
  return anchors.filter((anchor) =>
    anchor.promiseRefs.some((promiseRef) => refs.has(promiseRef)),
  )
}

export function formatShortProseCharacters(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

export function shortProseUnitLabel(kind: ShortProseUnitKind) {
  return kind === "chapter" ? "章节" : "段落单元"
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function isRef(value: unknown): value is string {
  return typeof value === "string" && REF_PATTERN.test(value)
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}
