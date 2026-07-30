import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createRunControlSaver, isRunControlFlushPoint } from './runControlPersistence';
import type { StoredRunControlState } from './storage';

function snapshot(marker: number, overrides: Partial<StoredRunControlState> = {}): StoredRunControlState {
  return {
    activeRunId: 'run-1',
    events: [{ type: 'chapter_delta', run_id: 'run-1', delta: `delta-${marker}` }],
    paused: false,
    runControlState: 'running',
    selectedId: 'text',
    workspacePhase: 'running',
    ...overrides,
  };
}

describe('createRunControlSaver (F2)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('coalesces high-frequency events into at most one write per second', () => {
    const writes: StoredRunControlState[] = [];
    const saver = createRunControlSaver((state) => writes.push(state));

    for (let i = 0; i < 60; i += 1) saver.schedule(snapshot(i));
    expect(writes).toHaveLength(0);

    vi.advanceTimersByTime(1000);
    expect(writes).toHaveLength(1);
    expect(writes[0].events?.[0]?.delta).toBe('delta-59');

    for (let i = 60; i < 120; i += 1) saver.schedule(snapshot(i));
    vi.advanceTimersByTime(1000);
    expect(writes).toHaveLength(2);
    expect(writes[1].events?.[0]?.delta).toBe('delta-119');
  });

  it('flush persists the latest snapshot immediately without a later double write', () => {
    const writes: StoredRunControlState[] = [];
    const saver = createRunControlSaver((state) => writes.push(state));

    saver.schedule(snapshot(1));
    saver.schedule(snapshot(2));
    saver.flush();
    expect(writes).toHaveLength(1);
    expect(writes[0].events?.[0]?.delta).toBe('delta-2');

    vi.advanceTimersByTime(5000);
    expect(writes).toHaveLength(1);

    saver.flush();
    expect(writes).toHaveLength(1);
  });

  it('dispose drops pending state and timers', () => {
    const writes: StoredRunControlState[] = [];
    const saver = createRunControlSaver((state) => writes.push(state));
    saver.schedule(snapshot(1));
    saver.dispose();
    vi.advanceTimersByTime(5000);
    expect(writes).toHaveLength(0);
  });
});

describe('isRunControlFlushPoint (F2)', () => {
  it('flushes on pause/complete/fail states and their run events', () => {
    expect(isRunControlFlushPoint('paused')).toBe(true);
    expect(isRunControlFlushPoint('completed')).toBe(true);
    expect(isRunControlFlushPoint('failed')).toBe(true);
    expect(isRunControlFlushPoint('running', 'run_paused')).toBe(true);
    expect(isRunControlFlushPoint('running', 'run_failed')).toBe(true);
    expect(isRunControlFlushPoint('running', 'run_recovery_required')).toBe(true);
  });

  it('keeps ordinary streaming events on the throttled path', () => {
    expect(isRunControlFlushPoint('running', 'chapter_delta')).toBe(false);
    expect(isRunControlFlushPoint('running')).toBe(false);
    expect(isRunControlFlushPoint('idle')).toBe(false);
  });
});
