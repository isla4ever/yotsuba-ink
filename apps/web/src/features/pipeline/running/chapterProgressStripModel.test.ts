import { describe, expect, it } from 'vitest';
import { chapterProgressStrip } from './chapterProgressStripModel';
import type { RunEvent } from '../contracts';

function progressEvent(): RunEvent {
  return {
    type: 'chapter_progress_updated',
    run_id: 'r',
    node_id: 'text',
    chapters: [
      { volume: '卷一', chapter: '第1章', status: 'completed', words: 3200, quality_score: 0.88, node_id: 'text' },
      { volume: '卷一', chapter: '第2章', status: 'completed', words: 2800, quality_score: 0.7, node_id: 'text' },
      { volume: '卷一', chapter: '第3章', status: 'running', words: 400, quality_score: 0, node_id: 'text' },
      { volume: '卷一', chapter: '第4章', status: 'planned', words: 0, quality_score: 0, node_id: 'text' },
      { volume: '卷一', chapter: '第5章', status: 'failed', words: 0, quality_score: 0, node_id: 'text' },
    ],
  } as RunEvent;
}

describe('chapterProgressStrip (D8)', () => {
  it('returns null without a real chapter progress snapshot (no placeholder band)', () => {
    expect(chapterProgressStrip([], 'text')).toBeNull();
    expect(chapterProgressStrip([{ type: 'chapter_delta', run_id: 'r', node_id: 'text' } as RunEvent], 'text')).toBeNull();
  });

  it('maps real statuses per chapter and derives review/failed from quality events', () => {
    const events = [
      // Newest-first: 第2章 has an open revision directive; 第1章 recheck passed after one.
      { type: 'revision_directive_created', run_id: 'r', node_id: 'text', chapter: '第2章' },
      { type: 'quality_recheck_completed', run_id: 'r', node_id: 'text', chapter: '第1章' },
      { type: 'revision_directive_created', run_id: 'r', node_id: 'text', chapter: '第1章' },
      progressEvent(),
    ] as RunEvent[];
    const strip = chapterProgressStrip(events, 'text');
    expect(strip?.cells.map((cell) => cell.status)).toEqual(['completed', 'review', 'running', 'planned', 'failed']);
    expect(strip?.counts).toEqual({ completed: 1, failed: 1, planned: 1, review: 1, running: 1 });
    expect(strip?.completed).toBe(1);
    expect(strip?.total).toBe(5);
    expect(strip?.cells[0].description).toBe('第1章 · 已完成 · 3,200 字 · Q 0.88');
    expect(strip?.cells[3].description).toBe('第4章 · 计划中');
  });

  it('escalates manual interventions to 需处理 regardless of base status', () => {
    const events = [
      { type: 'manual_intervention_required', run_id: 'r', node_id: 'text', chapter: '第1章', budget_state: {} },
      progressEvent(),
    ] as RunEvent[];
    const strip = chapterProgressStrip(events, 'text');
    expect(strip?.cells[0].status).toBe('failed');
    expect(strip?.cells[0].description).toContain('需处理');
  });
});
