export type LongChapterDraft = {
  chapter_ref: string
  volume_ref: string
  title: string
  pov_subject_ref: string
  content: string
}

export type LongChapterPlan = {
  chapterRef: string
  ordinal: number
  windowRef: string
  windowOrdinal: number
  volumeRef: string
  title: string
  povSubjectRef: string
  castSubjectRefs: string[]
  dramaticJob: string
  entryState: string
  conflict: string
  stakes: string
  exitState: string
  hook: string
  handoff: string
  lengthHint: number
  scenes: Array<{
    sceneRef: string
    location: string
    timeContext: string
    goal: string
    opposition: string
    outcome: string
  }>
}

export type LongChapterContext = {
  chapters: LongChapterPlan[]
  cast: Record<string, {
    displayName: string
    role: string
    voice: string
  }>
  volumes: Record<string, {
    ordinal: number
    partRef: string
    promise: string
    conflict: string
  }>
  parts: Record<string, {
    ordinal: number
    dramaticQuestion: string
    entryState: string
    exitState: string
  }>
  bookPromise: string
}

export const EMPTY_LONG_CHAPTER_CONTEXT: LongChapterContext = {
  bookPromise: "",
  cast: {},
  chapters: [],
  parts: {},
  volumes: {},
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/

export function parsePhase32LongChapter(payload: unknown) {
  if (!isRecord(payload))
    return { artifact: null, error: "章节正文 Artifact 尚未生成" }
  if (
    !isRef(payload.chapter_ref) ||
    !isRef(payload.volume_ref) ||
    !text(payload.title) ||
    !isRef(payload.pov_subject_ref) ||
    typeof payload.content !== "string" ||
    !payload.content.trim()
  )
    return { artifact: null, error: "章节正文 Artifact 字段不完整" }
  return {
    artifact: {
      chapter_ref: String(payload.chapter_ref),
      volume_ref: String(payload.volume_ref),
      title: text(payload.title),
      pov_subject_ref: String(payload.pov_subject_ref),
      content: payload.content,
    } satisfies LongChapterDraft,
    error: "",
  }
}

export function extractLongChapterContext(
  detailPayload: Record<string, unknown>,
  volumesPayload: Record<string, unknown>,
  architecturePayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): LongChapterContext {
  const chapters = (
    Array.isArray(detailPayload.windows) ? detailPayload.windows : []
  ).flatMap((windowValue): LongChapterPlan[] => {
    if (!isRecord(windowValue) || !isRef(windowValue.window_ref)) return []
    const windowRef = String(windowValue.window_ref)
    const windowOrdinal = integer(windowValue.ordinal)
    return (
      Array.isArray(windowValue.chapters) ? windowValue.chapters : []
    ).flatMap((chapterValue): LongChapterPlan[] => {
      if (
        !isRecord(chapterValue) ||
        !isRef(chapterValue.chapter_ref) ||
        !isRef(chapterValue.volume_ref) ||
        !isRef(chapterValue.pov_subject_ref)
      )
        return []
      return [
        {
          castSubjectRefs: refs(chapterValue.cast_subject_refs),
          chapterRef: String(chapterValue.chapter_ref),
          conflict: text(chapterValue.conflict),
          dramaticJob: text(chapterValue.dramatic_job),
          entryState: text(chapterValue.entry_state),
          exitState: text(chapterValue.exit_state),
          handoff: text(chapterValue.handoff),
          hook: text(chapterValue.hook),
          lengthHint: integer(chapterValue.length_hint),
          ordinal: integer(chapterValue.ordinal),
          povSubjectRef: String(chapterValue.pov_subject_ref),
          scenes: (Array.isArray(chapterValue.scenes)
            ? chapterValue.scenes
            : []
          ).flatMap((scene): LongChapterPlan["scenes"] => {
            if (!isRecord(scene) || !isRef(scene.scene_ref)) return []
            return [
              {
                goal: text(scene.goal),
                location: text(scene.location),
                opposition: text(scene.opposition),
                outcome: text(scene.outcome),
                sceneRef: String(scene.scene_ref),
                timeContext: text(scene.time_context),
              },
            ]
          }),
          stakes: text(chapterValue.stakes),
          title: text(chapterValue.title),
          volumeRef: String(chapterValue.volume_ref),
          windowOrdinal,
          windowRef,
        },
      ]
    })
  })
  const volumes = Object.fromEntries(
    (Array.isArray(volumesPayload.volumes)
      ? volumesPayload.volumes
      : []
    ).flatMap(
      (value): Array<[string, LongChapterContext["volumes"][string]]> => {
        if (
          !isRecord(value) ||
          !isRef(value.volume_ref) ||
          !isRef(value.part_ref)
        )
          return []
        return [
          [
            String(value.volume_ref),
            {
              conflict: text(value.conflict),
              ordinal: integer(value.ordinal),
              partRef: String(value.part_ref),
              promise: text(value.promise),
            },
          ],
        ]
      },
    ),
  )
  const parts = Object.fromEntries(
    (Array.isArray(architecturePayload.parts)
      ? architecturePayload.parts
      : []
    ).flatMap((value): Array<[string, LongChapterContext["parts"][string]]> => {
      if (!isRecord(value) || !isRef(value.part_ref)) return []
      return [
        [
          String(value.part_ref),
          {
            dramaticQuestion: text(value.dramatic_question),
            entryState: text(value.entry_state),
            exitState: text(value.exit_state),
            ordinal: integer(value.ordinal),
          },
        ],
      ]
    }),
  )
  const cast = Object.fromEntries(
    (Array.isArray(castPayload.characters)
      ? castPayload.characters
      : []
    ).flatMap((value): Array<[string, LongChapterContext["cast"][string]]> => {
      if (!isRecord(value) || !isRef(value.subject_ref)) return []
      return [
        [
          String(value.subject_ref),
          {
            displayName: text(value.display_name) || String(value.subject_ref),
            role: text(value.role),
            voice: text(value.voice),
          },
        ],
      ]
    }),
  )
  return {
    bookPromise: text(architecturePayload.book_promise),
    cast,
    chapters,
    parts,
    volumes,
  }
}

export function longChapterContractError(
  artifact: LongChapterDraft | null,
  context: LongChapterContext,
  expectedChapterRef: string,
) {
  if (!artifact) return "当前章尚无可确认的正文"
  const plan = context.chapters.find(
    (chapter) => chapter.chapterRef === artifact.chapter_ref,
  )
  if (!plan || artifact.chapter_ref !== expectedChapterRef)
    return "当前正文不在冻结的章节游标中"
  if (artifact.volume_ref !== plan.volumeRef) return "正文卷册身份与细纲不一致"
  if (artifact.title !== plan.title) return "正文标题必须与冻结细纲一致"
  if (artifact.pov_subject_ref !== plan.povSubjectRef)
    return "正文 POV 必须与冻结细纲一致"
  if (!context.cast[artifact.pov_subject_ref])
    return "正文 POV 必须来自已确认人物名册"
  return ""
}

export function longChapterDiagnostics(
  artifact: LongChapterDraft,
  plan?: LongChapterPlan,
) {
  const characterCount = artifact.content.replace(/\s/g, "").length
  return {
    budgetRatio: plan?.lengthHint ? characterCount / plan.lengthHint : 0,
    characterCount,
    paragraphCount: longChapterParagraphs(artifact.content).length,
  }
}

export function longChapterParagraphs(content: string) {
  return content
    .split(/\n\s*\n|\n/g)
    .map((value) => value.trim())
    .filter(Boolean)
}

function refs(value: unknown) {
  return Array.isArray(value) ? value.filter(isRef) : []
}

function integer(value: unknown) {
  return Number.isInteger(value) ? Number(value) : 0
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
