// @vitest-environment happy-dom
import { act, memo } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  PipelineShellProvider,
  useRunEventsSelector,
  useRunStateContext,
} from './pipelineShellContext';
import {
  buildTestRunState,
  buildTestUICommands,
  buildTestWorkflowConfig,
} from './PipelineShellTestProviders';
import { appendRunEvent, buildRunEventIndex, indexedCompletedStageIds } from './runEventIndex';
import { createRunEventsStore, type RunEventsSnapshot } from './runEventsStore';
import type { RunEvent } from '../contracts';

/**
 * Phase 12 F5 render-isolation evidence: streaming deltas published to the
 * run-events store must not re-render shell chrome that reads only the
 * low-frequency RunState slice, while selector subscribers re-render exactly
 * when their selected value changes.
 */

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

const renders = { events: 0, shell: 0 };

const ShellChromeProbe = memo(function ShellChromeProbe() {
  const run = useRunStateContext();
  renders.shell += 1;
  return <span data-run={run.activeRunId} />;
});

function CompletedStagesProbe() {
  const completed = useRunEventsSelector(
    (snapshot) => indexedCompletedStageIds(snapshot.index).length,
  );
  renders.events += 1;
  return <span data-completed={completed} />;
}

function delta(sequence: number): RunEvent {
  return { type: 'chapter_delta', run_id: 'run-1', node_id: 'text', delta: `字${sequence}` } as RunEvent;
}

function snapshotWith(previous: RunEventsSnapshot, event: RunEvent): RunEventsSnapshot {
  return { events: [event, ...previous.events], index: appendRunEvent(previous.index, event) };
}

describe('PipelineShellProvider run-events split (F5)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    renders.events = 0;
    renders.shell = 0;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('streaming deltas re-render zero shell-chrome components', () => {
    const store = createRunEventsStore({ events: [], index: buildRunEventIndex([]) });
    act(() => {
      root.render(
        <PipelineShellProvider
          runEvents={store}
          runState={buildTestRunState({ activeRunId: 'run-1', runHasStarted: true })}
          uiCommands={buildTestUICommands()}
          workflowConfig={buildTestWorkflowConfig()}
        >
          <ShellChromeProbe />
          <CompletedStagesProbe />
        </PipelineShellProvider>,
      );
    });
    const shellRendersAfterMount = renders.shell;
    expect(shellRendersAfterMount).toBeGreaterThan(0);

    let snapshot = store.getSnapshot();
    act(() => {
      for (let sequence = 0; sequence < 40; sequence += 1) {
        snapshot = snapshotWith(snapshot, delta(sequence));
        store.publish(snapshot);
      }
    });

    // 40 streaming deltas: the shell probe (memoized, slice-only) never re-rendered.
    expect(renders.shell).toBe(shellRendersAfterMount);
  });

  it('selector subscribers re-render only when the selected value changes', () => {
    const store = createRunEventsStore({ events: [], index: buildRunEventIndex([]) });
    act(() => {
      root.render(
        <PipelineShellProvider
          runEvents={store}
          runState={buildTestRunState()}
          uiCommands={buildTestUICommands()}
          workflowConfig={buildTestWorkflowConfig()}
        >
          <CompletedStagesProbe />
        </PipelineShellProvider>,
      );
    });
    const mountRenders = renders.events;

    let snapshot = store.getSnapshot();
    act(() => {
      for (let sequence = 0; sequence < 25; sequence += 1) {
        snapshot = snapshotWith(snapshot, delta(sequence));
        store.publish(snapshot);
      }
    });
    // Deltas never change the completed-stage count: zero extra renders.
    expect(renders.events).toBe(mountRenders);

    act(() => {
      snapshot = snapshotWith(snapshot, { type: 'node_completed', run_id: 'run-1', node_id: 'info' } as RunEvent);
      store.publish(snapshot);
    });
    // A real completion changes the selected value: exactly one more render.
    expect(renders.events).toBe(mountRenders + 1);
    expect(container.querySelector('[data-completed]')?.getAttribute('data-completed')).toBe('1');
  });
});
