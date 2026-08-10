import type { CharacterGraph, RunEvent, StageType } from '../contracts';
import type { WorldbuildingView } from '../lib/stageConfig';
import { parseStoryBriefArtifact, parseDetailArtifact, parseOutlineArtifact, parseSummaryArtifact } from './artifactsVnext';
import { parseCharacterBibleArtifact } from './characterBibleArtifact';

export type RuntimeStageProjection = Partial<Record<'character' | 'worldbuilding' | 'foreshadow', string>>;

export type RuntimeWritebackStatus = {
  status: 'not_proposed' | 'proposed' | 'queued' | 'committed' | 'rejected' | 'failed';
  label: string;
  transactionId: string;
};

export type RuntimeArtifactProjection = {
  characterGraph?: CharacterGraph;
  stage: RuntimeStageProjection;
  worldbuilding?: WorldbuildingView;
  writeback: RuntimeWritebackStatus;
};

type ProjectionSources = {
  activeStageType: StageType;
  characters: string;
  detail: string;
  events: RunEvent[];
  info: string;
  outline: string;
  summary: string;
};

export function runtimeArtifactProjection(sources: ProjectionSources): RuntimeArtifactProjection {
  return {
    characterGraph: characterGraphFrom(sources.characters),
    stage: stageProjection(sources),
    worldbuilding: worldbuildingFrom(sources.info),
    writeback: writebackStatus(sources.events, stageIdForType(sources.activeStageType)),
  };
}

function characterGraphFrom(source: string): CharacterGraph | undefined {
  const artifact = parseCharacterBibleArtifact(source).artifact;
  if (!artifact) return undefined;
  return {
    nodes: artifact.characters.map((character) => {
      const appearance = firstAppearanceMarker(character.first_appearance_window);
      return {
        id: character.id,
        name: character.name,
        role: character.narrative_function,
        faction: '',
        status: 'frozen',
        tier: character.tier === 'functional' ? 'supporting' : character.tier,
        first_appearance_stage: appearance.stage,
        first_appearance_chapter: appearance.chapter,
      };
    }),
    edges: artifact.relationships.map((relationship) => ({
      source: relationship.source_id,
      target: relationship.target_id,
      relation: relationship.nature,
      strength: 0.6,
      kind: 'other',
      polarity: 'complex',
      valid_from_stage: 'characters',
      history: [{ stage: 'characters', change: relationship.initial_state }],
    })),
    updated_by: 'characters-artifact',
  };
}

function firstAppearanceMarker(window: string): { stage: 'text'; chapter: string } {
  const match = /^chapter:([1-9][0-9]*)(?:-[1-9][0-9]*)?$/.exec(window);
  if (!match) throw new Error(`Invalid Character Bible appearance window: ${window}`);
  return { stage: 'text', chapter: match[1] };
}

function worldbuildingFrom(source: string): WorldbuildingView | undefined {
  const artifact = parseStoryBriefArtifact(source).artifact;
  if (!artifact) return undefined;
  return {
    source: '创作立项 Artifact',
    seed: artifact.premise,
    rules: artifact.world_rules,
    tone: artifact.story_promise.tone,
    impact: [artifact.thematic_question, artifact.ending_promise],
  };
}

function stageProjection(sources: ProjectionSources): RuntimeStageProjection {
  if (sources.activeStageType === 'summary') {
    const artifact = parseSummaryArtifact(sources.summary).artifact;
    return artifact ? { character: `${artifact.character_outcomes.length} 个人物结局引用已绑定人物圣经` } : {};
  }
  if (sources.activeStageType === 'outline') {
    const artifact = parseOutlineArtifact(sources.outline).artifact;
    if (!artifact) return {};
    const characterWindows = artifact.volumes.reduce((total, volume) => total + volume.character_windows.length, 0);
    const threadWindows = artifact.volumes.reduce((total, volume) => total + volume.thread_windows.length, 0);
    return {
      character: `${characterWindows} 个人物区间由分卷计划引用`,
      foreshadow: `${threadWindows} 条剧情与线索窗口等待章节施工图落实`,
    };
  }
  if (sources.activeStageType === 'detail') {
    const artifact = parseDetailArtifact(sources.detail).artifact;
    if (!artifact) return {};
    const obligations = artifact.chapters.flatMap((chapter) => chapter.obligations);
    const count = (kind: string) => obligations.filter((item) => item.kind === kind).length;
    return {
      character: `${count('character')} 条人物义务引用冻结角色`,
      worldbuilding: `${count('world_rule')} 条世界规则义务，仅作章节约束提示`,
      foreshadow: `${count('thread')} 条线索义务与 ${artifact.chapters.length} 个章节交接`,
    };
  }
  return {};
}

function writebackStatus(events: RunEvent[], stageId: string): RuntimeWritebackStatus {
  const event = events
    .filter((item) => item.stage_id === stageId && ['writeback.queued', 'writeback.committed', 'writeback.failed'].includes(item.type))
    .sort((left, right) => Number(right.sequence ?? 0) - Number(left.sequence ?? 0))[0];
  const status = event?.type === 'writeback.queued'
    ? 'queued'
    : event?.type === 'writeback.committed'
      ? 'committed'
      : event?.type === 'writeback.failed'
        ? 'failed'
        : 'not_proposed';
  const labels = {
    not_proposed: '尚未提出正式写回',
    proposed: '写回提案待决策',
    queued: '写回已进入事务队列',
    committed: '写回事务已提交',
    rejected: '写回提案已拒绝',
    failed: '写回事务失败',
  } as const;
  const transactionId = typeof event?.payload?.transaction_id === 'string' ? event.payload.transaction_id : '';
  return { status, label: labels[status], transactionId };
}

function stageIdForType(type: StageType) {
  const map: Record<StageType, string> = {
    info: 'info',
    characters: 'characters',
    summary: 'summary',
    outline: 'outline',
    detail: 'detail',
    text: 'text',
    cover: 'cover',
    export: 'export',
  };
  return map[type];
}
