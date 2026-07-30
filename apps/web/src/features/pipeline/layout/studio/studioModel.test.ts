import { describe, expect, it } from 'vitest';
import {
  formatWordCount,
  mapWithConcurrency,
  relativeTimeLabel,
  stageProgressDots,
  unarchivedRuns,
} from './studioModel';
import type { RunHistoryItem } from '../../contracts';

describe('stageProgressDots', () => {
  it('derives the seven-stage dot matrix from real completed/current facts', () => {
    const dots = stageProgressDots({
      completed_stage_ids: ['info', 'summary'],
      current_stage: { id: 'outline', label: '分卷大纲' },
    });
    expect(dots.map((dot) => dot.id)).toEqual(['info', 'summary', 'outline', 'detail', 'text', 'cover', 'export']);
    expect(dots.map((dot) => dot.status)).toEqual([
      'completed', 'completed', 'current', 'pending', 'pending', 'pending', 'pending',
    ]);
  });

  it('treats a completed current stage as completed and no summary as all pending', () => {
    const dots = stageProgressDots({ completed_stage_ids: ['info'], current_stage: { id: 'info' } });
    expect(dots[0].status).toBe('completed');
    expect(stageProgressDots(null).every((dot) => dot.status === 'pending')).toBe(true);
  });
});

describe('unarchivedRuns', () => {
  const runs = [
    { run_id: 'run-a', project_id: 'run-a' },
    { run_id: 'run-b', project_id: '' },
    { run_id: 'run-c', project_id: 'proj-1' },
    { run_id: 'run-d', project_id: 'run-d' },
  ] as RunHistoryItem[];

  it('groups legacy runs (project_id missing or equal to run_id) and excludes archived ones', () => {
    expect(unarchivedRuns(runs, {}).map((item) => item.run_id)).toEqual(['run-a', 'run-b', 'run-d']);
    expect(unarchivedRuns(runs, { 'run-d': 'proj-9' }).map((item) => item.run_id)).toEqual(['run-a', 'run-b']);
  });
});

describe('mapWithConcurrency', () => {
  it('caps parallelism, preserves order, and turns failures into null', async () => {
    let inFlight = 0;
    let peak = 0;
    const results = await mapWithConcurrency([1, 2, 3, 4, 5, 6], 4, async (item) => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 2));
      inFlight -= 1;
      if (item === 3) throw new Error('boom');
      return item * 10;
    });
    expect(results).toEqual([10, 20, null, 40, 50, 60]);
    expect(peak).toBeLessThanOrEqual(4);
  });
});

describe('labels', () => {
  it('formats relative time and word counts for card metadata', () => {
    const now = new Date('2026-07-26T12:00:00Z').getTime();
    expect(relativeTimeLabel('2026-07-26T11:59:40Z', now)).toBe('刚刚');
    expect(relativeTimeLabel('2026-07-26T11:20:00Z', now)).toBe('40 分钟前');
    expect(relativeTimeLabel('2026-07-26T04:00:00Z', now)).toBe('8 小时前');
    expect(relativeTimeLabel('2026-07-23T12:00:00Z', now)).toBe('3 天前');
    expect(relativeTimeLabel('', now)).toBe('时间未知');
    expect(formatWordCount(0)).toBe('0 字');
    expect(formatWordCount(860)).toBe('860 字');
    expect(formatWordCount(123456)).toBe('12.3 万字');
  });
});
