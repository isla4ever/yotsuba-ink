import type { RunControlState, RunEvent } from '../contracts';

/**
 * Phase 12 F6: incremental per-type / per-stage index over the newest-first
 * Graph event list. The reducer appends to it on every `event_received`, so hot
 * selectors (run-active detection, recoverability, per-stage runtime status)
 * read O(1)/O(#stages) instead of re-scanning up to 500 events per render.
 */

export const RUN_EVENT_LIMIT = 500;

/**
 * Trims a newest-first event list to the capped window while pinning each
 * stage's newest closing event (committed Artifact / stage-end node) past the
 * cap. Long runs emit more than the window holds; without the pins, every
 * events-derived projection (pipeline rail, artifact deck, canvas badges)
 * regresses completed early stages to "待开始". Bounded: window + one pin per
 * closed stage.
 */
export function trimRunEventWindow(newestFirst: RunEvent[]): RunEvent[] {
  if (newestFirst.length <= RUN_EVENT_LIMIT) return newestFirst;
  const window = newestFirst.slice(0, RUN_EVENT_LIMIT);
  const represented = new Set<string>();
  for (const event of window) {
    if (stageCompletedBy(event)) represented.add(eventStageId(event));
  }
  const pinned: RunEvent[] = [];
  for (let cursor = RUN_EVENT_LIMIT; cursor < newestFirst.length; cursor += 1) {
    const event = newestFirst[cursor];
    if (!stageCompletedBy(event)) continue;
    const stageId = eventStageId(event);
    if (!stageId || represented.has(stageId)) continue;
    represented.add(stageId);
    pinned.push(event);
  }
  return pinned.length ? [...window, ...pinned] : window;
}

function eventStageId(event: RunEvent): string {
  return event.stage_id || event.node_id?.split('.')[0] || '';
}

export type StageRunStatus = 'idle' | 'running' | 'awaiting' | 'done' | 'attention' | 'failed';

type StageLifecycle = {
  /** Latest stable node event type for the stage (run-active semantics). */
  nodeEventType: string;
  /** Latest event that changes the stage delivery lifecycle. */
  statusEventType: string;
  /** Whether that status event closes the stage; later diagnostics do not erase it. */
  stageCompleted: boolean;
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
  const stageId = event.stage_id || event.node_id?.split('.')[0];
  if (!stageId) return;
  index.byStage[stageId] = [event, ...(index.byStage[stageId] ?? [])];
  const lifecycle: StageLifecycle = {
    ...(index.lifecycleByStage[stageId] ?? {
      checkpointReady: false,
      nodeEventType: '',
      stageCompleted: false,
      statusEventType: '',
    }),
  };
  if (event.type.startsWith('node.')) {
    lifecycle.nodeEventType = event.type;
  }
  if (isStageStatusEvent(event.type)) {
    lifecycle.statusEventType = event.type;
    lifecycle.stageCompleted = stageCompletedBy(event);
  }
  if (event.type === 'checkpoint.saved' || stageCompletedBy(event)) lifecycle.checkpointReady = true;
  index.lifecycleByStage[stageId] = lifecycle;
}

function isStageStatusEvent(type: string) {
  return type.startsWith('node.')
    || type === 'artifact.candidate_ready'
    || type === 'artifact.committed'
    || type === 'decision.required'
    || type === 'decision.resolved'
    || type === 'run.failed';
}

/** Index-backed equivalent of `hasRunningNodeFromEvents` (runSelectors). */
export function indexedRunningNodeExists(index: RunEventIndex): boolean {
  if (
    (index.countsByType['run.completed'] ?? 0) > 0
    || (index.countsByType['run.failed'] ?? 0) > 0
  ) return false;
  return Object.values(index.lifecycleByStage).some((lifecycle) => (
    lifecycle.nodeEventType === 'node.started'
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
  if ((index.countsByType['run.completed'] ?? 0) > 0) return false;
  if ((index.countsByType['run.failed'] ?? 0) > 0) return false;
  return index.size > 0 || runControlState !== 'idle';
}

/** Projects the current runtime status for one stage from stable domain events. */
export function indexedStageStatus(index: RunEventIndex, stageId: string): StageRunStatus {
  const lifecycle = index.lifecycleByStage[stageId];
  if (!lifecycle || !lifecycle.statusEventType) return 'idle';
  const type = lifecycle.statusEventType;
  if (type === 'node.failed' || type === 'run.failed') return 'failed';
  if (lifecycle.stageCompleted) return 'done';
  if (type === 'decision.required') return 'awaiting';
  if (type === 'node.started' || type === 'node.completed' || type === 'artifact.candidate_ready' || type === 'decision.resolved') return 'running';
  return 'idle';
}

export function indexedStageCheckpointReady(index: RunEventIndex, stageId: string): boolean {
  return Boolean(index.lifecycleByStage[stageId]?.checkpointReady);
}

/** Unique stage ids with a committed Artifact or an explicit stage-end node. */
export function indexedCompletedStageIds(index: RunEventIndex): string[] {
  const ids: string[] = [];
  const completed = [
    ...(index.byType['artifact.committed'] ?? []),
    ...(index.byType['node.completed'] ?? []).filter(stageCompletedBy),
  ];
  for (const event of completed) {
    const stageId = event.stage_id || event.node_id?.split('.')[0];
    if (stageId && !ids.includes(stageId)) ids.push(stageId);
  }
  return ids;
}

function stageCompletedBy(event: RunEvent) {
  if (event.type === 'artifact.committed' && event.stage_id !== 'text') return true;
  if (event.type !== 'node.completed') return false;
  return event.node_id?.endsWith('.checkpoint_stage') || event.node_id === 'text.finish_chapters';
}
