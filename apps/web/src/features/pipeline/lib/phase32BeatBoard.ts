export type BeatBoardBeatDraft = {
  beat_ref: string
  dramatic_job: string
  visible_pressure: string
  character_decision: string
  outcome: string
  setup_or_payoff_refs: string[]
  timing_hint: string
}

export type BeatBoardDraft = {
  beats: BeatBoardBeatDraft[]
}

export type BeatBoardBriefContext = {
  audiencePromise: string
  endingEffect: string
  sampleType: string
  targetMinutes: number | null
  tone: string
  visibleConflict: string
}

export type BeatBoardCastMember = {
  label: string
  ref: string
  role: string
}

export type BeatBoardReferenceContext = {
  brief: BeatBoardBriefContext
  cast: Record<string, BeatBoardCastMember>
}

export type BeatBoardDiagnostics = {
  beatCount: number
  beatsWithoutReference: string[]
  referenceCoverage: Array<{
    beatRefs: string[]
    reference: string
  }>
  uniqueReferenceCount: number
}

type BeatBoardParseResult = {
  artifact: BeatBoardDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export const EMPTY_BEAT_BOARD_CONTEXT: BeatBoardReferenceContext = {
  brief: {
    audiencePromise: "",
    endingEffect: "",
    sampleType: "",
    targetMinutes: null,
    tone: "",
    visibleConflict: "",
  },
  cast: {},
}

export function parsePhase32BeatBoard(
  payload: Record<string, unknown> | null,
): BeatBoardParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Beat Board Artifact" }
  if (!Array.isArray(payload.beats))
    return { artifact: null, error: "因果节拍字段不完整" }

  const beats = payload.beats.map(parseBeat)
  if (beats.some((beat) => beat === null))
    return { artifact: null, error: "节拍字段不完整" }

  const artifact = { beats: beats as BeatBoardBeatDraft[] }
  const refs = artifact.beats.map((beat) => beat.beat_ref)
  const invalid =
    artifact.beats.length === 0 ||
    artifact.beats.length > 120 ||
    new Set(refs).size !== refs.length ||
    artifact.beats.some(
      (beat) =>
        !REF_PATTERN.test(beat.beat_ref) ||
        !nonEmpty(beat.dramatic_job) ||
        !nonEmpty(beat.visible_pressure) ||
        !nonEmpty(beat.character_decision) ||
        !nonEmpty(beat.outcome) ||
        !nonEmpty(beat.timing_hint) ||
        beat.setup_or_payoff_refs.length > 24 ||
        beat.setup_or_payoff_refs.some((ref) => !REF_PATTERN.test(ref)),
    )

  return {
    artifact,
    error: invalid
      ? "因果节拍存在空字段、无效引用、重复身份或超出数量限制"
      : "",
  }
}

export function extractBeatBoardReferenceContext(
  briefPayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): BeatBoardReferenceContext {
  const cast: BeatBoardReferenceContext["cast"] = {}
  const characters = Array.isArray(castPayload.characters)
    ? castPayload.characters
    : []
  for (const character of characters) {
    if (
      !isRecord(character) ||
      typeof character.subject_ref !== "string" ||
      typeof character.display_name !== "string"
    )
      continue
    cast[character.subject_ref] = {
      label: character.display_name,
      ref: character.subject_ref,
      role: typeof character.role === "string" ? character.role : "",
    }
  }
  return {
    brief: {
      audiencePromise: textValue(briefPayload.audience_promise),
      endingEffect: textValue(briefPayload.ending_effect),
      sampleType: textValue(briefPayload.sample_type),
      targetMinutes: Number.isInteger(briefPayload.target_minutes)
        ? Number(briefPayload.target_minutes)
        : null,
      tone: textValue(briefPayload.tone),
      visibleConflict: textValue(briefPayload.visible_conflict),
    },
    cast,
  }
}

export function beatBoardDiagnostics(
  artifact: BeatBoardDraft,
): BeatBoardDiagnostics {
  const coverage = new Map<string, string[]>()
  for (const beat of artifact.beats) {
    for (const reference of new Set(beat.setup_or_payoff_refs)) {
      const beatRefs = coverage.get(reference) ?? []
      beatRefs.push(beat.beat_ref)
      coverage.set(reference, beatRefs)
    }
  }
  return {
    beatCount: artifact.beats.length,
    beatsWithoutReference: artifact.beats
      .filter((beat) => beat.setup_or_payoff_refs.length === 0)
      .map((beat) => beat.beat_ref),
    referenceCoverage: Array.from(coverage, ([reference, beatRefs]) => ({
      beatRefs,
      reference,
    })),
    uniqueReferenceCount: coverage.size,
  }
}

export function reorderBeatBoardBeats(
  beats: BeatBoardBeatDraft[],
  index: number,
  offset: -1 | 1,
) {
  const target = index + offset
  if (target < 0 || target >= beats.length) return beats
  const reordered = [...beats]
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  return reordered
}

export function normalizeBeatBoardReferences(value: string) {
  return Array.from(
    new Set(
      value
        .split(/[\s,，]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  )
}

export function shortBeatRef(value: string) {
  return value.length > 22 ? `${value.slice(0, 19)}...` : value
}

function parseBeat(value: unknown): BeatBoardBeatDraft | null {
  if (!isRecord(value)) return null
  const textFields = [
    "beat_ref",
    "dramatic_job",
    "visible_pressure",
    "character_decision",
    "outcome",
    "timing_hint",
  ] as const
  if (
    !textFields.every((field) => typeof value[field] === "string") ||
    !Array.isArray(value.setup_or_payoff_refs) ||
    !value.setup_or_payoff_refs.every((item) => typeof item === "string")
  )
    return null
  return value as BeatBoardBeatDraft
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}

function textValue(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}
