import { describe, expect, it } from 'vitest';
import type { RunEvent, WorkflowStage } from '../contracts';
import { displayRunLogEvents, latestNodeStatus } from './cockpitRuntime';

describe('latestNodeStatus', () => {
  it('treats a newer stage confirmation as the terminal stage state', () => {
    const events = [
      event('stage_artifact_confirmed'),
      event('node_started'),
      event('node_completed'),
    ];

    expect(latestNodeStatus(events, 'outline').status).toBe('done');
  });

  it('keeps a retry running when its start is newer than the prior confirmation', () => {
    const events = [
      event('node_started'),
      event('stage_artifact_confirmed'),
      event('node_completed'),
    ];

    expect(latestNodeStatus(events, 'outline').status).toBe('running');
  });

  it('keeps a newer stage failure visible after an older confirmation', () => {
    const events = [
      event('node_failed'),
      event('artifact_approved'),
      event('node_completed'),
    ];

    expect(latestNodeStatus(events, 'outline').status).toBe('failed');
  });
});

describe('latestNodeStatus usage subscription (D1)', () => {
  it('derives completed seconds from real stage_usage_finalized events', () => {
    const events: RunEvent[] = [
      event('node_completed'),
      {
        node_id: 'outline',
        run_id: 'status-test',
        type: 'stage_usage_finalized',
        usage: {
          estimated_input_tokens: 100,
          estimated_output_tokens: 40,
          cached_tokens: 0,
          candidate_count: 1,
          revision_count: 0,
          elapsed_ms: 4200,
        },
      },
      event('node_started'),
    ];

    const status = latestNodeStatus(events, 'outline');
    expect(status.status).toBe('done');
    expect(status.completedSeconds).toBe(4);
  });
});

describe('asset progress derivation (D2)', () => {
  const coverStage = { id: 'cover', label: 'AI 封面', type: 'cover_image' } as WorkflowStage;

  it('derives progress from real ready/total counts', () => {
    const events: RunEvent[] = [
      { node_id: 'cover', run_id: 'run-1', type: 'asset_progress_updated', ready_count: 1, failed_count: 0, total: 3 },
      { node_id: 'cover', run_id: 'run-1', type: 'node_started' },
    ];

    const items = displayRunLogEvents(events, coverStage);
    expect(items.find((item) => item.agent === 'main')?.progress).toBeCloseTo(1 / 3, 5);
    expect(items.find((item) => item.agent === 'asset')?.progress).toBeCloseTo(1 / 3, 5);
  });

  it('stays indeterminate without counts instead of showing a fabricated percentage', () => {
    const events: RunEvent[] = [
      { node_id: 'cover', run_id: 'run-1', type: 'asset_progress_updated' },
      { node_id: 'cover', run_id: 'run-1', type: 'node_started' },
    ];

    const items = displayRunLogEvents(events, coverStage);
    expect(items.find((item) => item.agent === 'main')?.progress).toBeUndefined();
    expect(items.find((item) => item.agent === 'asset')?.progress).toBeUndefined();
  });

  it('reports full progress once the stage node completes', () => {
    const events: RunEvent[] = [
      { node_id: 'cover', run_id: 'run-1', type: 'node_completed' },
      { node_id: 'cover', run_id: 'run-1', type: 'asset_progress_updated', ready_count: 2, failed_count: 1, total: 3 },
      { node_id: 'cover', run_id: 'run-1', type: 'node_started' },
    ];

    const items = displayRunLogEvents(events, coverStage);
    const lane = items.find((item) => item.agent === 'asset');
    expect(lane?.progress).toBe(1);
    expect(lane?.status).toBe('done');
  });
});

function event(type: RunEvent['type']): RunEvent {
  return { node_id: 'outline', run_id: 'status-test', type };
}
