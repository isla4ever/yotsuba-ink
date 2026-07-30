import { BookOpenText, Boxes, Download, FileText, Image, Layers3, ListChecks, Sparkles, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { ChapterProgressItem, RunEvent, StageType, WorkflowStage } from '../contracts';
import { runEventLabel } from '../lib/runEventLabels';
import { buildRunEventIndex } from '../state/runEventIndex';
import { stageDeliveryStatus } from '../state/stageDeliveryStatus';

export function stageConfig(type: StageType) {
  const iconMap: Record<StageType, { icon: ReactNode; steps: string[] }> = {
    info_recommend: { icon: <Sparkles size={18} />, steps: ['需求解析', '资料检索', '推荐生成', '设定沉淀'] },
    summary: { icon: <FileText size={18} />, steps: ['读取推荐', '主线推演', '角色弧', '梗概成稿'] },
    outline: { icon: <Layers3 size={18} />, steps: ['卷数规划', '卷冲突', '章节范围', '伏笔分布'] },
    detail_outline: { icon: <ListChecks size={18} />, steps: ['读取卷纲', '章节拆解', '钩子伏笔', '覆盖校验'] },
    chapter_text: { icon: <BookOpenText size={18} />, steps: ['章节读取', '候选生成', '质量评审', '正文写回'] },
    cover_image: { icon: <Image size={18} />, steps: ['提炼气质', '构图提示', '生成预览', '产物记录'] },
    export_artifact: { icon: <Download size={18} />, steps: ['资产汇总', '格式校验', '文件打包', '导出完成'] },
  };
  return iconMap[type];
}

export function currentStep(stageId: string, events: RunEvent[], total: number) {
  if (events.some((event) => event.type === 'node_completed' && event.node_id === stageId)) return total - 1;
  if (events.some((event) => event.type === 'quality_check_completed' && event.node_id === stageId)) return Math.min(total - 1, 2);
  if (events.some((event) => event.type === 'node_started' && event.node_id === stageId)) return 1;
  return 0;
}

export function statusText(stage: Pick<WorkflowStage, 'id' | 'type'>, events: RunEvent[]) {
  const status = stageDeliveryStatus(buildRunEventIndex(events), stage);
  if (events.some((event) => (
    (event.type === 'run_recovery_required' || event.recovery_state?.needs_recovery)
    && (!event.node_id || event.node_id === stage.id)
  ))) return '待恢复';
  if (status === 'failed') return '失败';
  if (status === 'attention') return '待完善';
  if (status === 'done') return '已完成';
  if (status === 'running') return '运行中';
  return '等待中';
}

export function stageQualityScore(events: RunEvent[], stageId: string) {
  const event = events.find((item) => (
    item.node_id === stageId
    && ['asset_progress_updated', 'quality_check_completed', 'quality_recheck_completed'].includes(item.type)
    && (item.quality_report?.score != null || item.quality?.score != null || item.score != null)
  ));
  const score = Number(event?.quality_report?.score ?? event?.quality?.score ?? event?.score);
  return Number.isFinite(score) ? Math.max(0, Math.min(1, score > 1 ? score / 100 : score)) : null;
}

export function latestResult(events: RunEvent[], stageId: string) {
  const selected = events.find((item) => item.type === 'draft_candidate_selected' && item.node_id === stageId);
  if (selected?.artifact) return typeof selected.artifact === 'string' ? selected.artifact : JSON.stringify(selected.artifact);
  const restored = events.find((item) => item.type === 'artifact_validated' && item.node_id === stageId);
  if (restored?.artifact) return typeof restored.artifact === 'string' ? restored.artifact : JSON.stringify(restored.artifact);
  const completed = events.find((item) => item.type === 'node_completed' && item.node_id === stageId);
  if (!completed?.result) return '';
  return typeof completed.result === 'string' ? completed.result : JSON.stringify(completed.result);
}

export function latestApprovedArtifact(events: RunEvent[], stageId: string) {
  const event = events.find((item) => item.type === 'artifact_approved' && item.node_id === stageId);
  if (!event?.artifact) return '';
  return typeof event.artifact === 'string' ? event.artifact : JSON.stringify(event.artifact);
}

export function labelForRag(type: string) {
  const map: Record<string, string> = {
    reference_collection_started: '资料搜集',
    reference_source_found: '发现来源',
    reference_understanding_completed: '资料理解',
    reference_context_injected: '注入推荐',
    web_search_started: '联网搜索',
    web_results_found: '联网命中',
    rag_query_started: '检索启动',
    rag_query_rewritten: '检索改写',
    rag_results_found: '命中资料',
    rag_context_selected: '上下文注入',
  };
  return map[type] ?? runEventLabel(type);
}

export function referenceEventText(event: RunEvent) {
  if (event.title) return `${event.title}${event.section ? ` / ${event.section}` : ''}${event.score ? ` · score ${Number(event.score).toFixed(2)}` : ''}`;
  if (event.url) return event.url;
  if (event.message) return event.message;
  if (event.query_rewrite) return String(event.query_rewrite);
  if (event.results?.length) return `命中 ${event.results.length} 条资料`;
  if (event.target) return `已注入 ${event.target}`;
  return String(event.reason || event.preview || event.source || '') || runEventLabel(event.type);
}

export function chaptersFrom(events: RunEvent[]): ChapterProgressItem[] {
  const latest = events.find((event) => event.type === 'chapter_progress_updated' && event.chapters);
  return latest?.chapters?.length ? latest.chapters : [];
}

export function currentChapter(events: RunEvent[]) {
  const latestActive = events.find((event) => event.type === 'chapter_delta' || event.type === 'chapter_started');
  return latestActive?.chapter ?? '';
}

export function writingContent(events: RunEvent[]) {
  const chronological = [...events].reverse();
  const activeChapter = currentChapter(events);
  const completed = chronological
    .filter((event) => event.type === 'chapter_completed' && event.content && event.chapter !== activeChapter)
    .map((event) => `\n\n${event.chapter}\n${event.content}`);
  const streaming = chronological
    .filter((event) => event.type === 'chapter_delta' && event.delta && (!activeChapter || event.chapter === activeChapter))
    .map((event) => event.delta)
    .join('');
  const currentBlock = activeChapter && streaming ? `${activeChapter}\n${streaming}` : streaming;
  return [completed.join('\n').trim(), currentBlock].filter(Boolean).join('\n\n').trim();
}

export function writingContentByChapter(events: RunEvent[]) {
  const map = new Map<string, { content: string; completed: boolean; streaming: boolean; words: number }>();
  [...events].reverse().forEach((event) => {
    if (!event.chapter) return;
    if (event.type === 'chapter_delta' && event.delta) {
      const current = map.get(event.chapter) ?? { content: '', completed: false, streaming: false, words: 0 };
      map.set(event.chapter, {
        ...current,
        content: `${current.content}${event.delta}`,
        streaming: true,
        words: current.words + String(event.delta).length,
      });
    }
    if (event.type === 'chapter_completed' && event.content) {
      map.set(event.chapter, {
        content: String(event.content),
        completed: true,
        streaming: false,
        words: Number(event.words ?? String(event.content).length),
      });
    }
  });
  return map;
}

export function streamDeltasFor(events: RunEvent[], stageId: string) {
  return [...events]
    .reverse()
    .filter((event) => event.type === 'artifact_stream_delta' && event.node_id === stageId && event.delta)
    .map((event) => ({ section: event.section ?? '生成片段', delta: String(event.delta ?? '') }));
}

export function qualityEventLabel(type: string) {
  const map: Record<string, string> = {
    chapter_context_built: '章节上下文',
    quality_check_started: '开始检查',
    quality_check_completed: '检查完成',
    revision_directive_created: '修订指令',
    revision_applied: '局部修订',
    quality_recheck_completed: '复检完成',
    story_bible_updated: '写回 Bible',
    manual_intervention_required: '人工介入',
  };
  return map[type] ?? runEventLabel(type);
}

export function qualityEventText(event: RunEvent) {
  if (event.context_packet) return `${event.chapter ?? event.context_packet.chapter} · ${event.context_packet.chapter_kind} · 读取 ${event.context_packet.open_foreshadows?.length ?? 0} 个伏笔`;
  if (event.directive) return event.directive.instruction || event.directive.issue;
  if (event.quality_report) {
    const findings = event.quality_report.findings?.length ?? 0;
    const hits = event.quality_report.constraint_hits?.join('、') || '基础结构';
    return `Q ${event.quality_report.score.toFixed(2)} · ${findings} 个问题 · 命中 ${hits}`;
  }
  if (event.reason) return event.reason;
  if (event.story_bible) return '世界观、人物、伏笔与章节摘要已同步';
  return event.message || runEventLabel(event.type);
}

export function chapterQualityClass(events: RunEvent[], chapter: string) {
  if (events.some((event) => event.type === 'manual_intervention_required' && event.chapter === chapter)) return 'blocked';
  if (events.some((event) => event.type === 'revision_directive_created' && event.chapter === chapter)) return 'revision';
  if (events.some((event) => event.type === 'quality_check_completed' && event.chapter === chapter)) return 'checked';
  return '';
}

export function chapterQualityLabel(events: RunEvent[], chapter: string) {
  if (events.some((event) => event.type === 'manual_intervention_required' && event.chapter === chapter)) return '需人工处理';
  if (events.some((event) => event.type === 'revision_directive_created' && event.chapter === chapter)) return '修订中';
  if (events.some((event) => event.type === 'quality_recheck_completed' && event.chapter === chapter)) return '复检';
  if (events.some((event) => event.type === 'quality_check_completed' && event.chapter === chapter)) return '已检查';
  return '待检查';
}
