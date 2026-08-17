import type { CharacterGraph, RunEvent, StageType } from '../contracts';
import type { WorldbuildingView } from '../lib/stageConfig';
import { parseDetailArtifact, parseSpineArtifact, parseStoryBriefArtifact, parseVolumesArtifact } from './artifactsVnext';
import { parseCharacterBibleArtifact } from './characterBibleArtifact';
import { projectCharacterBibleGraph } from './characterBibleGraphProjection';

export type RuntimeStageProjection = Partial<Record<'character' | 'worldbuilding' | 'foreshadow', string>>;
export type RuntimeWritebackStatus = { status: 'not_proposed' | 'proposed' | 'queued' | 'committed' | 'rejected' | 'failed'; label: string; transactionId: string };
export type RuntimeArtifactProjection = { characterGraph?: CharacterGraph; stage: RuntimeStageProjection; worldbuilding?: WorldbuildingView; writeback: RuntimeWritebackStatus };

type ProjectionSources = { activeStageType: StageType; brief: string; cast: string; detail: string; events: RunEvent[]; spine: string; volumes: string };

export function runtimeArtifactProjection(sources: ProjectionSources): RuntimeArtifactProjection {
  const cast = parseCharacterBibleArtifact(sources.cast).artifact;
  return {
    characterGraph: cast ? projectCharacterBibleGraph(cast) : undefined,
    stage: stageProjection(sources),
    worldbuilding: worldbuildingFrom(sources.brief),
    writeback: writebackStatus(sources.events, sources.activeStageType),
  };
}

function worldbuildingFrom(source: string): WorldbuildingView | undefined {
  const artifact = parseStoryBriefArtifact(source).artifact;
  return artifact ? { source: '创作立项 Artifact', seed: artifact.premise, rules: artifact.world_rules, tone: artifact.voice, impact: [artifact.theme, artifact.ending_promise] } : undefined;
}

function stageProjection(sources: ProjectionSources): RuntimeStageProjection {
  if (sources.activeStageType === 'spine') {
    const artifact = parseSpineArtifact(sources.spine).artifact;
    return artifact ? { character: `${artifact.turns.length} 个因果转折等待职责需求提案` } : {};
  }
  if (sources.activeStageType === 'volumes') {
    const artifact = parseVolumesArtifact(sources.volumes).artifact;
    if (!artifact) return {};
    const castRefs = artifact.volumes.reduce((total, volume) => total + volume.cast_ids.length, 0);
    return { character: `${castRefs} 个人物引用分配到完整故事卷` };
  }
  if (sources.activeStageType === 'detail') {
    const artifact = parseDetailArtifact(sources.detail).artifact;
    if (!artifact) return {};
    const sceneCount = artifact.chapters.reduce((total, chapter) => total + chapter.scenes.length, 0);
    return { character: `${artifact.chapters.length} 个 POV 引用人物圣经`, worldbuilding: `${sceneCount} 个场景按需读取证据`, foreshadow: `${artifact.chapters.length} 条章节交接进入 Context Manifest` };
  }
  return {};
}

function writebackStatus(events: RunEvent[], stageId: StageType): RuntimeWritebackStatus {
  const event = events.filter((item) => item.stage_id === stageId && ['writeback.queued', 'writeback.committed', 'writeback.failed'].includes(item.type)).sort((left, right) => Number(right.sequence ?? 0) - Number(left.sequence ?? 0))[0];
  const status = event?.type === 'writeback.queued' ? 'queued' : event?.type === 'writeback.committed' ? 'committed' : event?.type === 'writeback.failed' ? 'failed' : 'not_proposed';
  const labels = { not_proposed: '尚未提出正式写回', proposed: '写回提案待决策', queued: '写回已进入事务队列', committed: '写回事务已提交', rejected: '写回提案已拒绝', failed: '写回事务失败' } as const;
  const transactionId = typeof event?.payload?.transaction_id === 'string' ? event.payload.transaction_id : '';
  return { status, label: labels[status], transactionId };
}
