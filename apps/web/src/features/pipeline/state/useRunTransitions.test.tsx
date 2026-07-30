// @vitest-environment happy-dom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SETTLEMENT_DWELL_MS, useRunTransitions, type RunTransitions } from './useRunTransitions';
import type { RunAction } from './runReducer';
import type { WorkflowStage } from '../contracts';

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const stages = [{ id: 'summary' }, { id: 'outline' }] as WorkflowStage[];

function Harness({ dispatch, expose }: { dispatch: (action: RunAction) => void; expose: (value: RunTransitions) => void }) {
  expose(useRunTransitions({ dispatchRun: dispatch, stages }));
  return null;
}

describe('settlement dwell state machine (D7)', () => {
  let container: HTMLDivElement;
  let root: Root;
  let dispatched: RunAction[];
  let transitions: RunTransitions;

  beforeEach(() => {
    vi.useFakeTimers();
    dispatched = [];
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => {
      root.render(
        <Harness
          dispatch={(action) => dispatched.push(action)}
          expose={(value) => {
            transitions = value;
          }}
        />,
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.useRealTimers();
  });

  it('route settlements dwell until the 4s auto-continue, then navigate once', () => {
    act(() => transitions.startSettlement({ kind: 'route', nextStageId: 'outline', stageId: 'summary' }));
    expect(transitions.settlementStageId).toBe('summary');
    expect(transitions.settlementDwell).toBe(true);

    act(() => vi.advanceTimersByTime(SETTLEMENT_DWELL_MS - 1));
    expect(transitions.settlementStageId).toBe('summary');
    expect(dispatched).toHaveLength(0);

    act(() => vi.advanceTimersByTime(1));
    expect(transitions.settlementStageId).toBe('');
    expect(dispatched).toEqual([{ type: 'stage_selected', stageId: 'outline' }]);
  });

  it('user 继续 completes immediately and cancels the auto-continue', () => {
    act(() => transitions.startSettlement({ kind: 'route', nextStageId: 'outline', stageId: 'summary' }));
    act(() => transitions.continueSettlement());
    expect(transitions.settlementStageId).toBe('');
    expect(dispatched).toEqual([{ type: 'stage_selected', stageId: 'outline' }]);

    act(() => vi.advanceTimersByTime(SETTLEMENT_DWELL_MS * 2));
    expect(dispatched).toHaveLength(1);
  });

  it('cockpit auto settlements keep the non-blocking auto-advance timing', () => {
    act(() => transitions.startSettlement({ kind: 'cockpit_auto', nextStageId: 'outline', stageId: 'summary' }));
    expect(transitions.settlementDwell).toBe(false);

    act(() => vi.advanceTimersByTime(900));
    expect(dispatched).toEqual([{ type: 'stage_selected', stageId: 'outline' }]);

    act(() => vi.advanceTimersByTime(300));
    expect(transitions.settlementStageId).toBe('');
  });
});
