import { describe, expect, it } from 'vitest';
import {
  appendRunEvent,
  buildRunEventIndex,
  emptyRunEventIndex,
  indexedCompletedStageIds,
  indexedHasRecoverableRun,
  indexedRunningNodeExists,
  indexedStageStatus,
  RUN_EVENT_LIMIT,
  trimRunEventWindow,
} from './runEventIndex';
import { createInitialRunState, runReducer } from './runReducer';
import { hasRecoverableRun, hasRunningNodeFromEvents } from './runSelectors';
import { latestNodeStatus } from '../planning/cockpitRuntime';
import type { RunControlState, RunEvent } from '../contracts';
import { runEvent as makeRunEvent } from '../contracts/runEventTestFactory';

const stageIds = ['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export'];

function event(type: string, nodeId = '', extra: Partial<RunEvent> = {}): RunEvent {
  return makeRunEvent(type, {
    run_id: 'run-1',
    ...(nodeId ? { stage_id: nodeId as RunEvent['stage_id'], node_id: `${nodeId}.generate_candidate` } : {}),
    ...extra,
  });
}

/** Deterministic pseudo-random event stream covering the hot selector inputs. */
function syntheticStream(length: number): RunEvent[] {
  const types = [
    'node.started', 'node.completed', 'checkpoint.saved', 'review.started',
    'review.completed', 'artifact.candidate_ready', 'decision.required',
    'writeback.queued', 'writeback.committed', 'checkpoint.saved',
  ];
  const chronological: RunEvent[] = [];
  let seed = 42;
  for (let step = 0; step < length; step += 1) {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    const type = types[seed % types.length];
    const nodeId = stageIds[seed % stageIds.length];
    chronological.push(event(type, nodeId));
  }
  return chronological;
}

describe('runEventIndex (F6)', () => {
  it('append path stays equivalent to a full rebuild', () => {
    const chronological = syntheticStream(120);
    let appended = emptyRunEventIndex();
    for (const item of chronological) appended = appendRunEvent(appended, item);
    const rebuilt = buildRunEventIndex([...chronological].reverse());
    expect(appended).toEqual(rebuilt);
  });

  it('index selectors match direct stable-event scans on a synthetic run', () => {
    const streams: RunEvent[][] = [
      [],
      [event('node.started', 'brief')],
      [event('artifact.committed', 'brief', { node_id: 'brief.commit_artifact', payload: {} })],
      [event('node.completed', 'brief'), event('node.started', 'brief')],
      [event('run.completed'), event('node.started', 'text')],
      [event('run.failed', 'text'), event('node.started', 'text')],
      [...syntheticStream(80)].reverse(),
    ];
    const controls: RunControlState[] = ['idle', 'running', 'paused', 'completed', 'failed'];
    for (const newestFirst of streams) {
      const index = buildRunEventIndex(newestFirst);
      expect(indexedRunningNodeExists(index)).toBe(hasRunningNodeFromEvents(newestFirst));
      for (const control of controls) {
        expect(indexedHasRecoverableRun('run-1', index, control))
          .toBe(hasRecoverableRun('run-1', newestFirst, control));
      }
      for (const stageId of stageIds) {
        expect(indexedStageStatus(index, stageId)).toBe(latestNodeStatus(newestFirst, stageId).status);
      }
    }
  });

  it('derives completed stage ids from committed Artifacts', () => {
    const newestFirst = [
      event('artifact.committed', 'spine', { node_id: 'spine.commit_artifact', payload: {} }),
      event('artifact.committed', 'brief', { node_id: 'brief.commit_artifact', payload: {} }),
      event('artifact.committed', 'brief', { node_id: 'brief.commit_artifact', payload: {} }),
      event('node.started', 'volumes'),
    ];
    expect(indexedCompletedStageIds(buildRunEventIndex(newestFirst))).toEqual(['spine', 'brief']);
  });

  it('keeps a human interrupt distinct from active generation', () => {
    const awaiting = buildRunEventIndex([
      event('checkpoint.saved', 'cast'),
      event('decision.required', 'cast'),
      event('artifact.candidate_ready', 'cast'),
    ]);
    expect(indexedStageStatus(awaiting, 'cast')).toBe('awaiting');

    const resumed = buildRunEventIndex([
      event('decision.resolved', 'cast'),
      event('decision.required', 'cast'),
    ]);
    expect(indexedStageStatus(resumed, 'cast')).toBe('running');
  });

  it('does not let a later checkpoint diagnostic erase stage completion', () => {
    const index = buildRunEventIndex([
      event('checkpoint.saved', 'spine'),
      event('artifact.committed', 'spine', { node_id: 'spine.commit_artifact', payload: {} }),
    ]);
    expect(indexedStageStatus(index, 'spine')).toBe('done');
  });

  it('reducer keeps events and index equivalent across the 500-event trim', () => {
    let state = createInitialRunState({
      activeRunId: 'run-1',
      events: [],
      paused: false,
      runControlState: 'running',
      selectedId: 'brief',
      stageId: 'brief',
      workspacePhase: 'running',
    });
    for (const item of syntheticStream(RUN_EVENT_LIMIT + 40)) {
      state = runReducer(state, { type: 'event_received', event: item });
    }
    expect(state.events.length).toBe(RUN_EVENT_LIMIT);
    expect(state.eventIndex).toEqual(buildRunEventIndex(state.events));
    expect(indexedRunningNodeExists(state.eventIndex)).toBe(hasRunningNodeFromEvents(state.events));
  });

  it('pins stage-closing events past the trim window so early stages stay done', () => {
    let state = createInitialRunState({
      activeRunId: 'run-1',
      events: [],
      paused: false,
      runControlState: 'running',
      selectedId: 'brief',
      stageId: 'brief',
      workspacePhase: 'running',
    });
    const receive = (item: RunEvent) => {
      state = runReducer(state, { type: 'event_received', event: item });
    };
    receive(event('artifact.committed', 'brief', { node_id: 'brief.commit_artifact', payload: {} }));
    receive(event('artifact.committed', 'spine', { node_id: 'spine.commit_artifact', payload: {} }));
    for (let step = 0; step < RUN_EVENT_LIMIT + 10; step += 1) {
      receive(event('node.started', 'text'));
    }
    // Window keeps the newest events plus one pinned closing event per stage.
    expect(state.events.length).toBe(RUN_EVENT_LIMIT + 2);
    expect(indexedStageStatus(state.eventIndex, 'brief')).toBe('done');
    expect(indexedStageStatus(state.eventIndex, 'spine')).toBe('done');
    expect(state.eventIndex).toEqual(buildRunEventIndex(state.events));
  });

  it('trimRunEventWindow keeps at most one pinned closing event per stage', () => {
    const closing = (stage: string) => event('artifact.committed', stage, { node_id: `${stage}.commit_artifact`, payload: {} });
    const filler = Array.from({ length: RUN_EVENT_LIMIT }, () => event('node.started', 'text'));
    const newestFirst = [...filler, closing('brief'), closing('brief'), closing('spine')];
    const trimmed = trimRunEventWindow(newestFirst);
    expect(trimmed.length).toBe(RUN_EVENT_LIMIT + 2);
    const pinnedStages = trimmed.slice(RUN_EVENT_LIMIT).map((item) => item.stage_id);
    expect(pinnedStages).toEqual(['brief', 'spine']);
    expect(trimRunEventWindow(filler)).toBe(filler);
  });
});
