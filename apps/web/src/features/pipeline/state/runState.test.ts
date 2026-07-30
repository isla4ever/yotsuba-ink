import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import {
  hydrateRunFromStoredState,
  resolveCachedRunRecovery,
  resolveHistoricalRunOpen,
  resolveServerRunRecovery,
  type StoredRunSnapshot,
} from './runState';

const runId = 'run-recovery-test';

describe('run recovery hydration', () => {
  it('reconnects a server run that is actively streaming', () => {
    const resolution = resolveServerRunRecovery(snapshot({
      events: [
        event('run_started'),
        event('node_completed', 'info'),
        event('node_started', 'summary'),
      ],
      state: {
        current_checkpoint_stage_id: 'info',
        current_stage_id: 'summary',
        runtime_phase: 'stage_streaming',
        stage_confirmation_state: { info: { status: 'confirmed', node_id: 'info' } },
      },
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(true);
    expect(resolution.hydrated.selectedId).toBe('summary');
    expect(resolution.hydrated.checkpointStageId).toBe('');
    expect(resolution.hydrated.runControlState).toBe('running');
  });

  it('restores a pending deep-stage confirmation without allowing continue', () => {
    const resolution = resolveServerRunRecovery(snapshot({
      approval: { required: true, node_id: 'summary', artifact: { full_synopsis: 'draft' } },
      events: [
        event('run_started'),
        event('node_completed', 'summary'),
        event('stage_checkpoint_ready', 'summary'),
        event('approval_required', 'summary'),
      ],
      paused: true,
      state: {
        approval_required: true,
        current_checkpoint_stage_id: 'summary',
        current_stage_id: 'summary',
        runtime_phase: 'awaiting_stage_confirmation',
        stage_confirmation_state: { summary: { status: 'pending', node_id: 'summary' } },
      },
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(false);
    expect(resolution.hydrated.approvalPending).toBe(true);
    expect(resolution.hydrated.checkpointStageId).toBe('summary');
    expect(resolution.hydrated.checkpointContinueReady).toBe(false);
    expect(resolution.hydrated.paused).toBe(true);
  });

  it('restores a confirmed info checkpoint as ready to continue', () => {
    const hydrated = hydrateRunFromStoredState(snapshot({
      approval: { required: false, node_id: 'info', artifact: { title: 'Approved' } },
      events: [
        event('run_started'),
        event('stage_checkpoint_ready', 'info'),
        event('approval_required', 'info'),
        event('stage_artifact_confirmed', 'info'),
        event('artifact_approved', 'info'),
      ],
      state: {
        approval_required: false,
        current_checkpoint_stage_id: 'info',
        current_stage_id: 'info',
        runtime_phase: 'stage_ready_to_continue',
        stage_confirmation_state: { info: { status: 'confirmed', node_id: 'info' } },
      },
    }), runId);

    expect(hydrated.approvalPending).toBe(false);
    expect(hydrated.infoContinueReady).toBe(true);
    expect(hydrated.checkpointStageId).toBe('info');
    expect(hydrated.runControlState).toBe('paused');
  });

  it('does not confuse a safe pause with the previous stage checkpoint', () => {
    const hydrated = hydrateRunFromStoredState(snapshot({
      events: [
        event('run_started'),
        event('stage_artifact_confirmed', 'info'),
        event('node_started', 'summary'),
        event('run_pause_requested', 'summary'),
        event('run_paused', 'summary'),
      ],
      paused: true,
      state: {
        current_checkpoint_stage_id: 'info',
        current_stage_id: 'summary',
        runtime_phase: 'stage_streaming',
        stage_confirmation_state: { info: { status: 'confirmed', node_id: 'info' } },
      },
    }), runId);

    expect(hydrated.selectedId).toBe('summary');
    expect(hydrated.paused).toBe(true);
    expect(hydrated.infoContinueReady).toBe(false);
    expect(hydrated.checkpointContinueReady).toBe(false);
    expect(hydrated.checkpointStageId).toBe('');
  });

  it('discards terminal, empty, and mismatched server snapshots', () => {
    const completed = resolveServerRunRecovery(snapshot({
      events: [event('run_started'), event('run_completed')],
      state: { runtime_phase: 'completed' },
    }), runId);
    const failed = resolveServerRunRecovery(snapshot({
      events: [event('run_started'), event('node_failed', 'summary')],
      state: { current_stage_id: 'summary', runtime_phase: 'failed' },
    }), runId);
    const empty = resolveServerRunRecovery(snapshot({ events: [] }), runId);
    const mismatched = resolveServerRunRecovery({ ...snapshot(), run_id: 'another-run' }, runId);

    expect(completed).toEqual({ kind: 'discard', reason: 'completed' });
    expect(failed).toEqual({ kind: 'discard', reason: 'failed' });
    expect(empty).toEqual({ kind: 'discard', reason: 'empty' });
    expect(mismatched).toEqual({ kind: 'discard', reason: 'invalid' });
  });

  it('restores a failed run when the backend marks it recoverable', () => {
    const resolution = resolveServerRunRecovery(snapshot({
      events: [
        event('run_started'),
        event('node_completed', 'summary', 2),
        {
          ...event('node_failed', 'outline', 3),
          recovery_state: { status: 'degraded', needs_recovery: true },
        },
        {
          ...event('run_failed', 'outline', 4),
          recovery_state: { status: 'degraded', needs_recovery: true },
        },
      ],
      state: {
        current_checkpoint_stage_id: 'summary',
        current_stage_id: 'outline',
        runtime_phase: 'failed',
        recovery_state: {
          status: 'degraded',
          needs_recovery: true,
          last_stable_checkpoint: { node_id: 'summary', output_key: 'summary' },
        },
      },
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(false);
    expect(resolution.hydrated.selectedId).toBe('outline');
    expect(resolution.hydrated.runControlState).toBe('paused');
    expect(resolution.hydrated.paused).toBe(true);
  });

  it('reconnects a streaming run after recovery despite earlier failure events', () => {
    const resolution = resolveServerRunRecovery(snapshot({
      events: [
        event('run_started', '', 1),
        {
          ...event('run_failed', 'outline', 2),
          recovery_state: { status: 'degraded', needs_recovery: true },
        },
        event('run_recovery_required', 'outline', 3),
        event('run_checkpoint_recovery_requested', 'outline', 4),
        event('node_started', 'outline', 5),
      ],
      paused: false,
      state: {
        current_checkpoint_stage_id: 'summary',
        current_stage_id: 'outline',
        runtime_phase: 'stage_streaming',
        recovery_state: { status: 'closed', needs_recovery: false },
      },
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(true);
    expect(resolution.hydrated.runControlState).toBe('running');
    expect(resolution.hydrated.paused).toBe(false);
    expect(resolution.hydrated.selectedId).toBe('outline');
  });

  it('keeps a restored checkpoint paused after refresh despite earlier failure events', () => {
    const resolution = resolveServerRunRecovery(snapshot({
      events: [
        event('run_started', '', 1),
        {
          ...event('run_failed', 'outline', 2),
          recovery_state: { status: 'degraded', needs_recovery: true },
        },
        event('run_recovery_required', 'outline', 3),
        event('run_snapshot_restored', 'summary', 4),
      ],
      paused: true,
      state: {
        current_checkpoint_stage_id: 'summary',
        current_stage_id: 'summary',
        runtime_phase: 'checkpoint_recovery',
        recovery_state: { status: 'closed', needs_recovery: false },
      },
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(false);
    expect(resolution.hydrated.runControlState).toBe('paused');
    expect(resolution.hydrated.paused).toBe(true);
    expect(resolution.hydrated.selectedId).toBe('summary');
  });

  it('opens a later stable checkpoint after an earlier failed attempt and keeps it paused', () => {
    const resolution = resolveHistoricalRunOpen(snapshot({
      events: [
        event('run_started', '', 1),
        event('run_failed', 'summary', 2),
        event('stage_checkpoint_ready', 'summary', 3),
        event('stage_artifact_confirmed', 'summary', 4),
      ],
      paused: false,
      state: {
        current_checkpoint_stage_id: 'summary',
        current_stage_id: 'summary',
        runtime_phase: 'stage_ready_to_continue',
        stage_confirmation_state: { summary: { status: 'confirmed', node_id: 'summary' } },
      },
    }), runId);

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.reconnect).toBe(false);
    expect(resolution.hydrated.runControlState).toBe('paused');
    expect(resolution.hydrated.paused).toBe(true);
    expect(resolution.hydrated.selectedId).toBe('summary');
    expect(resolution.hydrated.checkpointContinueReady).toBe(true);
  });

  it('hydrates trimmed historical events from persisted completed stages and artifacts', () => {
    const hydrated = hydrateRunFromStoredState(snapshot({
      events: [
        event('node_completed', 'export', 9),
        { ...event('artifact_validation_failed', 'summary', 8), errors: ['旧校验失败'] },
      ],
      state: {
        approved_artifacts: {},
        artifacts: {
          chapters: { chapters: [{ id: 'chapter-1', content: '正文' }] },
          detail_outline: { chapters: [{ chapter: '第一章' }] },
          export: { package_ready: true },
          info_recommend: { selected_title: '雾港旧声' },
          outline: { volumes: [{ title: '第一卷' }] },
          summary: { full_synopsis: '梗概' },
        },
        completed_stage_ids: ['info', 'summary', 'outline', 'detail', 'text'],
        current_checkpoint_stage_id: 'export',
        current_stage_id: 'export',
        runtime_phase: 'awaiting_stage_confirmation',
        stage_display_artifacts: {},
      },
    }), runId);

    const completed = hydrated.events
      .filter((item) => item.type === 'node_completed')
      .map((item) => item.node_id);
    expect(completed).toEqual(expect.arrayContaining(['info', 'summary', 'outline', 'detail', 'text', 'export']));
    expect(completed.filter((id) => id === 'export')).toHaveLength(1);
    expect(hydrated.events.find((item) => item.node_id === 'summary' && item.artifact)?.artifact).toEqual({ full_synopsis: '梗概' });
    expect(hydrated.events.find((item) => item.node_id === 'detail' && item.artifact)?.artifact).toEqual({ chapters: [{ chapter: '第一章' }] });
    expect(hydrated.selectedId).toBe('export');
  });

  it('keeps a currently failed run closed when no recovery state is present', () => {
    const resolution = resolveHistoricalRunOpen(snapshot({
      events: [
        event('run_started', '', 1),
        event('run_failed', 'summary', 2),
      ],
      state: {
        current_stage_id: 'summary',
        runtime_phase: 'failed',
      },
    }), runId);

    expect(resolution).toEqual({ kind: 'discard', reason: 'failed' });
  });

  it('keeps completed runs read-only instead of restoring them', () => {
    const resolution = resolveHistoricalRunOpen(snapshot({
      events: [
        event('run_started', '', 1),
        event('run_completed', 'export', 2),
      ],
      state: { current_stage_id: 'export' },
    }), runId);

    expect(resolution).toEqual({ kind: 'discard', reason: 'completed' });
  });

  it('keeps a valid local checkpoint paused when the server is unavailable', () => {
    const resolution = resolveCachedRunRecovery({
      activeRunId: runId,
      events: [
        event('artifact_approved', 'info', 5),
        event('approval_required', 'info', 4),
        event('stage_checkpoint_ready', 'info', 3),
        event('run_started', '', 1),
      ],
      paused: true,
      runControlState: 'paused',
      selectedId: 'info',
    });

    expect(resolution.kind).toBe('restore');
    if (resolution.kind !== 'restore') return;
    expect(resolution.source).toBe('cache');
    expect(resolution.reconnect).toBe(false);
    expect(resolution.hydrated.infoContinueReady).toBe(true);
    expect(resolution.hydrated.paused).toBe(true);
  });
});

function snapshot(overrides: Partial<StoredRunSnapshot> = {}): StoredRunSnapshot {
  return {
    run_id: runId,
    events: [],
    paused: false,
    state: {},
    ...overrides,
  };
}

function event(type: string, nodeId = '', order = 1): RunEvent {
  return {
    type,
    run_id: runId,
    node_id: nodeId || undefined,
    created_at: `2026-07-16T00:00:${String(order).padStart(2, '0')}Z`,
  };
}
