import type { RunControlState, RunEvent, WorkflowStage } from '../contracts';

export function sortRunEventsNewestFirst(events: RunEvent[]) {
  return [...events].sort((left, right) => eventTime(right) - eventTime(left));
}

export function selectMemoryEvents(events: RunEvent[]) {
  return events
    .filter((event) => event.type === 'evidence.proposed' || event.type.startsWith('writeback.'))
    .slice(0, 40);
}

export function selectStage(stages: WorkflowStage[], stageId: string) {
  return stages.find((stage) => stage.id === stageId) ?? stages[0];
}

export function stageExists(stages: WorkflowStage[], stageId: string) {
  return stages.some((stage) => stage.id === stageId);
}

export function selectNextStageId(stages: WorkflowStage[], stageId: string) {
  const index = stages.findIndex((stage) => stage.id === stageId);
  return index < 0 ? '' : stages[index + 1]?.id ?? '';
}

export function selectStageToResume(
  events: RunEvent[],
  stages: WorkflowStage[],
  selectedStageId: string,
) {
  const runningStage = events.find((event) => (
    event.type === 'node.started'
    && stageIdForEvent(event)
    && !events.find((candidate) => (
      candidate.node_id === event.node_id
      && (candidate.type === 'node.completed' || candidate.type === 'node.failed')
    ))
  ));
  const runningStageId = runningStage ? stageIdForEvent(runningStage) : '';
  if (runningStageId) return runningStageId;

  const completedStage = events.find(
    (event) => event.type === 'artifact.committed' && event.stage_id !== 'text',
  );
  const completedStageId = completedStage ? stageIdForEvent(completedStage) : '';
  return selectNextStageId(stages, completedStageId) || selectedStageId || 'brief';
}

export function selectCheckpointStageId(
  requestedStageId: string,
  events: RunEvent[],
  stages: WorkflowStage[],
  selectedStageId: string,
) {
  if (requestedStageId && stageExists(stages, requestedStageId)) return requestedStageId;
  const latestConfirmed = events.find((event) => (
    event.type === 'artifact.committed'
    && Boolean(stageIdForEvent(event))
    && stageExists(stages, stageIdForEvent(event))
  ));
  if (latestConfirmed) return stageIdForEvent(latestConfirmed);
  const latestCheckpoint = selectLatestCheckpointEvent(events, stages);
  if (latestCheckpoint) return stageIdForEvent(latestCheckpoint);
  if (selectedStageId && stageExists(stages, selectedStageId)) return selectedStageId;
  return 'brief';
}

export function selectLatestStageArtifact(events: RunEvent[], stageId: string) {
  return events.find((event) => (
    ['artifact.candidate_ready', 'artifact.committed'].includes(event.type)
    && stageIdForEvent(event) === stageId
    && event.payload != null
  ))?.payload;
}

export function selectLatestCheckpointEvent(events: RunEvent[], stages: WorkflowStage[]) {
  return events.find((event) => (
    (event.type === 'checkpoint.saved' || stageCompletedBy(event))
    && Boolean(stageIdForEvent(event))
    && stageExists(stages, stageIdForEvent(event))
  ));
}

export function hasRecoverableRun(
  activeRunId: string,
  events: RunEvent[],
  runControlState: RunControlState,
) {
  if (!activeRunId) return false;
  if (runControlState === 'failed' || runControlState === 'completed') return false;
  if (events.some((event) => event.type === 'run.completed' || event.type === 'run.failed')) return false;
  return events.length > 0 || runControlState !== 'idle';
}

export function hasRunningNodeFromEvents(events: RunEvent[]) {
  if (events.some((event) => event.type === 'run.completed' || event.type === 'run.failed')) return false;
  const nodeIds = [...new Set(events.map((event) => event.node_id).filter(Boolean) as string[])];
  return nodeIds.some((nodeId) => {
    const latestNodeEvent = events.find(
      (event) => event.node_id === nodeId && event.type.startsWith('node.'),
    );
    return latestNodeEvent?.type === 'node.started';
  });
}

/**
 * Facts-based mode-switch gate (Phase 12 F5): consumes pre-derived run facts
 * so shell chrome can call it without subscribing to the raw event stream.
 */
export function canSwitchModeFromFacts(params: {
  approvalPending: boolean;
  checkpointContinueReady: boolean;
  briefContinueReady: boolean;
  paused: boolean;
  /** hasRecoverableRun over the active run (the shell's `runHasStarted`). */
  recoverable: boolean;
  runControlState: RunControlState;
  /** Combined running flag (control state OR live run events). */
  running: boolean;
}) {
  if (
    params.running
    || params.paused
    || params.approvalPending
    || params.briefContinueReady
    || params.checkpointContinueReady
  ) return false;
  if (['starting', 'running', 'stop_requested', 'paused'].includes(params.runControlState)) return false;
  return !params.recoverable || ['completed', 'failed', 'idle'].includes(params.runControlState);
}

export function canSwitchMode(params: {
  activeRunId: string;
  approvalPending: boolean;
  checkpointContinueReady: boolean;
  events: RunEvent[];
  briefContinueReady: boolean;
  paused: boolean;
  runControlState: RunControlState;
  running: boolean;
}) {
  return canSwitchModeFromFacts({
    approvalPending: params.approvalPending,
    checkpointContinueReady: params.checkpointContinueReady,
    briefContinueReady: params.briefContinueReady,
    paused: params.paused,
    recoverable: hasRecoverableRun(params.activeRunId, params.events, params.runControlState),
    runControlState: params.runControlState,
    running: params.running || hasRunningNodeFromEvents(params.events),
  });
}

export function parseApprovalArtifact(value: string) {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function eventTime(event: RunEvent) {
  const createdAt = Date.parse(event.occurred_at);
  return Number.isFinite(createdAt) ? createdAt : 0;
}

function stageIdForEvent(event: RunEvent) {
  return event.stage_id || event.node_id?.split('.')[0] || '';
}

function stageCompletedBy(event: RunEvent) {
  if (event.type === 'artifact.committed' && event.stage_id !== 'text') return true;
  return event.type === 'node.completed' && (
    event.node_id?.endsWith('.checkpoint_stage') || event.node_id === 'text.finish_chapters'
  );
}
