import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import type { HydratedRunState } from './runState';
import { createInitialRunState, runReducer } from './runReducer';

describe('run reducer', () => {
  it('creates the stable run state from stored control and events', () => {
    const memory = event('memory_context_loaded', 'detail');
    const state = initialState({
      activeRunId: 'stored-run',
      events: [memory],
      paused: true,
      runControlState: 'paused',
      selectedId: 'detail',
      workspacePhase: 'running',
    });

    expect(state.activeRunId).toBe('stored-run');
    expect(state.selectedInspectorTarget).toEqual({ kind: 'stage', id: 'detail' });
    expect(state.memoryEvents).toEqual([memory]);
    expect(state.running).toBe(false);
  });

  it('starts a run atomically when the server confirms it', () => {
    const state = runReducer(initialState(), {
      type: 'event_received',
      event: event('run_started', 'info'),
    });

    expect(state.activeRunId).toBe('reducer-test');
    expect(state.running).toBe(true);
    expect(state.paused).toBe(false);
    expect(state.runControlState).toBe('running');
    expect(state.events[0].type).toBe('run_started');
  });

  it('selects the active stage for navigation events but ignores finalizing starts', () => {
    const started = runReducer(initialState(), {
      type: 'event_received',
      event: event('node_started', 'summary'),
    });
    const finalizing = runReducer(started, {
      type: 'event_received',
      event: { ...event('node_started', 'outline'), phase: 'finalizing' },
    });

    expect(started.selectedId).toBe('summary');
    expect(started.workspacePhase).toBe('running');
    expect(started.selectedInspectorTarget).toEqual({ kind: 'stage', id: 'summary' });
    expect(finalizing.selectedId).toBe('summary');
  });

  it('keeps only the newest 40 memory events', () => {
    let state = initialState();
    for (let index = 0; index < 45; index += 1) {
      state = runReducer(state, {
        type: 'event_received',
        event: { ...event('memory_writeback_completed', 'text'), message: String(index) },
      });
    }

    expect(state.memoryEvents).toHaveLength(40);
    expect(state.memoryEvents[0].message).toBe('44');
    expect(state.memoryEvents[state.memoryEvents.length - 1]?.message).toBe('5');
  });

  it('moves pause and resume fields together', () => {
    const running = runReducer(initialState(), {
      type: 'event_received',
      event: event('run_started', 'text'),
    });
    const paused = runReducer(running, {
      type: 'event_received',
      event: event('run_paused', 'text'),
    });
    const resumed = runReducer(paused, {
      type: 'event_received',
      event: event('run_resumed', 'text'),
    });

    expect(paused).toMatchObject({ paused: true, running: false, runControlState: 'paused' });
    expect(resumed).toMatchObject({ paused: false, running: true, runControlState: 'running' });
  });

  it('shows approval as waiting without inventing a completed run state', () => {
    const state = runReducer(initialState(), {
      type: 'event_received',
      event: { ...event('approval_required', 'info'), artifact: { title: '候选标题' } },
    });

    expect(state.selectedId).toBe('info');
    expect(state.latestResult).toContain('等待你确认定稿');
    expect(state.runControlState).toBe('idle');
  });

  it('keeps validation diagnostic until the terminal node failure arrives', () => {
    const invalid = runReducer(initialState(), {
      type: 'event_received',
      event: { ...event('artifact_validation_failed', 'outline'), error: 'volumes 缺失' },
    });
    const failed = runReducer(invalid, {
      type: 'event_received',
      event: { ...event('node_failed', 'outline'), error: '大纲生成失败' },
    });

    expect(invalid.runControlState).toBe('idle');
    expect(invalid.latestResult).toContain('volumes 缺失');
    expect(failed.runControlState).toBe('failed');
    expect(failed.latestResult).toBe('大纲生成失败');
  });

  it('keeps a recoverable node failure paused at the stable checkpoint', () => {
    const failed = runReducer(initialState({ activeRunId: 'recoverable-run', runControlState: 'running' }), {
      type: 'event_received',
      event: {
        ...event('node_failed', 'outline'),
        error: 'Provider timeout',
        recovery_state: { status: 'degraded', needs_recovery: true },
      },
    });

    expect(failed).toMatchObject({ paused: true, running: false, runControlState: 'paused' });
    expect(failed.latestResult).toContain('Provider timeout');
  });

  it('keeps budget warnings from stopping an active run (D5: bar consumes the event)', () => {
    const running = runReducer(initialState(), {
      type: 'event_received',
      event: event('run_started', 'summary'),
    });
    const warned = runReducer(running, {
      type: 'event_received',
      event: { ...event('stage_budget_warning', 'summary'), used_tokens: 8000, max_tokens: 10000 },
    });

    expect(warned).toMatchObject({ paused: false, running: true, runControlState: 'running' });
    expect(warned.events[0]?.type).toBe('stage_budget_warning');
  });

  it('pauses immediately when a provider call is blocked by budget', () => {
    const blocked = runReducer(initialState({ runControlState: 'running' }), {
      type: 'event_received',
      event: { ...event('run_budget_exceeded', 'text'), message: '本次运行 Token 预算已用尽' },
    });

    expect(blocked).toMatchObject({ paused: true, running: false, runControlState: 'paused' });
  });

  it('distinguishes completed runs from export-ready waiting', () => {
    const completed = runReducer(initialState(), {
      type: 'event_received',
      event: event('run_completed', 'export'),
    });
    const exportReady = runReducer(initialState(), {
      type: 'event_received',
      event: event('run_export_ready', 'export'),
    });

    expect(completed).toMatchObject({ running: false, runControlState: 'completed' });
    expect(exportReady).toMatchObject({ running: false, runControlState: 'running' });
    expect(exportReady.latestResult).toContain('等待人工下载');
  });

  it('restores and resets all stable run fields as one transition', () => {
    const restored = runReducer(initialState(), {
      type: 'run_restored',
      hydrated: hydratedState(),
    });
    const reset = runReducer(restored, { type: 'run_reset', stageId: 'info' });

    expect(restored).toMatchObject({
      activeRunId: 'restored-run',
      paused: true,
      runControlState: 'paused',
      selectedId: 'cover',
      workspacePhase: 'running',
    });
    expect(reset).toMatchObject({
      activeRunId: '',
      events: [],
      memoryEvents: [],
      paused: false,
      runControlState: 'idle',
      running: false,
      selectedId: 'info',
      workspacePhase: 'planning',
    });
  });
});

function initialState(overrides: Partial<Parameters<typeof createInitialRunState>[0]> = {}) {
  return createInitialRunState({
    activeRunId: '',
    events: [],
    paused: false,
    runControlState: 'idle',
    selectedId: 'info',
    stageId: 'info',
    workspacePhase: 'planning',
    ...overrides,
  });
}

function hydratedState(): HydratedRunState {
  const memory = event('memory_context_loaded', 'cover');
  return {
    activeRunId: 'restored-run',
    approvalDraft: '',
    approvalPending: false,
    approvalSource: '',
    automationCockpitReady: true,
    checkpointContinueReady: false,
    checkpointStageId: '',
    events: [memory],
    infoContinueReady: false,
    paused: true,
    runControlState: 'paused',
    selectedId: 'cover',
  };
}

function event(type: string, nodeId: string): RunEvent {
  return { type, run_id: 'reducer-test', node_id: nodeId };
}
