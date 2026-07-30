import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { buildTensionSeries, tensionPointDescription } from './tensionTrackModel';
import type { WritingChapter } from './writingArtifactModel';

function chapter(id: string, title: string): WritingChapter {
  return {
    id, title, generated_title: title, content: '正文', words: 2, status: 'completed', version: 1,
    commit_signature: '', summary: '', summary_dirty: false, context_packet: null,
    wiki_writebacks: [], character_shift: '', foreshadow_updates: [], quality_report: {},
    quality_recheck: null, model_review: null, writeback_proposal: null, revision_history: [], version_history: [],
  };
}

const chapters = [chapter('c1', '第一章'), chapter('c2', '第二章'), chapter('c3', '第三章')];

function scoredEvent(chapterName: string, score: number, basis: string): RunEvent {
  return { type: 'chapter_tension_scored', run_id: 'run-1', node_id: 'text', chapter: chapterName, score, basis, source: 'model_review' };
}

function bibleEvent(track: Array<Record<string, unknown>>): RunEvent {
  return { type: 'story_bible_updated', run_id: 'run-1', story_bible: { tension_track: track } };
}

describe('tension track series', () => {
  it('prefers chapter_tension_scored events and upserts per chapter (newest event wins)', () => {
    const events = [
      scoredEvent('第一章', 8.2, '重评后的高压对峙'),
      scoredEvent('第一章', 5, '初评'),
      bibleEvent([{ chapter: '第一章', score: 3, basis: '过期快照' }]),
    ];
    const series = buildTensionSeries(chapters, events, 'c1');
    expect(series.source).toBe('events');
    expect(series.points[0].score).toBe(8.2);
    expect(series.points[0].basis).toBe('重评后的高压对峙');
  });

  it('falls back to story_bible_updated.tension_track when no scored events exist', () => {
    const events = [bibleEvent([
      { chapter: '第一章', score: 4.5, basis: '铺垫章' },
      { chapter: '第二章', score: 7, basis: '冲突爆发' },
    ])];
    const series = buildTensionSeries(chapters, events, 'c2');
    expect(series.source).toBe('story_bible');
    expect(series.points.map((point) => point.score)).toEqual([4.5, 7, null]);
  });

  it('keeps unscored chapters as gaps and never interpolates across them', () => {
    const events = [scoredEvent('第一章', 6, ''), scoredEvent('第三章', 9, '高潮')];
    const series = buildTensionSeries(chapters, events, 'c1');
    expect(series.points[1].score).toBeNull();
    expect(series.segments.map((segment) => segment.map((point) => point.index))).toEqual([[0], [2]]);
    expect(tensionPointDescription(series.points[1])).toBe('第 2 章 第二章：暂无张力评分');
  });

  it('joins consecutive scored chapters into one line segment', () => {
    const events = [scoredEvent('第一章', 6, ''), scoredEvent('第二章', 7, '')];
    const series = buildTensionSeries(chapters, events, 'c1');
    expect(series.segments).toHaveLength(1);
    expect(series.segments[0].map((point) => point.index)).toEqual([0, 1]);
    expect(series.scoredCount).toBe(2);
  });

  it('marks only the active chapter as current', () => {
    const series = buildTensionSeries(chapters, [scoredEvent('第一章', 6, '')], 'c2');
    expect(series.points.map((point) => point.isCurrent)).toEqual([false, true, false]);
  });

  it('reports an honest empty state when neither events nor story bible carry scores (fast mode / old runs)', () => {
    const series = buildTensionSeries(chapters, [bibleEvent([])], 'c1');
    expect(series.empty).toBe(true);
    expect(series.source).toBe('none');
  });
});
