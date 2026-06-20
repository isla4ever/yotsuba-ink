import { BookOpenText, Boxes, Download, FileText, Image, Layers3, ListChecks, Sparkles, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { ChapterProgressItem, RunEvent, StageType, WorkflowStage } from '../../types/workflow';

export function stageConfig(type: StageType) {
  const iconMap: Record<StageType, { icon: ReactNode; steps: string[] }> = {
    info_recommend: { icon: <Sparkles size={18} />, steps: ['Brief 读取', '参考检索', '候选生成', '世界观种子'] },
    summary: { icon: <FileText size={18} />, steps: ['读取推荐', '主线推演', '角色弧', '梗概成稿'] },
    outline: { icon: <Layers3 size={18} />, steps: ['卷数规划', '卷冲突', '章节范围', '伏笔分布'] },
    detail_outline: { icon: <ListChecks size={18} />, steps: ['读取卷纲', '章节拆解', '钩子伏笔', '覆盖校验'] },
    chapter_text: { icon: <BookOpenText size={18} />, steps: ['章节读取', '候选生成', '质量评审', '正文写回'] },
    cover_image: { icon: <Image size={18} />, steps: ['提炼气质', '构图提示', '生成预览', '产物记录'] },
    export_artifact: { icon: <Download size={18} />, steps: ['资产汇总', '质量摘要', 'Wiki 摘要', '导出完成'] },
  };
  return iconMap[type];
}

export function currentStep(stageId: string, events: RunEvent[], total: number) {
  if (events.some((event) => event.type === 'node_completed' && event.node_id === stageId)) return total - 1;
  if (events.some((event) => event.type === 'quality_check_completed' && event.node_id === stageId)) return Math.min(total - 1, 2);
  if (events.some((event) => event.type === 'node_started' && event.node_id === stageId)) return 1;
  return 0;
}

export function statusText(stageId: string, events: RunEvent[]) {
  if (events.some((event) => event.type === 'node_failed' && event.node_id === stageId)) return '失败';
  if (events.some((event) => event.type === 'node_completed' && event.node_id === stageId)) return '已完成';
  if (events.some((event) => event.type === 'node_started' && event.node_id === stageId)) return '运行中';
  return '等待中';
}

export function latestResult(events: RunEvent[], stageId: string) {
  const event = events.find((item) => item.type === 'node_completed' && item.node_id === stageId);
  if (!event?.result) return '';
  return typeof event.result === 'string' ? event.result : JSON.stringify(event.result, null, 2);
}

export function labelForRag(type: string) {
  const map: Record<string, string> = {
    reference_collection_started: '资料搜集',
    reference_source_found: '发现来源',
    reference_understanding_completed: '资料理解',
    reference_context_injected: '注入 Brief',
    web_search_started: '联网搜索',
    web_results_found: '联网命中',
    rag_query_started: '检索启动',
    rag_query_rewritten: 'Query Rewrite',
    rag_results_found: '命中资料',
    rag_context_selected: '上下文注入',
  };
  return map[type] ?? type;
}

export function referenceEventText(event: RunEvent) {
  if (event.title) return `${event.title}${event.section ? ` / ${event.section}` : ''}${event.score ? ` · score ${Number(event.score).toFixed(2)}` : ''}`;
  if (event.url) return event.url;
  if (event.message) return event.message;
  if (event.query_rewrite) return String(event.query_rewrite);
  if (event.results?.length) return `命中 ${event.results.length} 条资料`;
  if (event.target) return `已注入 ${event.target}`;
  return String(event.reason || event.preview || event.source || event.type);
}

export function chaptersFrom(events: RunEvent[]): ChapterProgressItem[] {
  const latest = events.find((event) => event.type === 'chapter_progress_updated' && event.chapters);
  return latest?.chapters?.length ? latest.chapters : [];
}

export function currentChapter(events: RunEvent[]) {
  return events.find((event) => event.type === 'chapter_started')?.chapter ?? events.find((event) => event.type === 'chapter_delta')?.chapter ?? '';
}

export function writingContent(events: RunEvent[]) {
  const chronological = [...events].reverse();
  const completed = chronological
    .filter((event) => event.type === 'chapter_completed' && event.content)
    .map((event) => `\n\n${event.chapter}\n${event.content}`);
  if (completed.length) return completed.join('\n').trim();
  return chronological
    .filter((event) => event.type === 'chapter_delta' && event.delta)
    .map((event) => event.delta)
    .join('\n');
}

export function qualityEventLabel(type: string) {
  const map: Record<string, string> = {
    chapter_context_built: '上下文包',
    quality_check_started: '开始校验',
    quality_check_completed: '校验完成',
    revision_directive_created: '修订指令',
    revision_applied: '局部修订',
    quality_recheck_completed: '复检完成',
    story_bible_updated: '写回 Bible',
    manual_intervention_required: '人工介入',
  };
  return map[type] ?? type;
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
  return event.message || event.type;
}

export function chapterQualityClass(events: RunEvent[], chapter: string) {
  if (events.some((event) => event.type === 'manual_intervention_required' && event.chapter === chapter)) return 'blocked';
  if (events.some((event) => event.type === 'revision_directive_created' && event.chapter === chapter)) return 'revision';
  if (events.some((event) => event.type === 'quality_check_completed' && event.chapter === chapter)) return 'checked';
  return '';
}

export function chapterQualityLabel(events: RunEvent[], chapter: string) {
  if (events.some((event) => event.type === 'manual_intervention_required' && event.chapter === chapter)) return '阻断';
  if (events.some((event) => event.type === 'revision_directive_created' && event.chapter === chapter)) return '修订中';
  if (events.some((event) => event.type === 'quality_recheck_completed' && event.chapter === chapter)) return '复检';
  if (events.some((event) => event.type === 'quality_check_completed' && event.chapter === chapter)) return '已校验';
  return '待校验';
}
