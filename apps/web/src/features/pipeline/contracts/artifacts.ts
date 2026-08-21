export type StoryBriefArtifact = {
  title: string
  premise: string
  promise: string
  world_rules: string[]
  theme: string
  ending_promise: string
  voice: string
  length_envelope: {
    word_target_soft: number
  }
}

export type StoryProgressType = "information" | "relationship" | "external" | "internal"
export type StoryMilestone = "inciting" | "commitment" | "midpoint_reversal" | "crisis" | "climax" | "aftermath"

export type StorySpineTurn = {
  id: `turn-${number}`
  cause: string
  change: string
  progress_type: StoryProgressType
  milestones: StoryMilestone[]
}

export type StorySpineArtifact = {
  turns: StorySpineTurn[]
  ending: string
  open_questions: string[]
  progress_types: StoryProgressType[]
}

export type CharacterKind = "protagonist" | "major" | "functional" | "npc" | "historical_record"

export type CharacterSubject = {
  id: string
  name: string
  kind: CharacterKind
  function: string
  background: string
  conflict_history: string
  present_stakes: string
  temperament: string
  speech_style: string
  drive: string
  change: string
  debut: string
  limits: string[]
  demand_refs: string[]
}

export type CharacterRelation = {
  a: string
  b: string
  type: string
  pressure: string
}

export type CharacterBibleArtifact = {
  subjects: CharacterSubject[]
  relations: CharacterRelation[]
}

export type VolumeLengthHint = "short" | "medium" | "long"

export type VolumeContract = {
  id: `volume-${number}`
  title: string
  promise: string
  conflict: string
  climax: string
  climax_turn_ref: `turn-${number}`
  closure: string
  turn_refs: Array<`turn-${number}`>
  cast_ids: string[]
  length_hint: VolumeLengthHint
}

export type VolumeArchitectureArtifact = {
  volumes: VolumeContract[]
}

export type DetailScene = {
  place: string
  objective: string
  conflict: string
  turn: string
  result: string
}

export type DetailChapter = {
  ref: `chapter-${number}`
  volume_ref: `volume-${number}`
  title: string
  target_characters: number | null
  turn_refs: Array<`turn-${number}`>
  purpose: string
  pov: string
  cast_ids: string[]
  scenes: DetailScene[]
  handoff: string
}

export type DetailArtifact = {
  chapters: DetailChapter[]
}

export type ChapterArtifact = {
  chapter_id: `chapter-${number}`
  version_id: string
  title: string
  content: string
  author_status: "candidate" | "accepted" | "edited" | "branched"
}

export type ArtifactParseResult<T,> = {
  artifact: T | null
  error: string
}

export function parseStoryBriefArtifact(
  value: unknown,
): ArtifactParseResult<StoryBriefArtifact> {
  if (!isRecord(value)) return invalid("Story Brief 不是有效对象")
  const expected = [
    "title",
    "premise",
    "promise",
    "world_rules",
    "theme",
    "ending_promise",
    "voice",
    "length_envelope",
  ]
  const unknown = Object.keys(value).filter((key) => !expected.includes(key))
  if (unknown.length)
    return invalid(`Story Brief 包含未支持字段：${unknown.join("、")}`)
  const textFields = [
    "title",
    "premise",
    "promise",
    "theme",
    "ending_promise",
    "voice",
  ] as const
  for (const field of textFields) {
    if (typeof value[field] !== "string" || !value[field].trim())
      return invalid(`${field} 必须是非空文本`)
  }
  if (
    !Array.isArray(value.world_rules) ||
    value.world_rules.length === 0 ||
    value.world_rules.some((item) => typeof item !== "string" || !item.trim())
  ) {
    return invalid("world_rules 至少包含一条有效世界规则")
  }
  if (!isRecord(value.length_envelope))
    return invalid("length_envelope 不是有效对象")
  const wordTarget = value.length_envelope.word_target_soft
  if (
    typeof wordTarget !== "number" ||
    !Number.isInteger(wordTarget) ||
    wordTarget < 1
  ) {
    return invalid("word_target_soft 必须是正整数")
  }
  return { artifact: value as StoryBriefArtifact, error: "" }
}

export function parseStorySpineArtifact(
  value: unknown,
): ArtifactParseResult<StorySpineArtifact> {
  if (!isRecord(value)) return invalid("Story Spine 不是有效对象")
  const expected = ["turns", "ending", "open_questions", "progress_types"]
  const unknown = Object.keys(value).filter((key) => !expected.includes(key))
  if (unknown.length)
    return invalid(`Story Spine 包含未支持字段：${unknown.join("、")}`)
  if (!Array.isArray(value.turns) || value.turns.length === 0)
    return invalid("turns 至少包含一个因果转折")
  const turns: StorySpineTurn[] = []
  for (let index = 0; index < value.turns.length; index += 1) {
    const turn = value.turns[index]
    if (!isRecord(turn)) return invalid(`turn-${index + 1} 不是有效对象`)
    const turnExpected = [
      "id",
      "cause",
      "change",
      "progress_type",
      "milestones",
    ]
    const turnUnknown = Object.keys(turn).filter(
      (key) => !turnExpected.includes(key),
    )
    if (turnUnknown.length)
      return invalid(
        `turn-${index + 1} 包含未支持字段：${turnUnknown.join("、")}`,
      )
    if (turn.id !== `turn-${index + 1}`)
      return invalid(`turns 必须按 turn-1 起连续编号`)
    if (!nonEmptyText(turn.cause) || !nonEmptyText(turn.change))
      return invalid(`${turn.id} 的 cause/change 必须是非空文本`)
    if (!isProgressType(turn.progress_type))
      return invalid(`${turn.id} 的 progress_type 无效`)
    if (
      !Array.isArray(turn.milestones) ||
      turn.milestones.some((item) => !isMilestone(item))
    ) {
      return invalid(`${turn.id} 的 milestones 无效`)
    }
    turns.push(turn as StorySpineTurn)
  }
  if (!nonEmptyText(value.ending)) return invalid("ending 必须是非空文本")
  if (!validTextList(value.open_questions))
    return invalid("open_questions 必须是有效文本列表")
  if (
    !Array.isArray(value.progress_types) ||
    value.progress_types.some((item) => !isProgressType(item))
  ) {
    return invalid("progress_types 包含无效推进类型")
  }
  const declaredProgressTypes = value.progress_types as StoryProgressType[]
  const progressTypes = Array.from(
    new Set(turns.map((turn) => turn.progress_type)),
  )
  if (progressTypes.some((type) => !declaredProgressTypes.includes(type))) {
    return invalid("progress_types 必须覆盖 turns 中使用的全部推进类型")
  }
  return { artifact: value as StorySpineArtifact, error: "" }
}

export function parseCharacterBibleArtifact(
  value: unknown,
): ArtifactParseResult<CharacterBibleArtifact> {
  if (!isRecord(value)) return invalid("Character Bible 不是有效对象")
  const topLevelError = exactKeyError(
    value,
    ["subjects", "relations"],
    "Character Bible",
  )
  if (topLevelError) return invalid(topLevelError)
  if (!Array.isArray(value.subjects) || value.subjects.length === 0)
    return invalid("subjects 至少包含一个登记主体")
  if (!Array.isArray(value.relations)) return invalid("relations 必须是数组")

  const subjects: CharacterSubject[] = []
  const subjectIds = new Set<string>()
  for (let index = 0; index < value.subjects.length; index += 1) {
    const subject = value.subjects[index]
    if (!isRecord(subject)) return invalid(`主体 ${index + 1} 不是有效对象`)
    const keyError = exactKeyError(
      subject,
      [
        "id",
        "name",
        "kind",
        "function",
        "background",
        "conflict_history",
        "present_stakes",
        "temperament",
        "speech_style",
        "drive",
        "change",
        "debut",
        "limits",
        "demand_refs",
      ],
      `主体 ${index + 1}`,
    )
    if (keyError) return invalid(keyError)
    if (!isCharacterKind(subject.kind))
      return invalid(`主体 ${index + 1} 的 kind 无效`)
    const textFields = [
      "id",
      "name",
      "function",
      "background",
      "conflict_history",
      "present_stakes",
      "temperament",
      "speech_style",
      "drive",
      "change",
      "debut",
    ] as const
    for (const field of textFields) {
      if (!nonEmptyText(subject[field]))
        return invalid(`主体 ${index + 1} 的 ${field} 必须是非空文本`)
    }
    if (
      !/^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(subject.id as string)
    ) {
      return invalid(`主体 ${index + 1} 的 id 无效`)
    }
    if (
      !/^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$/.test(subject.debut as string)
    ) {
      return invalid(`主体 ${index + 1} 的 debut 无效`)
    }
    if (!validTextList(subject.limits) || subject.limits.length === 0)
      return invalid(`主体 ${index + 1} 的 limits 不能为空`)
    if (!validTextList(subject.demand_refs) || subject.demand_refs.length === 0)
      return invalid(`主体 ${index + 1} 的 demand_refs 不能为空`)
    if (subjectIds.has(subject.id as string))
      return invalid(`主体 ID 重复：${subject.id as string}`)
    subjectIds.add(subject.id as string)
    subjects.push(subject as CharacterSubject)
  }
  if (
    subjects.filter((subject) => subject.kind === "protagonist").length !== 1
  ) {
    return invalid("Character Bible 必须且只能包含一名主角")
  }

  const relations: CharacterRelation[] = []
  const relationKeys = new Set<string>()
  for (let index = 0; index < value.relations.length; index += 1) {
    const relation = value.relations[index]
    if (!isRecord(relation)) return invalid(`关系 ${index + 1} 不是有效对象`)
    const keyError = exactKeyError(
      relation,
      ["a", "b", "type", "pressure"],
      `关系 ${index + 1}`,
    )
    if (keyError) return invalid(keyError)
    if (
      !nonEmptyText(relation.a) ||
      !nonEmptyText(relation.b) ||
      !nonEmptyText(relation.type) ||
      !nonEmptyText(relation.pressure)
    ) {
      return invalid(`关系 ${index + 1} 的字段必须是非空文本`)
    }
    if (
      relation.a === relation.b ||
      !subjectIds.has(relation.a) ||
      !subjectIds.has(relation.b)
    ) {
      return invalid(`关系 ${index + 1} 引用了未登记或相同主体`)
    }
    const relationKey = [relation.a, relation.b].sort().join("|")
    if (relationKeys.has(relationKey))
      return invalid(`关系 ${index + 1} 重复连接同一组主体`)
    relationKeys.add(relationKey)
    relations.push(relation as CharacterRelation)
  }

  return { artifact: { subjects, relations }, error: "" }
}

export function parseVolumeArchitectureArtifact(
  value: unknown,
): ArtifactParseResult<VolumeArchitectureArtifact> {
  if (!isRecord(value)) return invalid("Volume Architecture 不是有效对象")
  const topLevelError = exactKeyError(value, ["volumes"], "Volume Architecture")
  if (topLevelError) return invalid(topLevelError)
  if (!Array.isArray(value.volumes) || value.volumes.length === 0)
    return invalid("volumes 至少包含一个分卷合同")

  const volumes: VolumeContract[] = []
  for (let index = 0; index < value.volumes.length; index += 1) {
    const volume = value.volumes[index]
    if (!isRecord(volume)) return invalid(`分卷 ${index + 1} 不是有效对象`)
    const keyError = exactKeyError(
      volume,
      [
        "id",
        "title",
        "promise",
        "conflict",
        "climax",
        "climax_turn_ref",
        "closure",
        "turn_refs",
        "cast_ids",
        "length_hint",
      ],
      `分卷 ${index + 1}`,
    )
    if (keyError) return invalid(keyError)
    if (volume.id !== `volume-${index + 1}`)
      return invalid("分卷必须从 volume-1 起连续编号")
    for (const field of [
      "title",
      "promise",
      "conflict",
      "climax",
      "climax_turn_ref",
      "closure",
    ] as const) {
      if (!nonEmptyText(volume[field]))
        return invalid(`分卷 ${index + 1} 的 ${field} 必须是非空文本`)
    }
    if (!/^turn-[1-9][0-9]*$/.test(volume.climax_turn_ref as string))
      return invalid(`分卷 ${index + 1} 的高潮引用无效`)
    if (
      !validTextList(volume.turn_refs) ||
      volume.turn_refs.some((item) => !/^turn-[1-9][0-9]*$/.test(item))
    ) {
      return invalid(`分卷 ${index + 1} 的 turn_refs 无效`)
    }
    if (!volume.turn_refs.includes(volume.climax_turn_ref as string))
      return invalid(`分卷 ${index + 1} 的高潮不在本卷因果边界内`)
    if (!validTextList(volume.cast_ids))
      return invalid(`分卷 ${index + 1} 的 cast_ids 无效`)
    if (
      volume.length_hint !== "short" &&
      volume.length_hint !== "medium" &&
      volume.length_hint !== "long"
    ) {
      return invalid(`分卷 ${index + 1} 的 length_hint 无效`)
    }
    volumes.push(volume as VolumeContract)
  }

  return { artifact: { volumes }, error: "" }
}

export function parseDetailArtifact(
  value: unknown,
): ArtifactParseResult<DetailArtifact> {
  if (!isRecord(value)) return invalid("Detail Artifact 不是有效对象")
  const topLevelError = exactKeyError(value, ["chapters"], "Detail Artifact")
  if (topLevelError) return invalid(topLevelError)
  if (!Array.isArray(value.chapters) || value.chapters.length === 0)
    return invalid("chapters 至少包含一章")

  const chapters: DetailChapter[] = []
  const titles = new Set<string>()
  for (let index = 0; index < value.chapters.length; index += 1) {
    const chapter = value.chapters[index]
    if (!isRecord(chapter)) return invalid(`章节 ${index + 1} 不是有效对象`)
    const chapterLabel = `章节 ${index + 1}`
    const keyError = exactKeyError(
      chapter,
      [
        "ref",
        "volume_ref",
        "title",
        "target_characters",
        "turn_refs",
        "purpose",
        "pov",
        "cast_ids",
        "scenes",
        "handoff",
      ],
      chapterLabel,
    )
    if (keyError) return invalid(keyError)
    if (chapter.ref !== `chapter-${index + 1}`)
      return invalid("章节必须从 chapter-1 起连续编号")
    if (
      typeof chapter.volume_ref !== "string" ||
      !/^volume-[1-9][0-9]*$/.test(chapter.volume_ref)
    ) {
      return invalid(`${chapterLabel} 的 volume_ref 无效`)
    }
    if (!nonEmptyText(chapter.title))
      return invalid(`${chapterLabel} 的 title 必须是非空文本`)
    const titleLength = Array.from(chapter.title.trim()).length
    if (titleLength < 2 || titleLength > 12)
      return invalid(`${chapterLabel} 的章名必须为 2-12 字`)
    if (titles.has(chapter.title.trim()))
      return invalid(`${chapterLabel} 的章名与前文重复`)
    titles.add(chapter.title.trim())
    if (
      chapter.target_characters !== null &&
      (!Number.isInteger(chapter.target_characters) ||
        (chapter.target_characters as number) < 1)
    ) {
      return invalid(`${chapterLabel} 的 target_characters 无效`)
    }
    if (
      !validTextList(chapter.turn_refs) ||
      chapter.turn_refs.length === 0 ||
      chapter.turn_refs.some((item) => !/^turn-[1-9][0-9]*$/.test(item))
    ) {
      return invalid(`${chapterLabel} 的 turn_refs 无效`)
    }
    if (new Set(chapter.turn_refs).size !== chapter.turn_refs.length)
      return invalid(`${chapterLabel} 的 turn_refs 不能重复`)
    if (!nonEmptyText(chapter.purpose))
      return invalid(`${chapterLabel} 的 purpose 必须是非空文本`)
    if (!nonEmptyText(chapter.pov))
      return invalid(`${chapterLabel} 的 pov 必须是非空文本`)
    if (!validTextList(chapter.cast_ids) || chapter.cast_ids.length === 0)
      return invalid(`${chapterLabel} 的 cast_ids 无效`)
    if (new Set(chapter.cast_ids).size !== chapter.cast_ids.length)
      return invalid(`${chapterLabel} 的 cast_ids 不能重复`)
    if (!chapter.cast_ids.includes(chapter.pov))
      return invalid(`${chapterLabel} 的 cast_ids 必须包含 POV`)
    if (
      !Array.isArray(chapter.scenes) ||
      chapter.scenes.length < 1 ||
      chapter.scenes.length > 12
    ) {
      return invalid(`${chapterLabel} 必须包含 1-12 个场景`)
    }
    for (
      let sceneIndex = 0;
      sceneIndex < chapter.scenes.length;
      sceneIndex += 1
    ) {
      const scene = chapter.scenes[sceneIndex]
      if (!isRecord(scene))
        return invalid(`${chapterLabel} 的场景 ${sceneIndex + 1} 不是有效对象`)
      const sceneError = exactKeyError(
        scene,
        ["place", "objective", "conflict", "turn", "result"],
        `${chapterLabel} 的场景 ${sceneIndex + 1}`,
      )
      if (sceneError) return invalid(sceneError)
      for (const field of [
        "place",
        "objective",
        "conflict",
        "turn",
        "result",
      ] as const) {
        if (!nonEmptyText(scene[field]))
          return invalid(
            `${chapterLabel} 的场景 ${sceneIndex + 1} 缺少 ${field}`,
          )
      }
    }
    if (!nonEmptyText(chapter.handoff))
      return invalid(`${chapterLabel} 的 handoff 必须是非空文本`)
    chapters.push(chapter as DetailChapter)
  }

  return { artifact: { chapters }, error: "" }
}

export function parseChapterArtifact(
  value: unknown,
): ArtifactParseResult<ChapterArtifact> {
  if (!isRecord(value)) return invalid("Chapter Artifact 不是有效对象")
  const keyError = exactKeyError(
    value,
    ["chapter_id", "version_id", "title", "content", "author_status"],
    "Chapter Artifact",
  )
  if (keyError) return invalid(keyError)
  if (
    typeof value.chapter_id !== "string" ||
    !/^chapter-[1-9][0-9]*$/.test(value.chapter_id)
  ) {
    return invalid("chapter_id 无效")
  }
  if (!nonEmptyText(value.version_id)) return invalid("version_id 不能为空")
  if (!nonEmptyText(value.title)) return invalid("title 不能为空")
  if (!nonEmptyText(value.content)) return invalid("content 不能为空")
  if (
    value.author_status !== "candidate" &&
    value.author_status !== "accepted" &&
    value.author_status !== "edited" &&
    value.author_status !== "branched"
  ) {
    return invalid("author_status 无效")
  }
  return { artifact: value as ChapterArtifact, error: "" }
}

function invalid<T>(error: string): ArtifactParseResult<T> {
  return { artifact: null, error }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function nonEmptyText(value: unknown): value is string {
  return typeof value === "string" && Boolean(value.trim())
}

function validTextList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => nonEmptyText(item))
}

function exactKeyError(
  value: Record<string, unknown>,
  expected: string[],
  label: string,
) {
  const unknown = Object.keys(value).filter((key) => !expected.includes(key))
  const missing = expected.filter((key) => !(key in value))
  if (unknown.length) return `${label} 包含未支持字段：${unknown.join("、")}`
  if (missing.length) return `${label} 缺少字段：${missing.join("、")}`
  return ""
}

function isCharacterKind(value: unknown): value is CharacterKind {
  return (
    value === "protagonist" ||
    value === "major" ||
    value === "functional" ||
    value === "npc" ||
    value === "historical_record"
  )
}

function isProgressType(value: unknown): value is StoryProgressType {
  return (
    value === "information" ||
    value === "relationship" ||
    value === "external" ||
    value === "internal"
  )
}

function isMilestone(value: unknown): value is StoryMilestone {
  return (
    value === "inciting" ||
    value === "commitment" ||
    value === "midpoint_reversal" ||
    value === "crisis" ||
    value === "climax" ||
    value === "aftermath"
  )
}
