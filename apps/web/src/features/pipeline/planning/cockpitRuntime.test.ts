import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import type { WorkflowStage } from '../contracts';
import { displayRunLogEvents, latestNodeStatus } from './cockpitRuntime';

const outlineStage = { id: 'volumes', label: '分卷架构', type: 'volumes' } as WorkflowStage;

describe('latestNodeStatus', () => {
  it('uses the newest Graph lifecycle event', () => {
    const done = [
      runEvent('artifact.committed', { stage_id: 'volumes', node_id: 'volumes.commit_artifact' }),
      runEvent('node.started', { stage_id: 'volumes', node_id: 'volumes.generate_candidate' }),
    ];
    expect(latestNodeStatus(done, 'volumes').status).toBe('done');

    const retry = [
      runEvent('node.started', { stage_id: 'volumes', node_id: 'volumes.generate_candidate' }),
      ...done,
    ];
    expect(latestNodeStatus(retry, 'volumes').status).toBe('running');
  });

  it('keeps a newer Graph failure visible', () => {
    const events = [
      runEvent('node.failed', { stage_id: 'volumes', node_id: 'volumes.generate_candidate', payload: { code: 'ProviderOperationError' } }),
      runEvent('artifact.committed', { stage_id: 'volumes', node_id: 'volumes.commit_artifact' }),
    ];
    expect(latestNodeStatus(events, 'volumes').status).toBe('failed');
  });

  it('projects decision interrupts as awaiting until they resolve', () => {
    const awaiting = [
      runEvent('checkpoint.saved', { stage_id: 'volumes', node_id: 'graph.checkpoint' }),
      runEvent('decision.required', { stage_id: 'volumes', node_id: 'volumes.human_decision' }),
      runEvent('artifact.candidate_ready', { stage_id: 'volumes', node_id: 'volumes.generate_candidate' }),
    ];
    expect(latestNodeStatus(awaiting, 'volumes').status).toBe('awaiting');

    const resumed = [
      runEvent('decision.resolved', { stage_id: 'volumes', node_id: 'volumes.human_decision' }),
      ...awaiting,
    ];
    expect(latestNodeStatus(resumed, 'volumes').status).toBe('running');
  });

  it('derives duration only from envelope timestamps', () => {
    const events = [
      runEvent('artifact.committed', { stage_id: 'volumes', node_id: 'volumes.commit_artifact', occurred_at: '2026-08-11T00:00:04Z' }),
      runEvent('node.started', { stage_id: 'volumes', node_id: 'volumes.generate_candidate', occurred_at: '2026-08-11T00:00:00Z' }),
    ];
    expect(latestNodeStatus(events, 'volumes').completedSeconds).toBe(4);
  });
});

describe('displayRunLogEvents', () => {
  it('projects node, review, writeback and checkpoint events without legacy metrics', () => {
    const events = [
      runEvent('checkpoint.saved', { stage_id: 'volumes', node_id: 'graph.checkpoint', checkpoint_id: 'cp-1' }),
      runEvent('writeback.committed', { stage_id: 'volumes', node_id: 'volumes.writeback', payload: { transaction_id: 'tx-1' } }),
      runEvent('review.completed', { stage_id: 'volumes', node_id: 'volumes.review', payload: { role: 'continuity', findings: [] } }),
      runEvent('node.started', { stage_id: 'volumes', node_id: 'volumes.generate_candidate' }),
    ];

    const items = displayRunLogEvents(events, outlineStage);
    expect(items.map((item) => item.agent)).toEqual(['main', 'quality', 'wiki', 'settlement']);
    expect(items.find((item) => item.agent === 'settlement')?.detail).toBe('cp-1');
    expect(items.every((item) => item.progress == null)).toBe(true);
  });
});
