import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { stagePositionSummary } from '../lib/stageProgress';
import { buildRunEventIndex } from '../state/runEventIndex';
import { completedDeliveryStageIds, stageDeliveryStatus } from '../state/stageDeliveryStatus';

export type ArtifactDeckStatus = 'attention' | 'confirmed' | 'current' | 'queued' | 'running';

export type ArtifactDeckItem = {
  artifact: string;
  decision: string;
  id: string;
  label: string;
  nextDependency: string;
  nextStage: string;
  status: ArtifactDeckStatus;
  statusLabel: string;
  writeback: string;
};

type StageSemantics = Pick<ArtifactDeckItem, 'artifact' | 'decision' | 'nextDependency' | 'writeback'>;

const stageSemantics: Record<WorkflowStage['type'], StageSemantics> = {
  info_recommend: {
    artifact: '方向 · 世界观 · 人物档案',
    decision: '确认创作方向',
    nextDependency: '创作方向 · 人物基线',
    writeback: '世界观 · 人物关系网',
  },
  summary: {
    artifact: '故事核心 · 全书梗概 · 关键转折',
    decision: '确认全书结构',
    nextDependency: '完整梗概 · 结构节点',
    writeback: '人物关系网 · 世界观 · 质量阀门',
  },
  outline: {
    artifact: '分卷目标 · 节奏 · 冲突推进',
    decision: '确认分卷方案',
    nextDependency: '分卷节拍 · 章节范围',
    writeback: '人物关系网 · 世界观 · 伏笔账本',
  },
  detail_outline: {
    artifact: '章节蓝图 · 事实 · 伏笔账本',
    decision: '确认章节施工图',
    nextDependency: '章节蓝图 · 连续性上下文',
    writeback: '人物关系网 · 世界观 · Wiki',
  },
  chapter_text: {
    artifact: '章节正文 · 修订 · 质量报告',
    decision: '确认当前定稿',
    nextDependency: '正文定稿 · 质量结论',
    writeback: 'Wiki · Canon · 人物关系网',
  },
  cover_image: {
    artifact: '封面简报 · 提示词 · 候选图',
    decision: '选定封面资产',
    nextDependency: '选定封面 · 出版元数据',
    writeback: '封面资产 · 导出清单',
  },
  export_artifact: {
    artifact: '清单 · 文件 · 校验结果',
    decision: '确认导出交付',
    nextDependency: '已校验交付包',
    writeback: '交付包 · 导出历史',
  },
};

export function buildArtifactDeckItems(workflow: WorkflowDefinition, events: RunEvent[], selectedId: string): ArtifactDeckItem[] {
  const eventIndex = buildRunEventIndex(events);
  return workflow.nodes.map((stage, index) => {
    const semantics = stageSemantics[stage.type];
    const status = deckStatus(stage, eventIndex, selectedId);
    return {
      ...semantics,
      id: stage.id,
      label: stage.label,
      nextStage: workflow.nodes[index + 1]?.label ?? '流程结束',
      status,
      statusLabel: statusLabel(status),
    };
  });
}

export function buildPlanningStagePosition(workflow: WorkflowDefinition, events: RunEvent[], selectedId: string) {
  const eventIndex = buildRunEventIndex(events);
  return stagePositionSummary({
    completedStageIds: completedDeliveryStageIds(eventIndex, workflow.nodes),
    currentStageId: selectedId,
    stageIds: workflow.nodes.map((stage) => stage.id),
  });
}

function deckStatus(stage: WorkflowStage, eventIndex: ReturnType<typeof buildRunEventIndex>, selectedId: string): ArtifactDeckStatus {
  const status = stageDeliveryStatus(eventIndex, stage);
  if (status === 'failed' || status === 'attention') return 'attention';
  if (status === 'done') return 'confirmed';
  if (status === 'running') return 'running';
  if (stage.id === selectedId) return 'current';
  return 'queued';
}

function statusLabel(status: ArtifactDeckStatus) {
  if (status === 'confirmed') return '已确认';
  if (status === 'running') return '生成中';
  if (status === 'attention') return '待完善';
  if (status === 'current') return '当前稿';
  return '待开始';
}
