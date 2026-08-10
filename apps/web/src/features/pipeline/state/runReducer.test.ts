import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import type { HydratedRunState } from './runState';
import { createInitialRunState, runReducer } from './runReducer';

describe('run reducer', () => {
  it('creates the stable run state from stored control and events', () => {
    const memory = event('evidence.proposed', 'detail');
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
      event: event('run.started', 'info'),
    });

    expect(state.activeRunId).toBe('reducer-test');
    expect(state.running).toBe(true);
    expect(state.paused).toBe(false);
    expect(state.runControlState).toBe('running');
    expect(state.events[0].type).toBe('run.started');
  });

  it('selects the active stage for Graph node events', () => {
    const started = runReducer(initialState(), {
      type: 'event_received',
      event: event('node.started', 'summary'),
    });
    const finalizing = runReducer(started, {
      type: 'event_received',
      event: event('node.completed', 'outline'),
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
        event: { ...event('writeback.committed', 'text'), payload: { message: String(index) } },
      });
    }

    expect(state.memoryEvents).toHaveLength(40);
    expect(state.memoryEvents[0].payload?.message).toBe('44');
    expect(state.memoryEvents[state.memoryEvents.length - 1]?.payload?.message).toBe('5');
  });

  it('moves pause and resume fields through the decision interrupt', () => {
    const running = runReducer(initialState(), {
      type: 'event_received',
      event: event('run.started', 'text'),
    });
    const paused = runReducer(running, {
      type: 'event_received',
      event: event('decision.required', 'text'),
    });
    const resumed = runReducer(paused, {
      type: 'event_received',
      event: event('decision.resolved', 'text'),
    });

    expect(paused).toMatchObject({ paused: true, running: false, runControlState: 'paused' });
    expect(resumed).toMatchObject({ paused: false, running: true, runControlState: 'running' });
  });

  it('shows approval as waiting without inventing a completed run state', () => {
    const state = runReducer(initialState(), {
      type: 'event_received',
      event: { ...event('decision.required', 'info'), payload: { decision_type: 'stage_artifact_decision' } },
    });

    expect(state.selectedId).toBe('info');
    expect(state.latestResult).toContain('等待你的决定');
    expect(state.runControlState).toBe('paused');
  });

  it('keeps validation diagnostic until the terminal node failure arrives', () => {
    const invalid = runReducer(initialState(), {
      type: 'event_received',
      event: { ...event('evidence.proposed', 'outline'), payload: { message: 'volumes 缺失' } },
    });
    const failed = runReducer(invalid, {
      type: 'event_received',
      event: { ...event('node.failed', 'outline'), payload: { message: '大纲生成失败' } },
    });

    expect(invalid.runControlState).toBe('idle');
    expect(invalid.latestResult).toContain('正文证据提案');
    expect(failed.runControlState).toBe('failed');
    expect(failed.latestResult).toBe('大纲生成失败');
  });

  it('treats node failure as a Graph terminal failure without recovery flags', () => {
    const failed = runReducer(initialState({ activeRunId: 'recoverable-run', runControlState: 'running' }), {
      type: 'event_received',
      event: {
        ...event('node.failed', 'outline'),
        payload: { message: 'Provider timeout' },
      },
    });

    expect(failed).toMatchObject({ paused: false, running: false, runControlState: 'failed' });
    expect(failed.latestResult).toContain('Provider timeout');
  });

  it('pauses immediately when a Graph decision is required', () => {
    const blocked = runReducer(initialState({ runControlState: 'running' }), {
      type: 'event_received',
      event: { ...event('decision.required', 'text'), payload: { decision_id: 'decision-1', domain_revision: 1 } },
    });

    expect(blocked).toMatchObject({ paused: true, running: false, runControlState: 'paused' });
  });

  it('distinguishes a completed run from a saved export artifact', () => {
    const completed = runReducer(initialState(), {
      type: 'event_received',
      event: event('run.completed', 'export'),
    });
    const exportReady = runReducer(initialState(), {
      type: 'event_received',
      event: event('artifact.committed', 'export'),
    });

    expect(completed).toMatchObject({ running: false, runControlState: 'completed' });
    expect(exportReady).toMatchObject({ running: false, runControlState: 'idle' });
    expect(exportReady.latestResult).toContain('正式写回');
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
  const memory = event('evidence.proposed', 'cover');
  return {
    activeRunId: 'restored-run',
    inputs: undefined,
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
  return runEvent(type, { run_id: 'reducer-test', stage_id: nodeId as RunEvent['stage_id'], node_id: `${nodeId}.test` });
}
