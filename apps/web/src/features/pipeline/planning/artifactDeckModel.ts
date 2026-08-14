import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { stagePositionSummary } from '../lib/stageProgress';
import { buildRunEventIndex } from '../state/runEventIndex';
import { completedDeliveryStageIds, stageDeliveryStatus } from '../state/stageDeliveryStatus';

export type ArtifactDeckStatus = 'attention' | 'awaiting' | 'confirmed' | 'current' | 'queued' | 'running';

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
  brief: {
    artifact: '前提 · 读者承诺 · 世界规则 · 长度包络',
    decision: '冻结创作契约',
    nextDependency: '因果脊柱与结局兑现',
    writeback: 'Story Brief Artifact',
  },
  spine: {
    artifact: '因果转折 · 结局 · 开放问题 · 进展类型',
    decision: '确认故事脊柱',
    nextDependency: '角色需求与自然卷界',
    writeback: 'Story Spine Artifact',
  },
  cast: {
    artifact: '人物职责 · 关系 · 弧线 · 出场窗口',
    decision: '冻结人物圣经',
    nextDependency: '卷级角色引用与压力诊断',
    writeback: 'Character Bible Artifact',
  },
  volumes: {
    artifact: '卷承诺 · 冲突 · 高潮 · 闭合 · 引用',
    decision: '冻结分卷架构',
    nextDependency: '当前卷合同与长度建议',
    writeback: 'Volume Architecture Artifact',
  },
  detail: {
    artifact: '章节目的 · 场景动作 · 结果 · 交接',
    decision: '确认章节施工图',
    nextDependency: '冻结的章节执行计划',
    writeback: 'Detail Artifact',
  },
  text: {
    artifact: '章节正文 · 作者状态',
    decision: '确认当前定稿',
    nextDependency: '已确认章节版本与证据',
    writeback: 'Chapter Artifact · Evidence Outbox',
  },
  cover: {
    artifact: '封面简报 · 选定资产',
    decision: '选定封面资产',
    nextDependency: '封面资产引用',
    writeback: 'Cover Artifact',
  },
  export: {
    artifact: '格式 · 章节版本 · 封面 · 元数据',
    decision: '确认导出交付',
    nextDependency: '流程完成',
    writeback: 'Export Artifact',
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
  if (status === 'awaiting') return 'awaiting';
  if (status === 'running') return 'running';
  if (stage.id === selectedId) return 'current';
  return 'queued';
}

function statusLabel(status: ArtifactDeckStatus) {
  if (status === 'confirmed') return '已确认';
  if (status === 'running') return '生成中';
  if (status === 'awaiting') return '待决策';
  if (status === 'attention') return '待完善';
  if (status === 'current') return '当前稿';
  return '待开始';
}
