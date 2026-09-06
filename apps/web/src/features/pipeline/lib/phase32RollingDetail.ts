export type RollingDetailSceneDraft = {
  scene_ref: string
  ordinal: number
  location: string
  time_context: string
  cast_subject_refs: string[]
  goal: string
  opposition: string
  outcome: string
}

export type RollingDetailChapterDraft = {
  chapter_ref: string
  ordinal: number
  volume_ref: string
  title: string
  pov_subject_ref: string
  cast_subject_refs: string[]
  dramatic_job: string
  entry_state: string
  scenes: RollingDetailSceneDraft[]
  conflict: string
  stakes: string
  exit_state: string
  hook: string
  handoff: string
  length_hint: number
}

export type RollingDetailWindowDraft = {
  window_ref: string
  ordinal: number
  volume_refs: string[]
  chapters: RollingDetailChapterDraft[]
  entry_state: string
  handoff: string
  next_window_entry_state: string
}

export type RollingDetailDraft = {
  windows: RollingDetailWindowDraft[]
}

export type RollingDetailReferenceLabel = {
  label: string
  ref: string
}

export type RollingDetailReferenceContext = {
  cast: Record<string, RollingDetailReferenceLabel>
  volumes: Record<string, RollingDetailReferenceLabel>
  volumeCast: Record<string, string[]>
}

export type RollingDetailDiagnostics = {
  chapterCount: number
  sceneCount: number
  totalLengthHint: number
  volumeCoverage: Array<{
    chapterCount: number
    lengthHint: number
    volumeRef: string
  }>
  windowCount: number
}

type RollingDetailParseResult = {
  artifact: RollingDetailDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32RollingDetail(
  payload: Record<string, unknown> | null,
): RollingDetailParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Rolling Detail Artifact" }
  if (!Array.isArray(payload.windows))
    return { artifact: null, error: "滚动细纲聚合字段不完整" }

  const windows = payload.windows.map(parseWindow)
  if (windows.some((window) => window === null))
    return { artifact: null, error: "Window、章节或场景施工字段不完整" }

  const artifact = { windows: windows as RollingDetailWindowDraft[] }
  const chapters = artifact.windows.flatMap((window) => window.chapters)
  const scenes = chapters.flatMap((chapter) => chapter.scenes)
  const invalid =
    artifact.windows.length === 0 ||
    artifact.windows.length > 24 ||
    !unique(artifact.windows.map((window) => window.window_ref)) ||
    artifact.windows.some((window, index) => !validWindow(window, index)) ||
    !unique(chapters.map((chapter) => chapter.chapter_ref)) ||
    chapters.some((chapter, index) => chapter.ordinal !== index + 1) ||
    !unique(scenes.map((scene) => scene.scene_ref))

  return {
    artifact,
    error: invalid ? "滚动细纲存在空字段、无效引用、重复身份或顺序漂移" : "",
  }
}

export function extractRollingDetailReferenceContext(
  volumesPayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): RollingDetailReferenceContext {
  const volumes: RollingDetailReferenceContext["volumes"] = {}
  const cast: RollingDetailReferenceContext["cast"] = {}
  const volumeCast: RollingDetailReferenceContext["volumeCast"] = {}
  const volumeValues = Array.isArray(volumesPayload.volumes)
    ? volumesPayload.volumes
    : []
  const characterValues = Array.isArray(castPayload.characters)
    ? castPayload.characters
    : []

  for (const [index, value] of volumeValues.entries()) {
    if (!isRecord(value) || typeof value.volume_ref !== "string") continue
    const promise =
      typeof value.promise === "string" ? value.promise.trim() : ""
    volumes[value.volume_ref] = {
      ref: value.volume_ref,
      label: `卷 ${String(index + 1).padStart(2, "0")}${
        promise ? ` · ${promise}` : ""
      }`,
    }
    volumeCast[value.volume_ref] = Array.isArray(value.cast_subject_refs)
      ? value.cast_subject_refs.filter(
          (subjectRef): subjectRef is string => typeof subjectRef === "string",
        )
      : []
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
  return { cast, volumes, volumeCast }
}

export function rollingDetailDiagnostics(
  artifact: RollingDetailDraft,
): RollingDetailDiagnostics {
  const coverage = new Map<string, {
    chapterCount: number
    lengthHint: number
  }>()
  const chapters = artifact.windows.flatMap((window) => window.chapters)
  for (const chapter of chapters) {
    const current = coverage.get(chapter.volume_ref) ?? {
      chapterCount: 0,
      lengthHint: 0,
    }
    current.chapterCount += 1
    current.lengthHint += chapter.length_hint
    coverage.set(chapter.volume_ref, current)
  }
  return {
    chapterCount: chapters.length,
    sceneCount: chapters.reduce(
      (total, chapter) => total + chapter.scenes.length,
      0,
    ),
    totalLengthHint: chapters.reduce(
      (total, chapter) => total + chapter.length_hint,
      0,
    ),
    volumeCoverage: Array.from(coverage, ([volumeRef, value]) => ({
      volumeRef,
      ...value,
    })),
    windowCount: artifact.windows.length,
  }
}

export function reorderDetailChapters(
  artifact: RollingDetailDraft,
  windowRef: string,
  chapterIndex: number,
  offset: -1 | 1,
) {
  const windows = artifact.windows.map((window) => {
    if (window.window_ref !== windowRef) return window
    const target = chapterIndex + offset
    if (target < 0 || target >= window.chapters.length) return window
    const chapters = [...window.chapters]
    ;[chapters[chapterIndex], chapters[target]] = [
      chapters[target],
      chapters[chapterIndex],
    ]
    return { ...window, chapters }
  })
  let ordinal = 0
  return {
    windows: windows.map((window) => ({
      ...window,
      chapters: window.chapters.map((chapter) => ({
        ...chapter,
        ordinal: ++ordinal,
      })),
    })),
  }
}

export function reorderDetailScenes(
  scenes: RollingDetailSceneDraft[],
  sceneIndex: number,
  offset: -1 | 1,
) {
  const target = sceneIndex + offset
  if (target < 0 || target >= scenes.length) return scenes
  const reordered = [...scenes]
  ;[reordered[sceneIndex], reordered[target]] = [
    reordered[target],
    reordered[sceneIndex],
  ]
  return reordered.map((scene, index) => ({ ...scene, ordinal: index + 1 }))
}

export function formatRollingDetailCount(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

function parseWindow(value: unknown): RollingDetailWindowDraft | null {
  if (
    !isRecord(value) ||
    !Array.isArray(value.volume_refs) ||
    !Array.isArray(value.chapters)
  )
    return null
  const chapters = value.chapters.map(parseChapter)
  if (
    chapters.some((chapter) => chapter === null) ||
    !value.volume_refs.every((ref) => typeof ref === "string")
  )
    return null
  const strings = [
    "window_ref",
    "entry_state",
    "handoff",
    "next_window_entry_state",
  ]
  if (
    !strings.every((field) => typeof value[field] === "string") ||
    !Number.isInteger(value.ordinal)
  )
    return null
  return { ...value, chapters } as RollingDetailWindowDraft
}

function parseChapter(value: unknown): RollingDetailChapterDraft | null {
  if (
    !isRecord(value) ||
    !Array.isArray(value.cast_subject_refs) ||
    !Array.isArray(value.scenes)
  )
    return null
  const scenes = value.scenes.map(parseScene)
  const strings = [
    "chapter_ref",
    "volume_ref",
    "title",
    "pov_subject_ref",
    "dramatic_job",
    "entry_state",
    "conflict",
    "stakes",
    "exit_state",
    "hook",
    "handoff",
  ]
  if (
    scenes.some((scene) => scene === null) ||
    !value.cast_subject_refs.every((ref) => typeof ref === "string") ||
    !strings.every((field) => typeof value[field] === "string") ||
    !Number.isInteger(value.ordinal) ||
    !Number.isInteger(value.length_hint)
  )
    return null
  return { ...value, scenes } as RollingDetailChapterDraft
}

function parseScene(value: unknown): RollingDetailSceneDraft | null {
  if (!isRecord(value) || !Array.isArray(value.cast_subject_refs)) return null
  const strings = [
    "scene_ref",
    "location",
    "time_context",
    "goal",
    "opposition",
    "outcome",
  ]
  if (
    !value.cast_subject_refs.every((ref) => typeof ref === "string") ||
    !strings.every((field) => typeof value[field] === "string") ||
    !Number.isInteger(value.ordinal)
  )
    return null
  return value as RollingDetailSceneDraft
}

function validWindow(window: RollingDetailWindowDraft, index: number) {
  const volumeSet = new Set(window.volume_refs)
  return (
    REF_PATTERN.test(window.window_ref) &&
    window.ordinal === index + 1 &&
    window.volume_refs.length >= 1 &&
    window.volume_refs.length <= 3 &&
    unique(window.volume_refs) &&
    window.volume_refs.every((ref) => REF_PATTERN.test(ref)) &&
    window.chapters.length >= 1 &&
    window.chapters.length <= 40 &&
    nonEmpty(window.entry_state) &&
    nonEmpty(window.handoff) &&
    nonEmpty(window.next_window_entry_state) &&
    setsEqual(
      volumeSet,
      new Set(window.chapters.map((chapter) => chapter.volume_ref)),
    ) &&
    window.chapters.every(validChapter)
  )
}

function validChapter(chapter: RollingDetailChapterDraft) {
  const castSet = new Set(chapter.cast_subject_refs)
  return (
    REF_PATTERN.test(chapter.chapter_ref) &&
    REF_PATTERN.test(chapter.volume_ref) &&
    REF_PATTERN.test(chapter.pov_subject_ref) &&
    chapter.cast_subject_refs.length >= 1 &&
    chapter.cast_subject_refs.length <= 64 &&
    unique(chapter.cast_subject_refs) &&
    castSet.has(chapter.pov_subject_ref) &&
    chapter.cast_subject_refs.every((ref) => REF_PATTERN.test(ref)) &&
    [
      chapter.title,
      chapter.dramatic_job,
      chapter.entry_state,
      chapter.conflict,
      chapter.stakes,
      chapter.exit_state,
      chapter.hook,
      chapter.handoff,
    ].every(nonEmpty) &&
    chapter.scenes.length >= 1 &&
    chapter.scenes.length <= 32 &&
    unique(chapter.scenes.map((scene) => scene.scene_ref)) &&
    chapter.scenes.every((scene, index) => validScene(scene, index, castSet)) &&
    chapter.length_hint >= 100 &&
    chapter.length_hint <= 100_000
  )
}

function validScene(
  scene: RollingDetailSceneDraft,
  index: number,
  chapterCast: Set<string>,
) {
  return (
    REF_PATTERN.test(scene.scene_ref) &&
    scene.ordinal === index + 1 &&
    scene.cast_subject_refs.length >= 1 &&
    scene.cast_subject_refs.length <= 32 &&
    unique(scene.cast_subject_refs) &&
    scene.cast_subject_refs.every(
      (ref) => REF_PATTERN.test(ref) && chapterCast.has(ref),
    ) &&
    [
      scene.location,
      scene.time_context,
      scene.goal,
      scene.opposition,
      scene.outcome,
    ].every(nonEmpty)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}

function setsEqual(left: Set<string>, right: Set<string>) {
  return (
    left.size === right.size &&
    Array.from(left).every((item) => right.has(item))
  )
}

function unique(values: string[]) {
  return new Set(values).size === values.length
}
