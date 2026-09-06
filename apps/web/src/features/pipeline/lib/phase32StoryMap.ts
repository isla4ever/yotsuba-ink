export type StoryMapAnchorDraft = {
  anchor_ref: string
  dramatic_job: string
  pressure: string
  choice_or_revelation: string
  consequence_or_open_effect: string
  promise_refs: string[]
}

export type StoryMapDraft = {
  opening_state: string
  story_question: string
  anchors: StoryMapAnchorDraft[]
  ending_state: string
  open_questions: string[]
}

export type StoryMapDiagnostics = {
  anchorCount: number
  anchorsWithoutPromise: string[]
  openQuestionCount: number
  promiseRefs: string[]
}

type StoryMapParseResult = {
  artifact: StoryMapDraft | null
  error: string
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32StoryMap(
  payload: Record<string, unknown> | null,
): StoryMapParseResult {
  if (!payload)
    return { artifact: null, error: "当前阶段尚无 Story Map Artifact" }
  if (
    typeof payload.opening_state !== "string" ||
    typeof payload.story_question !== "string" ||
    typeof payload.ending_state !== "string" ||
    !Array.isArray(payload.anchors) ||
    !Array.isArray(payload.open_questions) ||
    !payload.open_questions.every((item) => typeof item === "string")
  )
    return { artifact: null, error: "故事地图字段不完整" }

  const anchors = payload.anchors.map(parseAnchor)
  if (anchors.some((anchor) => anchor === null))
    return { artifact: null, error: "故事锚点字段不完整" }

  const artifact: StoryMapDraft = {
    opening_state: payload.opening_state,
    story_question: payload.story_question,
    anchors: anchors as StoryMapAnchorDraft[],
    ending_state: payload.ending_state,
    open_questions: payload.open_questions as string[],
  }
  const anchorRefs = artifact.anchors.map((anchor) => anchor.anchor_ref)
  const invalid =
    !nonEmpty(artifact.opening_state) ||
    !nonEmpty(artifact.story_question) ||
    !nonEmpty(artifact.ending_state) ||
    artifact.anchors.length === 0 ||
    artifact.anchors.length > 120 ||
    artifact.anchors.some(
      (anchor) =>
        !REF_PATTERN.test(anchor.anchor_ref) ||
        !nonEmpty(anchor.dramatic_job) ||
        !nonEmpty(anchor.pressure) ||
        !nonEmpty(anchor.choice_or_revelation) ||
        !nonEmpty(anchor.consequence_or_open_effect) ||
        anchor.promise_refs.some((ref) => !REF_PATTERN.test(ref)),
    ) ||
    new Set(anchorRefs).size !== anchorRefs.length ||
    artifact.open_questions.some((item) => !nonEmpty(item))

  return {
    artifact,
    error: invalid ? "故事地图存在空字段、无效引用或重复锚点" : "",
  }
}

export function storyMapDiagnostics(
  artifact: StoryMapDraft,
): StoryMapDiagnostics {
  return {
    anchorCount: artifact.anchors.length,
    anchorsWithoutPromise: artifact.anchors
      .filter((anchor) => anchor.promise_refs.length === 0)
      .map((anchor) => anchor.anchor_ref),
    openQuestionCount: artifact.open_questions.length,
    promiseRefs: Array.from(
      new Set(artifact.anchors.flatMap((anchor) => anchor.promise_refs)),
    ),
  }
}

export function splitStoryMapLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
}

function parseAnchor(value: unknown): StoryMapAnchorDraft | null {
  if (!isRecord(value)) return null
  const fields = [
    "anchor_ref",
    "dramatic_job",
    "pressure",
    "choice_or_revelation",
    "consequence_or_open_effect",
  ] as const
  if (
    !fields.every((field) => typeof value[field] === "string") ||
    !Array.isArray(value.promise_refs) ||
    !value.promise_refs.every((item) => typeof item === "string")
  )
    return null
  return value as StoryMapAnchorDraft
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmpty(value: string) {
  return Boolean(value.trim())
}
