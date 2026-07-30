import type { RunControlState, RunEvent } from '../contracts';

/**
 * Phase 12 F6: incremental per-type / per-stage index over the newest-first
 * run event list. The reducer appends to it on every `event_received`, so hot
 * selectors (run-active detection, recoverability, per-stage runtime status)
 * read O(1)/O(#stages) instead of re-scanning up to 500 events per render.
 */

export const RUN_EVENT_LIMIT = 500;

export type StageRunStatus = 'idle' | 'running' | 'done' | 'attention' | 'failed';

type StageLifecycle = {
  /** Latest `node_*` event type for the stage (run-active semantics). */
  nodeEventType: string;
  nodeEventPhase: string;
  /** Latest status event (node_*, run_error, stage_artifact_confirmed, artifact_approved). */
  statusEventType: string;
  statusEventPhase: string;
  checkpointReady: boolean;
};

export type RunEventIndex = {
  /** Number of events currently indexed (matches the capped list length). */
  size: number;
  countsByType: Record<string, number>;
  /** Newest-first event lists per event type. */
  byType: Record<string, RunEvent[]>;
  /** Newest-first event lists per stage (node_id). */
  byStage: Record<string, RunEvent[]>;
  lifecycleByStage: Record<string, StageLifecycle>;
};

export function emptyRunEventIndex(): RunEventIndex {
  return { byStage: {}, byType: {}, countsByType: {}, lifecycleByStage: {}, size: 0 };
}

/** Builds the index from a newest-first event list (restore / initial load). */
export function buildRunEventIndex(events: RunEvent[]): RunEventIndex {
  const index = emptyRunEventIndex();
  for (let cursor = events.length - 1; cursor >= 0; cursor -= 1) {
    applyEvent(index, events[cursor]);
  }
  return index;
}

/** Returns a new index with `event` appended as the newest entry. */
export function appendRunEvent(index: RunEventIndex, event: RunEvent): RunEventIndex {
  const next: RunEventIndex = {
    byStage: { ...index.byStage },
    byType: { ...index.byType },
    countsByType: { ...index.countsByType },
    lifecycleByStage: { ...index.lifecycleByStage },
    size: index.size,
  };
  applyEvent(next, event);
  return next;
}

function applyEvent(index: RunEventIndex, event: RunEvent) {
  index.size += 1;
  index.countsByType[event.type] = (index.countsByType[event.type] ?? 0) + 1;
  index.byType[event.type] = [event, ...(index.byType[event.type] ?? [])];
  const stageId = event.node_id;
  if (!stageId) return;
  index.byStage[stageId] = [event, ...(index.byStage[stageId] ?? [])];
  const lifecycle: StageLifecycle = {
    ...(index.lifecycleByStage[stageId] ?? {
      checkpointReady: false,
      nodeEventPhase: '',
      nodeEventType: '',
      statusEventPhase: '',
      statusEventType: '',
    }),
  };
  if (event.type.startsWith('node_')) {
    lifecycle.nodeEventType = event.type;
    lifecycle.nodeEventPhase = String(event.phase ?? '');
  }
  if (isStageStatusEvent(event.type)) {
    lifecycle.statusEventType = event.type;
    lifecycle.statusEventPhase = String(event.phase ?? '');
  }
  if (event.type === 'stage_checkpoint_ready') lifecycle.checkpointReady = true;
  index.lifecycleByStage[stageId] = lifecycle;
}

function isStageStatusEvent(type: string) {
  return type.startsWith('node_')
    || type === 'run_error'
    || type === 'stage_artifact_confirmed'
    || type === 'artifact_approved';
}

/** Index-backed equivalent of `hasRunningNodeFromEvents` (runSelectors). */
export function indexedRunningNodeExists(index: RunEventIndex): boolean {
  if (
    (index.countsByType.run_completed ?? 0) > 0
    || (index.countsByType.node_failed ?? 0) > 0
    || (index.countsByType.run_recovery_required ?? 0) > 0
  ) return false;
  return Object.values(index.lifecycleByStage).some((lifecycle) => (
    lifecycle.nodeEventType === 'node_started' && lifecycle.nodeEventPhase !== 'finalizing'
  ));
}

/** Index-backed equivalent of `hasRecoverableRun` (runSelectors). */
export function indexedHasRecoverableRun(
  activeRunId: string,
  index: RunEventIndex,
  runControlState: RunControlState,
): boolean {
  if (!activeRunId) return false;
  if (runControlState === 'failed' || runControlState === 'completed') return false;
  if ((index.countsByType.run_completed ?? 0) > 0) return false;
  if ((index.countsByType.node_failed ?? 0) > 0 && runControlState !== 'paused') return false;
  return index.size > 0 || runControlState !== 'idle';
}

/** Index-backed equivalent of `latestNodeStatus(...).status` (cockpitRuntime). */
export function indexedStageStatus(index: RunEventIndex, stageId: string): StageRunStatus {
  const lifecycle = index.lifecycleByStage[stageId];
  if (!lifecycle || !lifecycle.statusEventType) return 'idle';
  const type = lifecycle.statusEventType;
  if (type === 'node_failed' || type === 'run_error') return 'failed';
  if (type === 'node_completed' || type === 'stage_artifact_confirmed' || type === 'artifact_approved') return 'done';
  if (type === 'node_started') return lifecycle.statusEventPhase === 'finalizing' ? 'done' : 'running';
  return 'idle';
}

export function indexedStageCheckpointReady(index: RunEventIndex, stageId: string): boolean {
  return Boolean(index.lifecycleByStage[stageId]?.checkpointReady);
}

/** Unique stage ids with a `node_completed` event, newest occurrence first. */
export function indexedCompletedStageIds(index: RunEventIndex): string[] {
  const completed = index.byType.node_completed ?? [];
  const ids: string[] = [];
  for (const event of completed) {
    if (event.node_id && !ids.includes(event.node_id)) ids.push(event.node_id);
  }
  return ids;
}
