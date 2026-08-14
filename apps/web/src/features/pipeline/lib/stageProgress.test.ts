import { describe, expect, it } from 'vitest';
import { completedStageIdsFromEvents, stagePositionSummary } from './stageProgress';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';

const stageIds = ['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export'];

describe('stagePositionSummary (D4)', () => {
  it('derives 第 N/M and the completed count from real completed stage ids', () => {
    const position = stagePositionSummary({
      completedStageIds: ['brief', 'spine', 'ghost-stage'],
      currentStageId: 'volumes',
      stageIds,
    });
    expect(position).toEqual({ completed: 2, current: 4, total: 8 });
  });

  it('reports current 0 for unknown stages so the badge can hide', () => {
    const position = stagePositionSummary({ completedStageIds: [], currentStageId: 'missing', stageIds });
    expect(position).toEqual({ completed: 0, current: 0, total: 8 });
  });
});

describe('completedStageIdsFromEvents (D4)', () => {
  it('collects unique committed Artifact stage ids from the newest-first stream', () => {
    const events = [
      runEvent('node.started', { stage_id: 'text', node_id: 'text.generate_prose' }),
      runEvent('artifact.committed', { stage_id: 'spine', node_id: 'spine.commit_artifact' }),
      runEvent('artifact.committed', { stage_id: 'brief', node_id: 'brief.commit_artifact' }),
      runEvent('artifact.committed', { stage_id: 'brief', node_id: 'brief.commit_artifact' }),
    ];
    expect(completedStageIdsFromEvents(events)).toEqual(['spine', 'brief']);
  });
});
