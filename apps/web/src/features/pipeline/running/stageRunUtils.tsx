import {
  BookOpenText,
  Download,
  FileText,
  Image,
  Layers3,
  ListChecks,
  Sparkles,
  UsersRound,
} from 'lucide-react';
import type { ReactNode } from 'react';
import type { ChapterProgressItem, RunEvent, StageType, WorkflowStage } from '../contracts';
import { runEventLabel } from '../lib/runEventLabels';
import { buildRunEventIndex } from '../state/runEventIndex';
import { stageDeliveryStatus } from '../state/stageDeliveryStatus';

export function stageConfig(type: StageType) {
  const iconMap: Record<StageType, { icon: ReactNode; steps: string[] }> = {
    info: { icon: <Sparkles size={18} />, steps: ['读取立项', '装配前置资料', '生成创作契约', '等待冻结'] },
    characters: { icon: <UsersRound size={18} />, steps: ['读取创作契约', '编排人物职责', '校验关系与窗口', '等待冻结'] },
    summary: { icon: <FileText size={18} />, steps: ['读取人物圣经', '推演因果节拍', '核对人物结局', '等待冻结'] },
    outline: { icon: <Layers3 size={18} />, steps: ['读取故事脊柱', '规划分卷转折', '分配人物与线索窗口', '等待冻结'] },
    detail: { icon: <ListChecks size={18} />, steps: ['读取分卷方案', '拆分章节场景', '校验义务与交接', '等待冻结'] },
    text: { icon: <BookOpenText size={18} />, steps: ['装配章节上下文', '生成正文候选', '并发审稿', '等待定稿'] },
    cover: { icon: <Image size={18} />, steps: ['提炼封面简报', '生成资产候选', '记录生成回执', '等待选定'] },
    export: { icon: <Download size={18} />, steps: ['冻结版本选择', '确定性生成文件', '校验交付包', '记录导出'] },
  };
  return iconMap[type];
}

export function currentStep(stageId: string, events: RunEvent[], total: number) {
  if (events.some((event) => isStageEvent(event, stageId) && stageCompletedBy(event))) return total - 1;
  if (events.some((event) => isStageEvent(event, stageId) && event.type === 'decision.required')) return Math.min(total - 1, 2);
  if (events.some((event) => isStageEvent(event, stageId) && ['node.started', 'artifact.candidate_ready'].includes(event.type))) return 1;
  return 0;
}

export function statusText(stage: Pick<WorkflowStage, 'id' | 'type'>, events: RunEvent[]) {
  const status = stageDeliveryStatus(buildRunEventIndex(events), stage);
  if (status === 'failed') return '失败';
  if (status === 'attention') return '待完善';
  if (status === 'awaiting') return '待决策';
  if (status === 'done') return '已完成';
  if (status === 'running') return '运行中';
  return '等待中';
}

export function latestResult(events: RunEvent[], stageId: string) {
  return artifactText(events.find((event) => (
    isStageEvent(event, stageId)
    && ['artifact.candidate_ready', 'artifact.committed'].includes(event.type)
    && event.payload != null
  ))?.payload);
}

export function latestApprovedArtifact(events: RunEvent[], stageId: string) {
  return artifactText(events.find((event) => (
    isStageEvent(event, stageId)
    && event.type === 'artifact.committed'
    && event.payload != null
  ))?.payload);
}

export function labelForRag(type: string) {
  return runEventLabel(type);
}

export function referenceEventText(event: RunEvent) {
  return payloadText(event, 'message')
    || payloadText(event, 'title')
    || payloadText(event, 'query')
    || runEventLabel(event.type);
}

export function chaptersFrom(events: RunEvent[]): ChapterProgressItem[] {
  return events
    .filter((event) => event.type === 'artifact.committed' && event.stage_id === 'text' && event.chapter_id)
    .map((event) => ({
      volume: '',
      chapter: event.chapter_id,
      status: 'completed',
      words: payloadText(event, 'content').length,
      quality_score: 0,
      node_id: event.node_id,
    }));
}

export function currentChapter(events: RunEvent[]) {
  return events.find((event) => event.stage_id === 'text' && event.chapter_id)?.chapter_id ?? '';
}

export function writingContent(events: RunEvent[]) {
  return [...writingContentByChapter(events).entries()]
    .map(([chapter, value]) => `${chapter}\n${value.content}`)
    .join('\n\n');
}

export function writingContentByChapter(events: RunEvent[]) {
  const map = new Map<string, { content: string; completed: boolean; streaming: boolean; words: number }>();
  [...events].reverse().forEach((event) => {
    if (!event.chapter_id || !['artifact.candidate_ready', 'artifact.committed'].includes(event.type)) return;
    const content = payloadText(event, 'content');
    if (!content) return;
    map.set(event.chapter_id, {
      content,
      completed: event.type === 'artifact.committed',
      streaming: false,
      words: content.length,
    });
  });
  return map;
}

export function streamDeltasFor(_events: RunEvent[], _stageId: string) {
  return [] as Array<{ section: string; delta: string }>;
}

export function eventStageId(event: RunEvent): string {
  return event.stage_id || event.node_id.split('.')[0] || '';
}

export function isStageEvent(event: RunEvent, stageId: string): boolean {
  return eventStageId(event) === stageId;
}

export function qualityEventLabel(type: string) {
  const labels: Record<string, string> = {
    'review.started': '开始审稿',
    'review.completed': '审稿完成',
    'review.unavailable': '审稿角色不可用',
    'decision.required': '等待人工决定',
    'decision.resolved': '人工决定已确认',
  };
  return labels[type] ?? runEventLabel(type);
}

export function qualityEventText(event: RunEvent) {
  const role = payloadText(event, 'role');
  const findings = Array.isArray(event.payload?.findings) ? event.payload.findings.length : 0;
  if (event.type === 'review.completed') return `${role || '审稿角色'}完成审稿 · ${findings} 个发现`;
  if (event.type === 'review.unavailable') return `${role || '审稿角色'}不可用`;
  const reason = event.payload?.reason;
  if (reason && typeof reason === 'object') return JSON.stringify(reason);
  return payloadText(event, 'message') || runEventLabel(event.type);
}

export function chapterQualityClass(events: RunEvent[], chapter: string) {
  const signal = latestChapterQualitySignal(events, chapter);
  if (signal?.type === 'decision.required' || signal?.type === 'review.unavailable') return 'blocked';
  if (signal?.type === 'review.completed') return 'checked';
  return '';
}

export function chapterQualityLabel(events: RunEvent[], chapter: string) {
  const signal = latestChapterQualitySignal(events, chapter);
  if (signal?.type === 'decision.required' || signal?.type === 'review.unavailable') return '需人工处理';
  if (signal?.type === 'review.completed') return '已审稿';
  return '待检查';
}

function latestChapterQualitySignal(events: RunEvent[], chapter: string) {
  return events.find((event) => (
    event.chapter_id === chapter
    && ['decision.required', 'review.unavailable', 'review.completed'].includes(event.type)
  ));
}

function stageCompletedBy(event: RunEvent) {
  if (event.type === 'artifact.committed' && event.stage_id !== 'text') return true;
  return event.type === 'node.completed' && (
    event.node_id.endsWith('.checkpoint_stage') || event.node_id === 'text.finish_chapters'
  );
}

function payloadText(event: RunEvent, key: string) {
  const value = event.payload?.[key];
  return typeof value === 'string' ? value : '';
}

function artifactText(value: unknown) {
  return value && typeof value === 'object' && !Array.isArray(value) ? JSON.stringify(value) : '';
}
