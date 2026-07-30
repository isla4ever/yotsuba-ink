import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { captureRunResetSnapshot } from './runResetState';

describe('captureRunResetSnapshot', () => {
  it('captures the current run for a paused local-only restore', () => {
    const events: RunEvent[] = [
      {
        type: 'stage_checkpoint_ready',
        run_id: 'run-reset-safe',
        node_id: 'detail',
        artifact: { chapters: [] },
        created_at: '2026-07-19T12:00:01Z',
      },
      {
        type: 'run_started',
        run_id: 'run-reset-safe',
        node_id: 'info',
        created_at: '2026-07-19T12:00:00Z',
      },
    ];

    const snapshot = captureRunResetSnapshot({
      automationCockpitReady: true,
      decision: {
        approvalDraft: '当前人工稿',
        approvalPending: true,
        approvalSource: '服务端来源稿',
        checkpointContinueReady: false,
        checkpointStageId: 'detail',
        infoContinueReady: false,
      },
      events,
      runSource: 'backend',
      state: {
        activeRunId: 'run-reset-safe',
        paused: false,
        runControlState: 'running',
        selectedId: 'detail',
      },
    });

    expect(snapshot).not.toBeNull();
    expect(snapshot?.runSource).toBe('backend');
    expect(snapshot?.hydrated).toMatchObject({
      activeRunId: 'run-reset-safe',
      approvalDraft: '当前人工稿',
      approvalPending: true,
      automationCockpitReady: true,
      checkpointStageId: 'detail',
      paused: true,
      runControlState: 'paused',
      selectedId: 'detail',
    });
    expect(snapshot?.hydrated.events).toEqual(events);
  });

  it('does not offer undo without a persisted event context', () => {
    const snapshot = captureRunResetSnapshot({
      automationCockpitReady: false,
      decision: {
        approvalDraft: '',
        approvalPending: false,
        approvalSource: '',
        checkpointContinueReady: false,
        checkpointStageId: '',
        infoContinueReady: false,
      },
      events: [],
      runSource: 'backend',
      state: {
        activeRunId: 'starting-run',
        paused: false,
        runControlState: 'starting',
        selectedId: 'info',
      },
    });

    expect(snapshot).toBeNull();
  });
});
