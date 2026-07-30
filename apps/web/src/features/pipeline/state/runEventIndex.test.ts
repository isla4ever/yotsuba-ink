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
} from './runEventIndex';
import { createInitialRunState, runReducer } from './runReducer';
import { hasRecoverableRun, hasRunningNodeFromEvents } from './runSelectors';
import { latestNodeStatus } from '../planning/cockpitRuntime';
import type { RunControlState, RunEvent } from '../contracts';

const stageIds = ['info', 'summary', 'outline', 'detail', 'text', 'cover', 'export'];

function event(type: string, nodeId = '', extra: Partial<RunEvent> = {}): RunEvent {
  return { type, run_id: 'run-1', ...(nodeId ? { node_id: nodeId } : {}), ...extra } as RunEvent;
}

/** Deterministic pseudo-random event stream covering the hot selector inputs. */
function syntheticStream(length: number): RunEvent[] {
  const types = [
    'node_started', 'node_completed', 'artifact_stream_delta', 'chapter_delta',
    'stage_usage_updated', 'quality_check_completed', 'stage_checkpoint_ready',
    'stage_artifact_confirmed', 'artifact_approved', 'memory_context_loaded',
  ];
  const chronological: RunEvent[] = [];
  let seed = 42;
  for (let step = 0; step < length; step += 1) {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    const type = types[seed % types.length];
    const nodeId = stageIds[seed % stageIds.length];
    const phase = seed % 7 === 0 ? 'finalizing' : undefined;
    chronological.push(event(type, nodeId, phase ? { phase } : {}));
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

  it('index selectors match the legacy event scans on a synthetic run', () => {
    const streams: RunEvent[][] = [
      [],
      [event('node_started', 'info')],
      [event('node_started', 'info', { phase: 'finalizing' })],
      [event('node_completed', 'info'), event('node_started', 'info')],
      [event('run_completed'), event('node_started', 'text')],
      [event('node_failed', 'text'), event('node_started', 'text')],
      [event('run_recovery_required'), event('node_started', 'summary')],
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

  it('derives completed stage ids from real node_completed events (D4 source)', () => {
    const newestFirst = [
      event('node_completed', 'summary'),
      event('node_completed', 'info'),
      event('node_completed', 'info'),
      event('node_started', 'outline'),
    ];
    expect(indexedCompletedStageIds(buildRunEventIndex(newestFirst))).toEqual(['summary', 'info']);
  });

  it('reducer keeps events and index equivalent across the 500-event trim', () => {
    let state = createInitialRunState({
      activeRunId: 'run-1',
      events: [],
      paused: false,
      runControlState: 'running',
      selectedId: 'info',
      stageId: 'info',
      workspacePhase: 'running',
    });
    for (const item of syntheticStream(RUN_EVENT_LIMIT + 40)) {
      state = runReducer(state, { type: 'event_received', event: item });
    }
    expect(state.events.length).toBe(RUN_EVENT_LIMIT);
    expect(state.eventIndex).toEqual(buildRunEventIndex(state.events));
    expect(indexedRunningNodeExists(state.eventIndex)).toBe(hasRunningNodeFromEvents(state.events));
  });
});
