import type {
  ArtifactPatchCandidate,
  CollaborationMessage,
  CollaborationMode,
  CollaborationStageId,
  CollaborationThreadDetail,
  CollaborationTurn,
} from "../contracts/authorCollaboration"

export type CollaborationUnitScope = {
  label: string
  unitRef: string
}

export const collaborationStageLabels: Record<CollaborationStageId, string> = {
  cast: "人物圣经",
  beat_board: "决策节拍",
  scene_deck: "场景编排",
  script: "剧本正文",
  story_map: "故事地图",
  section_plan: "章节规划",
  text: "小说正文",
  book_architecture: "全书架构",
  volumes: "卷册架构",
  rolling_detail: "滚动细纲",
}

export const collaborationModeLabels: Record<CollaborationMode, string> = {
  discuss: "讨论",
  plan: "方案",
  revise: "改稿",
}

export function isCollaborationStageId(
  value: string,
): value is CollaborationStageId {
  return value in collaborationStageLabels
}

export function activeCollaborationTurn(
  detail: CollaborationThreadDetail | null,
): CollaborationTurn | null {
  return (
    [...(detail?.turns ?? [])]
      .reverse()
      .find((turn) => ["queued", "streaming"].includes(turn.status)) ?? null
  )
}

export function messagePatch(
  detail: CollaborationThreadDetail | null,
  message: CollaborationMessage,
): ArtifactPatchCandidate | null {
  if (!message.patch_candidate_ref) return null
  return (
    detail?.patches.find(
      (patch) => patch.patch_id === message.patch_candidate_ref,
    ) ?? null
  )
}

export function patchBeforeText(
  detail: CollaborationThreadDetail | null,
  patch: ArtifactPatchCandidate,
): string {
  return (
    detail?.turns.find((turn) => turn.turn_id === patch.turn_id)
      ?.selection_anchor?.selected_text ?? ""
  )
}

export function shortProviderLabel(
  detail: CollaborationThreadDetail | null,
): string {
  const execution = detail?.thread.provider_execution
  return execution
    ? `${execution.provider_profile_id} · ${execution.model_id}`
    : "冻结模型"
}

export function defaultCollaborationUnit(
  stageId: CollaborationStageId,
  artifactText: string,
): CollaborationUnitScope {
  try {
    const value = JSON.parse(artifactText) as Record<string, unknown>
    if (stageId === "cast")
      return firstUnit(value.characters, "subject_ref", "人物全局")
    if (stageId === "beat_board")
      return firstUnit(value.beats, "beat_ref", "决策节拍")
    if (stageId === "scene_deck")
      return firstUnit(value.scenes, "scene_ref", "场景编排")
    if (stageId === "story_map")
      return firstUnit(value.anchors, "anchor_ref", "故事地图")
    if (stageId === "section_plan")
      return firstUnit(value.units, "unit_ref", "章节规划")
    if (stageId === "book_architecture")
      return firstUnit(value.parts, "part_ref", "全书架构")
    if (stageId === "volumes")
      return firstUnit(value.volumes, "volume_ref", "卷册架构")
    if (stageId === "rolling_detail")
      return firstNestedUnit(
        value.windows,
        "chapters",
        "chapter_ref",
        "滚动细纲",
      )
    if (stageId === "script") return textUnit(value, "scene_ref")
    if (stageId === "text") return textUnit(value, "unit_ref", "chapter_ref")
  } catch {
    // An unavailable Artifact is handled by the panel empty state.
  }
  return { unitRef: "artifact", label: collaborationStageLabels[stageId] }
}

function textUnit(value: Record<string, unknown>, ...keys: string[]) {
  const unitRef =
    keys
      .map((key) => value[key])
      .find(
        (candidate): candidate is string => typeof candidate === "string",
      ) ?? "artifact"
  return {
    unitRef,
    label: typeof value.title === "string" ? value.title : unitRef,
  }
}

function firstUnit(value: unknown, key: string, fallback: string) {
  const item =
    Array.isArray(value) && value[0] && typeof value[0] === "object"
      ? value[0] as Record<string, unknown>
      : null
  const unitRef =
    item && typeof item[key] === "string" ? item[key] as string : "artifact"
  const label =
    item && typeof item.title === "string"
      ? item.title
      : item && typeof item.name === "string"
        ? item.name
        : unitRef === "artifact"
          ? fallback
          : unitRef
  return { unitRef, label }
}

function firstNestedUnit(
  groups: unknown,
  collectionKey: string,
  unitKey: string,
  fallback: string,
) {
  if (!Array.isArray(groups)) return { unitRef: "artifact", label: fallback }
  for (const group of groups) {
    if (!group || typeof group !== "object") continue
    const collection = (group as Record<string, unknown>)[collectionKey]
    if (Array.isArray(collection) && collection.length > 0)
      return firstUnit(collection, unitKey, fallback)
  }
  return { unitRef: "artifact", label: fallback }
}
