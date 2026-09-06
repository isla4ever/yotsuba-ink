export type SceneDeckSceneDraft = {
  scene_ref: string
  heading: string
  location_and_time: string
  cast_subject_refs: string[]
  visible_goal: string
  opposition: string
  outcome: string
  soft_page_target: number
}

export type SceneDeckDraft = {
  scenes: SceneDeckSceneDraft[]
}

export type SceneDeckCastMember = {
  label: string
  ref: string
  role: string
}

export type SceneDeckBeatContext = {
  beatRef: string
  decision: string
  dramaticJob: string
  outcome: string
}

export type SceneDeckReferenceContext = {
  beats: SceneDeckBeatContext[]
  cast: Record<string, SceneDeckCastMember>
}

export type SceneDeckDiagnostics = {
  averagePageTarget: number
  castCoverage: Array<{
    count: number
    ref: string
  }>
  sceneCount: number
  totalPageTarget: number
  unknownCastRefs: string[]
}

type SceneDeckParseResult = {
  artifact: SceneDeckDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export const EMPTY_SCENE_DECK_CONTEXT: SceneDeckReferenceContext = {
  beats: [],
  cast: {},
}

export function parsePhase32SceneDeck(
  payload: Record<string, unknown> | null,
): SceneDeckParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Scene Deck Artifact" }
  if (!Array.isArray(payload.scenes))
    return { artifact: null, error: "场景调度字段不完整" }

  const scenes = payload.scenes.map(parseScene)
  if (scenes.some((scene) => scene === null))
    return { artifact: null, error: "场景字段不完整" }

  const artifact = { scenes: scenes as SceneDeckSceneDraft[] }
  const refs = artifact.scenes.map((scene) => scene.scene_ref)
  const invalid =
    artifact.scenes.length === 0 ||
    artifact.scenes.length > 120 ||
    new Set(refs).size !== refs.length ||
    artifact.scenes.some(
      (scene) =>
        !REF_PATTERN.test(scene.scene_ref) ||
        !nonEmpty(scene.heading) ||
        !nonEmpty(scene.location_and_time) ||
        !nonEmpty(scene.visible_goal) ||
        !nonEmpty(scene.opposition) ||
        !nonEmpty(scene.outcome) ||
        scene.soft_page_target < 0.5 ||
        scene.soft_page_target > 50 ||
        scene.cast_subject_refs.length === 0 ||
        scene.cast_subject_refs.length > 32 ||
        new Set(scene.cast_subject_refs).size !==
          scene.cast_subject_refs.length ||
        scene.cast_subject_refs.some((ref) => !REF_PATTERN.test(ref)),
    )

  return {
    artifact,
    error: invalid
      ? "场景调度存在空字段、无效引用、重复身份或超出数量限制"
      : "",
  }
}

export function extractSceneDeckReferenceContext(
  beatBoardPayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): SceneDeckReferenceContext {
  const beats: SceneDeckBeatContext[] = []
  const beatValues = Array.isArray(beatBoardPayload.beats)
    ? beatBoardPayload.beats
    : []
  for (const beat of beatValues) {
    if (!isRecord(beat) || typeof beat.beat_ref !== "string") continue
    beats.push({
      beatRef: beat.beat_ref,
      decision: textValue(beat.character_decision),
      dramaticJob: textValue(beat.dramatic_job),
      outcome: textValue(beat.outcome),
    })
  }

  const cast: SceneDeckReferenceContext["cast"] = {}
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
      role: textValue(character.role),
    }
  }
  return { beats, cast }
}

export function sceneDeckDiagnostics(
  artifact: SceneDeckDraft,
  context: SceneDeckReferenceContext,
): SceneDeckDiagnostics {
  const castCounts = new Map<string, number>()
  const unknownCastRefs = new Set<string>()
  let totalPageTarget = 0
  for (const scene of artifact.scenes) {
    totalPageTarget += scene.soft_page_target
    for (const ref of scene.cast_subject_refs) {
      castCounts.set(ref, (castCounts.get(ref) ?? 0) + 1)
      if (!context.cast[ref]) unknownCastRefs.add(ref)
    }
  }
  return {
    averagePageTarget: artifact.scenes.length
      ? totalPageTarget / artifact.scenes.length
      : 0,
    castCoverage: Array.from(castCounts, ([ref, count]) => ({
      count,
      ref,
    })).sort(
      (left, right) =>
        right.count - left.count || left.ref.localeCompare(right.ref),
    ),
    sceneCount: artifact.scenes.length,
    totalPageTarget,
    unknownCastRefs: Array.from(unknownCastRefs).sort(),
  }
}

export function reorderSceneDeckScenes(
  scenes: SceneDeckSceneDraft[],
  index: number,
  offset: -1 | 1,
) {
  const target = index + offset
  if (target < 0 || target >= scenes.length) return scenes
  const reordered = [...scenes]
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  return reordered
}

export function formatPageTarget(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function shortSceneRef(value: string) {
  return value.length > 22 ? `${value.slice(0, 19)}...` : value
}

function parseScene(value: unknown): SceneDeckSceneDraft | null {
  if (!isRecord(value)) return null
  const textFields = [
    "scene_ref",
    "heading",
    "location_and_time",
    "visible_goal",
    "opposition",
    "outcome",
  ] as const
  if (
    !textFields.every((field) => typeof value[field] === "string") ||
    !Array.isArray(value.cast_subject_refs) ||
    !value.cast_subject_refs.every((item) => typeof item === "string") ||
    typeof value.soft_page_target !== "number" ||
    !Number.isFinite(value.soft_page_target)
  )
    return null
  return value as SceneDeckSceneDraft
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
