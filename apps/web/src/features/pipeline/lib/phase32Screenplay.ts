export type ScreenplayBlockKind = "scene_heading" | "action" | "dialogue" | "parenthetical" | "transition"

export type ScreenplayBlockDraft = {
  kind: ScreenplayBlockKind
  text: string
  speaker_ref?: string
}

export type ScreenplayDraft = {
  scene_ref: string
  blocks: ScreenplayBlockDraft[]
}

export type ScreenplayParseResult = {
  artifact: ScreenplayDraft | null
  error: string
}

export type ScreenplaySceneContext = {
  castSubjectRefs: string[]
  heading: string
  locationAndTime: string
  opposition: string
  outcome: string
  sceneRef: string
  softPageTarget: number
  visibleGoal: string
}

export type ScreenplayCastMember = {
  displayName: string
  ref: string
  role: string
  voice: string
}

export type ScreenplayReferenceContext = {
  cast: Record<string, ScreenplayCastMember>
  scenes: ScreenplaySceneContext[]
}

export type ScreenplayDiagnostics = {
  actionBlocks: number
  blockCount: number
  dialogueBlocks: number
  outOfSceneSpeakerRefs: string[]
  sceneHeadingMatches: boolean
  sceneKnown: boolean
  speakerRefs: string[]
  unknownSpeakerRefs: string[]
}

const REF_PATTERN = /^[a-z][a-z0-9_-]{1,63}$/
const BLOCK_KINDS = new Set<ScreenplayBlockKind>([
  "scene_heading",
  "action",
  "dialogue",
  "parenthetical",
  "transition",
])

export const EMPTY_SCREENPLAY_CONTEXT: ScreenplayReferenceContext = {
  cast: {},
  scenes: [],
}

export function parsePhase32Screenplay(
  payload: Record<string, unknown> | null,
): ScreenplayParseResult {
  if (!payload)
    return { artifact: null, error: "当前场景尚无 Screenplay Artifact" }
  if (!isRef(payload.scene_ref) || !Array.isArray(payload.blocks))
    return { artifact: null, error: "剧本场景身份或正文块缺失" }
  if (payload.blocks.length < 2 || payload.blocks.length > 500)
    return { artifact: null, error: "剧本场景必须包含 2 至 500 个正文块" }
  const blocks: ScreenplayBlockDraft[] = []
  for (const value of payload.blocks) {
    if (!isRecord(value) || !BLOCK_KINDS.has(value.kind as ScreenplayBlockKind))
      return { artifact: null, error: "剧本正文包含未知块类型" }
    const kind = value.kind as ScreenplayBlockKind
    const text = typeof value.text === "string" ? value.text.trim() : ""
    const speakerRef =
      typeof value.speaker_ref === "string" ? value.speaker_ref.trim() : ""
    if (!text) return { artifact: null, error: "剧本正文块不能为空" }
    if (kind === "dialogue" && !isRef(speakerRef))
      return { artifact: null, error: "对白块必须绑定已确认人物" }
    if (!["dialogue", "parenthetical"].includes(kind) && speakerRef)
      return { artifact: null, error: "当前正文块类型不能绑定人物" }
    blocks.push({
      kind,
      text,
      ...(speakerRef ? { speaker_ref: speakerRef } : {}),
    })
  }
  if (blocks[0].kind !== "scene_heading")
    return { artifact: null, error: "剧本场景必须从标准场景标题开始" }
  if (
    !blocks
      .slice(1)
      .some((block) => ["action", "dialogue"].includes(block.kind))
  )
    return { artifact: null, error: "剧本场景至少需要一个动作或对白块" }
  return {
    artifact: { scene_ref: String(payload.scene_ref), blocks },
    error: "",
  }
}

export function extractScreenplayReferenceContext(
  sceneDeckPayload: Record<string, unknown>,
  castPayload: Record<string, unknown>,
): ScreenplayReferenceContext {
  const scenes = Array.isArray(sceneDeckPayload.scenes)
    ? sceneDeckPayload.scenes.flatMap((value): ScreenplaySceneContext[] => {
        if (!isRecord(value) || !isRef(value.scene_ref)) return []
        const castSubjectRefs = Array.isArray(value.cast_subject_refs)
          ? value.cast_subject_refs.filter(isRef)
          : []
        return [
          {
            castSubjectRefs,
            heading: text(value.heading),
            locationAndTime: text(value.location_and_time),
            opposition: text(value.opposition),
            outcome: text(value.outcome),
            sceneRef: String(value.scene_ref),
            softPageTarget:
              typeof value.soft_page_target === "number"
                ? value.soft_page_target
                : 0,
            visibleGoal: text(value.visible_goal),
          },
        ]
      })
    : []
  const cast = Object.fromEntries(
    (Array.isArray(castPayload.characters)
      ? castPayload.characters
      : []
    ).flatMap((value): Array<[string, ScreenplayCastMember]> => {
      if (!isRecord(value) || !isRef(value.subject_ref)) return []
      const ref = String(value.subject_ref)
      return [
        [
          ref,
          {
            displayName: text(value.display_name) || ref,
            ref,
            role: text(value.role),
            voice: text(value.voice),
          },
        ],
      ]
    }),
  )
  return { cast, scenes }
}

export function screenplayDiagnostics(
  artifact: ScreenplayDraft,
  context: ScreenplayReferenceContext,
): ScreenplayDiagnostics {
  const speakerRefs = Array.from(
    new Set(
      artifact.blocks.flatMap((block) =>
        block.speaker_ref ? [block.speaker_ref] : [],
      ),
    ),
  )
  const scene = context.scenes.find(
    (item) => item.sceneRef === artifact.scene_ref,
  )
  const sceneCastRefs = new Set(scene?.castSubjectRefs ?? [])
  return {
    actionBlocks: artifact.blocks.filter((block) => block.kind === "action")
      .length,
    blockCount: artifact.blocks.length,
    dialogueBlocks: artifact.blocks.filter((block) => block.kind === "dialogue")
      .length,
    outOfSceneSpeakerRefs: speakerRefs.filter((ref) => !sceneCastRefs.has(ref)),
    sceneHeadingMatches: Boolean(
      scene && artifact.blocks[0]?.text === scene.heading,
    ),
    sceneKnown: Boolean(scene),
    speakerRefs,
    unknownSpeakerRefs: speakerRefs.filter((ref) => !context.cast[ref]),
  }
}

export function screenplayContractError(
  artifact: ScreenplayDraft | null,
  context: ScreenplayReferenceContext,
) {
  if (!artifact) return "当前 Scene 尚无可确认的剧本正文"
  const diagnostics = screenplayDiagnostics(artifact, context)
  if (!diagnostics.sceneKnown) return "当前剧本 Scene 身份不在冻结的场景调度中"
  if (!diagnostics.sceneHeadingMatches)
    return "场景标题必须与冻结的 Scene Deck 标题一致"
  if (diagnostics.unknownSpeakerRefs.length)
    return "对白人物必须来自已确认的人物名册"
  if (diagnostics.outOfSceneSpeakerRefs.length)
    return "对白人物必须属于当前 Scene 的冻结人物范围"
  return ""
}

export function shortSceneRef(sceneRef: string) {
  return sceneRef.replace(/^scene[-_]?/i, "SCENE ").replace(/_/g, " ")
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
