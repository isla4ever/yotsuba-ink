import { describe, expect, it } from 'vitest';
import { completedStageIdsFromEvents, stagePositionSummary } from './stageProgress';
import type { RunEvent } from '../contracts';

const stageIds = ['info', 'summary', 'outline', 'detail', 'text', 'cover', 'export'];

describe('stagePositionSummary (D4)', () => {
  it('derives 第 N/M and the completed count from real completed stage ids', () => {
    const position = stagePositionSummary({
      completedStageIds: ['info', 'summary', 'ghost-stage'],
      currentStageId: 'outline',
      stageIds,
    });
    expect(position).toEqual({ completed: 2, current: 3, total: 7 });
  });

  it('reports current 0 for unknown stages so the badge can hide', () => {
    const position = stagePositionSummary({ completedStageIds: [], currentStageId: 'missing', stageIds });
    expect(position).toEqual({ completed: 0, current: 0, total: 7 });
  });
});

describe('completedStageIdsFromEvents (D4)', () => {
  it('collects unique node_completed stage ids from the newest-first stream', () => {
    const events = [
      { type: 'chapter_delta', node_id: 'text' },
      { type: 'node_completed', node_id: 'summary' },
      { type: 'node_completed', node_id: 'info' },
      { type: 'node_completed', node_id: 'info' },
      { type: 'node_completed' },
    ] as RunEvent[];
    expect(completedStageIdsFromEvents(events)).toEqual(['summary', 'info']);
  });
});
