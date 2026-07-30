import type { RunEvent } from '../contracts';

/**
 * Phase 12 D8: per-chapter progress cells for the Text stage band. Base facts
 * come from the real `chapter_progress_updated` snapshot (status/words/quality
 * per chapter); the review/failed refinements come from the chapter-scoped
 * quality events (`revision_directive_created`, `quality_recheck_completed`,
 * `manual_intervention_required`). No synthetic progress.
 */

export type ChapterCellStatus = 'planned' | 'running' | 'review' | 'completed' | 'failed';

export type ChapterProgressCell = {
  chapter: string;
  volume: string;
  status: ChapterCellStatus;
  words: number;
  qualityScore: number | null;
  /** Tooltip / accessible description, e.g. 「第3章 · 已完成 · 3,214 字」. */
  description: string;
};

export type ChapterProgressStripData = {
  cells: ChapterProgressCell[];
  counts: Record<ChapterCellStatus, number>;
  completed: number;
  total: number;
};

export const chapterCellStatusLabels: Record<ChapterCellStatus, string> = {
  completed: '已完成',
  failed: '需处理',
  planned: '计划中',
  review: '修订中',
  running: '写作中',
};

export function chapterProgressStrip(events: RunEvent[], stageId: string): ChapterProgressStripData | null {
  const progress = events.find((event) => (
    event.type === 'chapter_progress_updated' && event.node_id === stageId && event.chapters?.length
  ));
  if (!progress?.chapters?.length) return null;

  const counts: Record<ChapterCellStatus, number> = { completed: 0, failed: 0, planned: 0, review: 0, running: 0 };
  const cells = progress.chapters.map((item) => {
    const status = cellStatus(item.status, events, item.chapter);
    counts[status] += 1;
    const score = Number(item.quality_score);
    const qualityScore = Number.isFinite(score) && score > 0 ? score : null;
    const words = Number(item.words) || 0;
    const parts = [item.chapter, chapterCellStatusLabels[status]];
    if (words) parts.push(`${words.toLocaleString()} 字`);
    if (qualityScore != null) parts.push(`Q ${qualityScore.toFixed(2)}`);
    return {
      chapter: item.chapter,
      description: parts.join(' · '),
      qualityScore,
      status,
      volume: item.volume,
      words,
    };
  });
  return { cells, completed: counts.completed, counts, total: cells.length };
}

function cellStatus(
  base: 'planned' | 'running' | 'completed' | 'failed',
  events: RunEvent[],
  chapter: string,
): ChapterCellStatus {
  // Newest chapter-scoped quality signal wins (events are newest-first).
  const signal = events.find((event) => (
    event.chapter === chapter
    && (
      event.type === 'manual_intervention_required'
      || event.type === 'revision_directive_created'
      || event.type === 'quality_recheck_completed'
    )
  ));
  if (signal?.type === 'manual_intervention_required') return 'failed';
  if (signal?.type === 'revision_directive_created') return 'review';
  return base;
}

/** Cheap change signature so the strip only re-renders on real cell changes. */
export function chapterStripSignature(strip: ChapterProgressStripData | null): string {
  if (!strip) return '';
  return strip.cells.map((cell) => `${cell.chapter}:${cell.status}:${cell.words}:${cell.qualityScore ?? ''}`).join('|');
}
