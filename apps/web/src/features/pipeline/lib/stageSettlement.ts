import type { RunEvent, WorkflowStage } from '../contracts';

export type StageSettlementSummary = {
  checkpointId: string;
  committedArtifact: boolean;
  reviewCount: number;
  unavailableReviewCount: number;
  writebackStatus: 'none' | 'queued' | 'committed' | 'failed';
};

export function stageSettlementSummary(events: RunEvent[], stage: Pick<WorkflowStage, 'id'>): StageSettlementSummary {
  const stageEvents = events.filter((event) => event.stage_id === stage.id);
  const writeback = stageEvents.find((event) => event.type.startsWith('writeback.'));
  return {
    checkpointId: stageEvents.find((event) => event.type === 'checkpoint.saved')?.checkpoint_id ?? '',
    committedArtifact: stageEvents.some((event) => event.type === 'artifact.committed'),
    reviewCount: stageEvents.filter((event) => event.type === 'review.completed').length,
    unavailableReviewCount: stageEvents.filter((event) => event.type === 'review.unavailable').length,
    writebackStatus: writeback?.type === 'writeback.queued'
      ? 'queued'
      : writeback?.type === 'writeback.committed'
        ? 'committed'
        : writeback?.type === 'writeback.failed'
          ? 'failed'
          : 'none',
  };
}

export function settlementNextStageLabel(next: string): string {
  const labels: Record<string, string> = {
    info: '创作立项',
    characters: '人物编排',
    summary: '全书梗概',
    outline: '分卷大纲',
    detail: '章节施工图',
    text: '正文生成',
    cover: 'AI 封面',
    export: '导出',
  };
  return labels[next] ?? next;
}
