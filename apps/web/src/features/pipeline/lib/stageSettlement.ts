import type { RunEvent, WorkflowStage } from '../contracts';
import { stageUsageCostUsd, stageUsageElapsedMs, stageUsageFromEvents, stageUsageTokens } from './stageUsage';

/**
 * Phase 12 D7: real settlement facts for a completed stage — words, usage,
 * elapsed time and the quality gate score (D1 data path). Shared between the
 * route settlement overlay and the cockpit settlement summary card.
 */
export type StageSettlementSummary = {
  elapsedMs: number | null;
  tokens: number | null;
  costUsd: number | null;
  words: number;
  qualityScore: number | null;
  qualityFindings: number;
  message: string;
  nextStep: string;
};

export function stageSettlementSummary(events: RunEvent[], stage: Pick<WorkflowStage, 'id'>): StageSettlementSummary {
  const usage = stageUsageFromEvents(events, stage.id);
  const summary = events.find((event) => event.type === 'stage_summary_ready' && event.node_id === stage.id);
  const quality = events.find((event) => event.type === 'quality_check_completed' && event.node_id === stage.id)?.quality_report;
  return {
    costUsd: stageUsageCostUsd(usage),
    elapsedMs: stageUsageElapsedMs(usage) ?? positiveOrNull(Number(summary?.elapsed_ms ?? 0)),
    message: summary?.message ?? '',
    nextStep: String(summary?.next_step ?? ''),
    qualityFindings: quality?.findings.length ?? 0,
    qualityScore: quality ? quality.score : null,
    tokens: stageUsageTokens(usage),
    words: settlementWordCount(events, stage.id),
  };
}

function settlementWordCount(events: RunEvent[], stageId: string): number {
  const chapterWords = events.find((event) => event.type === 'chapter_progress_updated' && event.node_id === stageId)
    ?.chapters?.reduce((sum, item) => sum + item.words, 0);
  if (chapterWords) return chapterWords;
  return events.find((event) => event.type === 'chapter_completed' && event.node_id === stageId)?.words ?? 0;
}

export function formatSettlementMs(value: number): string {
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

export function settlementNextStageLabel(next: string): string {
  const map: Record<string, string> = {
    summary: '全书梗概',
    outline: '分卷大纲',
    detail: '章节细纲',
    text: '正文生成',
    cover: 'AI 封面',
    export: '导出',
  };
  return map[next] ?? next;
}

function positiveOrNull(value: number) {
  return Number.isFinite(value) && value > 0 ? value : null;
}
