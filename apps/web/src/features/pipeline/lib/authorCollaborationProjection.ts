import type {
  ArtifactPatchCandidate,
  CollaborationMessage,
  CollaborationMode,
  CollaborationStageId,
  CollaborationThreadDetail,
  CollaborationTurn,
} from "../contracts/authorCollaboration"

export type CollaborationUnitScope = {
  label: string;
  unitRef: string;
};

export const collaborationStageLabels: Record<CollaborationStageId, string> = {
  spine: '故事脊柱',
  cast: '人物编排',
  volumes: '分卷架构',
  detail: '章节细纲',
  text: '章节正文',
};

export const collaborationModeLabels: Record<CollaborationMode, string> = {
  discuss: '讨论',
  plan: '方案',
  revise: '改稿',
};

export function isCollaborationStageId(value: string): value is CollaborationStageId {
  return ["spine", "cast", "volumes", "detail", "text"].includes(value)
}

export function activeCollaborationTurn(detail: CollaborationThreadDetail | null): CollaborationTurn | null {
  return [...(detail?.turns ?? [])].reverse().find((turn) => ['queued', 'streaming'].includes(turn.status)) ?? null;
}

export function messagePatch(
  detail: CollaborationThreadDetail | null,
  message: CollaborationMessage,
): ArtifactPatchCandidate | null {
  if (!message.patch_candidate_ref) return null;
  return detail?.patches.find((patch) => patch.patch_id === message.patch_candidate_ref) ?? null;
}

export function patchBeforeText(detail: CollaborationThreadDetail | null, patch: ArtifactPatchCandidate): string {
  return detail?.turns.find((turn) => turn.turn_id === patch.turn_id)?.selection_anchor?.selected_text ?? '';
}

export function shortProviderLabel(detail: CollaborationThreadDetail | null): string {
  const binding = detail?.thread.provider_binding;
  return binding ? `${binding.provider_profile_id} · ${binding.model}` : '冻结模型';
}

export function defaultCollaborationUnit(stageId: CollaborationStageId, artifactText: string): CollaborationUnitScope {
  try {
    const value = JSON.parse(artifactText) as Record<string, unknown>;
    if (stageId === 'spine') return firstUnit(value.turns, 'id', '全局脊柱');
    if (stageId === 'cast') return firstUnit(value.subjects, 'id', '人物全局');
    if (stageId === 'volumes') return firstUnit(value.volumes, 'id', '全书分卷');
    if (stageId === 'detail') return firstUnit(value.chapters, 'ref', '章节细纲');
    if (stageId === 'text') {
      const unitRef = typeof value.chapter_id === 'string' ? value.chapter_id : 'artifact';
      return { unitRef, label: typeof value.title === 'string' ? value.title : unitRef };
    }
  } catch {
    // An unavailable Artifact is handled by the panel empty state.
  }
  return { unitRef: 'artifact', label: collaborationStageLabels[stageId] };
}

function firstUnit(value: unknown, key: string, fallback: string) {
  const item = Array.isArray(value) && value[0] && typeof value[0] === 'object'
    ? value[0] as Record<string, unknown>
    : null;
  const unitRef = item && typeof item[key] === 'string' ? item[key] as string : 'artifact';
  const label = item && typeof item.title === 'string'
    ? item.title
    : item && typeof item.name === 'string'
      ? item.name
      : unitRef === 'artifact' ? fallback : unitRef;
  return { unitRef, label };
}
