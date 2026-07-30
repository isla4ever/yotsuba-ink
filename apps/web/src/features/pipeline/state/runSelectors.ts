import type { RunControlState, RunEvent, WorkflowStage } from '../contracts';

export function sortRunEventsNewestFirst(events: RunEvent[]) {
  return [...events].sort((left, right) => eventTime(right) - eventTime(left));
}

export function selectMemoryEvents(events: RunEvent[]) {
  return events
    .filter((event) => event.type === 'memory_context_loaded' || event.type === 'memory_writeback_completed')
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
    event.type === 'node_started'
    && event.node_id
    && !events.find((candidate) => (
      candidate.node_id === event.node_id
      && (candidate.type === 'node_completed' || candidate.type === 'node_failed')
    ))
  ))?.node_id;
  if (runningStage) return runningStage;

  const completedStage = events.find(
    (event) => event.type === 'node_completed' && event.node_id,
  )?.node_id ?? '';
  return selectNextStageId(stages, completedStage) || selectedStageId || 'info';
}

export function selectCheckpointStageId(
  requestedStageId: string,
  events: RunEvent[],
  stages: WorkflowStage[],
  selectedStageId: string,
) {
  if (requestedStageId && stageExists(stages, requestedStageId)) return requestedStageId;
  const latestConfirmed = events.find((event) => (
    event.type === 'stage_artifact_confirmed'
    && Boolean(event.node_id)
    && stageExists(stages, event.node_id ?? '')
  ));
  if (latestConfirmed?.node_id) return latestConfirmed.node_id;
  const latestCheckpoint = selectLatestCheckpointEvent(events, stages);
  if (latestCheckpoint?.node_id) return latestCheckpoint.node_id;
  if (selectedStageId && stageExists(stages, selectedStageId)) return selectedStageId;
  return 'info';
}

export function selectLatestStageArtifact(events: RunEvent[], stageId: string) {
  const selectedCandidate = events.find(
    (event) => event.type === 'draft_candidate_selected' && event.node_id === stageId,
  );
  if (selectedCandidate?.artifact) return selectedCandidate.artifact;
  return events.find(
    (event) => event.type === 'node_completed' && event.node_id === stageId,
  )?.result;
}

export function selectLatestCheckpointEvent(events: RunEvent[], stages: WorkflowStage[]) {
  return events.find((event) => (
    event.type === 'stage_checkpoint_ready'
    && Boolean(event.node_id)
    && stageExists(stages, event.node_id ?? '')
  ));
}

export function hasRecoverableRun(
  activeRunId: string,
  events: RunEvent[],
  runControlState: RunControlState,
) {
  if (!activeRunId) return false;
  if (runControlState === 'failed' || runControlState === 'completed') return false;
  if (events.some((event) => event.type === 'run_completed')) return false;
  if (events.some((event) => event.type === 'node_failed') && runControlState !== 'paused') return false;
  return events.length > 0 || runControlState !== 'idle';
}

export function hasRunningNodeFromEvents(events: RunEvent[]) {
  if (events.some((event) => event.type === 'run_completed' || event.type === 'node_failed' || event.type === 'run_recovery_required')) return false;
  const nodeIds = [...new Set(events.map((event) => event.node_id).filter(Boolean) as string[])];
  return nodeIds.some((nodeId) => {
    const latestNodeEvent = events.find(
      (event) => event.node_id === nodeId && event.type.startsWith('node_'),
    );
    return latestNodeEvent?.type === 'node_started' && latestNodeEvent.phase !== 'finalizing';
  });
}

/**
 * Facts-based mode-switch gate (Phase 12 F5): consumes pre-derived run facts
 * so shell chrome can call it without subscribing to the raw event stream.
 */
export function canSwitchModeFromFacts(params: {
  approvalPending: boolean;
  checkpointContinueReady: boolean;
  infoContinueReady: boolean;
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
    || params.infoContinueReady
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
  infoContinueReady: boolean;
  paused: boolean;
  runControlState: RunControlState;
  running: boolean;
}) {
  return canSwitchModeFromFacts({
    approvalPending: params.approvalPending,
    checkpointContinueReady: params.checkpointContinueReady,
    infoContinueReady: params.infoContinueReady,
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
  const createdAt = event.created_at ? Date.parse(event.created_at) : 0;
  return Number.isFinite(createdAt) ? createdAt : 0;
}
