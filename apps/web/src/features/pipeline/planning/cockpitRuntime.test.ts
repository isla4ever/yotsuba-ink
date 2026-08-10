import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import type { WorkflowStage } from '../contracts';
import { displayRunLogEvents, latestNodeStatus } from './cockpitRuntime';

const outlineStage = { id: 'outline', label: '分卷大纲', type: 'outline' } as WorkflowStage;

describe('latestNodeStatus', () => {
  it('uses the newest Graph lifecycle event', () => {
    const done = [
      runEvent('artifact.committed', { stage_id: 'outline', node_id: 'outline.commit_artifact' }),
      runEvent('node.started', { stage_id: 'outline', node_id: 'outline.generate_candidate' }),
    ];
    expect(latestNodeStatus(done, 'outline').status).toBe('done');

    const retry = [
      runEvent('node.started', { stage_id: 'outline', node_id: 'outline.generate_candidate' }),
      ...done,
    ];
    expect(latestNodeStatus(retry, 'outline').status).toBe('running');
  });

  it('keeps a newer Graph failure visible', () => {
    const events = [
      runEvent('node.failed', { stage_id: 'outline', node_id: 'outline.generate_candidate', payload: { code: 'ProviderOperationError' } }),
      runEvent('artifact.committed', { stage_id: 'outline', node_id: 'outline.commit_artifact' }),
    ];
    expect(latestNodeStatus(events, 'outline').status).toBe('failed');
  });

  it('derives duration only from envelope timestamps', () => {
    const events = [
      runEvent('artifact.committed', { stage_id: 'outline', node_id: 'outline.commit_artifact', occurred_at: '2026-08-11T00:00:04Z' }),
      runEvent('node.started', { stage_id: 'outline', node_id: 'outline.generate_candidate', occurred_at: '2026-08-11T00:00:00Z' }),
    ];
    expect(latestNodeStatus(events, 'outline').completedSeconds).toBe(4);
  });
});

describe('displayRunLogEvents', () => {
  it('projects node, review, writeback and checkpoint events without legacy metrics', () => {
    const events = [
      runEvent('checkpoint.saved', { stage_id: 'outline', node_id: 'graph.checkpoint', checkpoint_id: 'cp-1' }),
      runEvent('writeback.committed', { stage_id: 'outline', node_id: 'outline.writeback', payload: { transaction_id: 'tx-1' } }),
      runEvent('review.completed', { stage_id: 'outline', node_id: 'outline.review', payload: { role: 'continuity', findings: [] } }),
      runEvent('node.started', { stage_id: 'outline', node_id: 'outline.generate_candidate' }),
    ];

    const items = displayRunLogEvents(events, outlineStage);
    expect(items.map((item) => item.agent)).toEqual(['main', 'quality', 'wiki', 'settlement']);
    expect(items.find((item) => item.agent === 'settlement')?.detail).toBe('cp-1');
    expect(items.every((item) => item.progress == null)).toBe(true);
  });
});
