import { describe, expect, it } from 'vitest';
import {
  formatWordCount,
  mapWithConcurrency,
  relativeTimeLabel,
  stageProgressDots,
  studioLibraryStats,
} from './studioModel';
import type { ProjectRecord, ProjectSummary } from '../../contracts';

describe('stageProgressDots', () => {
  it('derives the eight-stage dot matrix from real completed/current facts', () => {
    const dots = stageProgressDots({
      completed_stage_ids: ['brief', 'spine'],
      current_stage: { id: 'volumes', label: '分卷架构' },
    });
    expect(dots.map((dot) => dot.id)).toEqual(['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export']);
    expect(dots.map((dot) => dot.status)).toEqual([
      'completed', 'completed', 'pending', 'current', 'pending', 'pending', 'pending', 'pending',
    ]);
  });

  it('treats a completed current stage as completed and no summary as all pending', () => {
    const dots = stageProgressDots({ completed_stage_ids: ['brief'], current_stage: { id: 'brief' } });
    expect(dots[0].status).toBe('completed');
    expect(stageProgressDots(null).every((dot) => dot.status === 'pending')).toBe(true);
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

describe('studioLibraryStats', () => {
  it('derives word, delivery, and stage coverage figures from project summaries', () => {
    const project = (id: string): ProjectRecord => ({
      accent_hue: 160, created_at: '', id, latest_run_id: '', status: 'active', summary: '', title: id, updated_at: '', workflow_id: '',
    });
    const projects = [project('p1'), project('p2')];
    const summary = (projectRecord: ProjectRecord, status: string, words: number, completed: string[]): ProjectSummary => ({
      completed_stage_ids: completed,
      current_stage: {},
      latest_run: null,
      project: projectRecord,
      status,
      title: projectRecord.title,
      updated_at: '',
      words,
    });
    expect(studioLibraryStats(projects, {
      p1: summary(projects[0], 'completed', 107_613, ['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export']),
      p2: summary(projects[1], 'running', 12_000, ['brief', 'spine']),
    })).toEqual({ completedProjects: 1, projectCount: 2, stageCoverage: 63, totalWords: 119_613 });
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
