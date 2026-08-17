import type {
  GraphRunEnvelope,
  GraphRunReadModel,
  RunArtifactRecord,
  RunControlState,
  RunEvent,
  RunInputs,
} from '../contracts';
import type { ChapterVersionRecord } from '../services/runApi';
import { isRunInputs } from './runInputSnapshot';

export { canSwitchMode, canSwitchModeFromFacts, hasRecoverableRun, hasRunningNodeFromEvents } from './runSelectors';

export type HydratedRunState = {
  activeRunId: string;
  inputs?: RunInputs;
  approvalPending: boolean;
  checkpointContinueReady: boolean;
  checkpointStageId: string;
  events: RunEvent[];
  briefContinueReady: boolean;
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
  /** Stage artifact events persisted past the capped event window (long runs). */
  stickyStageEvents?: RunEvent[];
};

export type RunRecoveryDiscardReason = 'completed' | 'failed' | 'invalid' | 'not_found';
export type RunRecoveryResolution =
  | { kind: 'discard'; reason: RunRecoveryDiscardReason }
  | { kind: 'restore'; hydrated: HydratedRunState; reconnect: boolean; source: 'server' };

export function resolveServerRunRecovery(
  envelope: GraphRunEnvelope,
  fallbackRunId: string,
  committedArtifacts: RunArtifactRecord[] = [],
): RunRecoveryResolution {
  if (!isGraphRunEnvelope(envelope, fallbackRunId)) {
    return { kind: 'discard', reason: 'invalid' };
  }
  if (envelope.read_model.status === 'completed') {
    return { kind: 'discard', reason: 'completed' };
  }
  if (envelope.read_model.status === 'failed' || envelope.read_model.status === 'cancelled') {
    return { kind: 'discard', reason: 'failed' };
  }
  return {
    kind: 'restore',
    hydrated: hydrateGraphRun(envelope, committedArtifacts),
    reconnect: true,
    source: 'server',
  };
}

/**
 * Presentation restore: unlike boot-time recovery (which discards terminal
 * runs so a reload never re-enters an old session), explicitly opening a book
 * or a history run must present terminal runs too — the SSE replay closes
 * itself after the terminal event, leaving a read-only completed/failed view.
 */
export function resolveServerRunPresentation(
  envelope: GraphRunEnvelope,
  fallbackRunId: string,
  committedArtifacts: RunArtifactRecord[] = [],
  acceptedChapters: ChapterVersionRecord[] = [],
): RunRecoveryResolution {
  if (!isGraphRunEnvelope(envelope, fallbackRunId)) {
    return { kind: 'discard', reason: 'invalid' };
  }
  return {
    kind: 'restore',
    hydrated: hydrateGraphRun(envelope, committedArtifacts, acceptedChapters),
    reconnect: !isTerminalRun(envelope.read_model.status),
    source: 'server',
  };
}

export function hydrateGraphRun(
  envelope: GraphRunEnvelope,
  committedArtifacts: RunArtifactRecord[] = [],
  acceptedChapters: ChapterVersionRecord[] = [],
): HydratedRunState {
  const projection = envelope.read_model;
  const pending = projection.pending_decisions[0];
  const pendingStage = stageIdFromDecision(pending);
  const awaitingDecision = projection.status === 'awaiting_decision';
  return {
    activeRunId: projection.run_id,
    inputs: isRunInputs(envelope.definition.inputs) ? envelope.definition.inputs : undefined,
    approvalPending: awaitingDecision && Boolean(pending),
    checkpointContinueReady: false,
    checkpointStageId: awaitingDecision ? pendingStage || projection.active_stage_id : '',
    events: committedArtifactSnapshotEvents(envelope, committedArtifacts, acceptedChapters),
    briefContinueReady: false,
    paused: awaitingDecision,
    runControlState: controlStateFromProjection(projection),
    selectedId: pendingStage || projection.active_stage_id,
  };
}

export function committedArtifactSnapshotEvents(
  envelope: GraphRunEnvelope,
  records: RunArtifactRecord[],
  acceptedChapters: ChapterVersionRecord[] = [],
): RunEvent[] {
  const runId = envelope.read_model.run_id;
  const threadId = envelope.read_model.thread_id;
  const occurredAt = envelope.read_model.updated_at;
  const artifactEvents = [...records]
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
    .map((record) => ({
      event_id: `${runId}:snapshot:${record.artifact_id}`,
      sequence: 0,
      occurred_at: record.created_at,
      run_id: runId,
      thread_id: threadId,
      type: 'artifact.committed',
      stage_id: record.stage_id,
      node_id: `${record.stage_id}.restore_committed_artifact`,
      chapter_id: '',
      status: 'completed',
      payload: record.payload,
      payload_ref: record.artifact_id,
      checkpoint_id: envelope.read_model.checkpoint_id,
    }));
  const chapterEvents = [...acceptedChapters]
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
    .map((record) => ({
      event_id: `${runId}:snapshot:${record.chapter_id}:${record.version_id}`,
      sequence: 0,
      occurred_at: record.created_at,
      run_id: runId,
      thread_id: threadId,
      type: 'artifact.committed',
      stage_id: 'text' as const,
      node_id: 'text.finish_chapters',
      chapter_id: record.chapter_id,
      status: 'completed',
      payload: record.artifact,
      payload_ref: record.version_id,
      checkpoint_id: envelope.read_model.checkpoint_id,
    }));
  const stageStatus = envelope.read_model.stage_status ?? {};
  const lifecycleEvents: RunEvent[] = Object.entries(stageStatus)
    .filter(([, status]) => status === 'completed')
    .map(([stageId]) => ({
      event_id: `${runId}:snapshot:${stageId}:completed`,
      sequence: 0,
      occurred_at: occurredAt,
      run_id: runId,
      thread_id: threadId,
      type: 'node.completed',
      stage_id: stageId as RunEvent['stage_id'],
      node_id: stageId === 'text' ? 'text.finish_chapters' : `${stageId}.checkpoint_stage`,
      chapter_id: '',
      status: 'completed',
      payload: null,
      payload_ref: '',
      checkpoint_id: envelope.read_model.checkpoint_id,
    }));
  const completionEvent: RunEvent = {
    event_id: `${runId}:snapshot:run-state`,
    sequence: 0,
    occurred_at: occurredAt,
    run_id: runId,
    thread_id: threadId,
    type: envelope.read_model.status === 'completed' ? 'run.completed' : 'run.failed',
    stage_id: null,
    node_id: '',
    chapter_id: '',
    status: envelope.read_model.status,
    payload: { provider_usage: envelope.read_model.provider_usage },
    payload_ref: '',
    checkpoint_id: envelope.read_model.checkpoint_id,
  };
  const metadataOnlyCover = stageStatus.cover === 'completed'
    && envelope.definition.export_preferences.include_cover_image === false;
  if (metadataOnlyCover) {
    lifecycleEvents.push({
      event_id: `${runId}:snapshot:cover:metadata-only`,
      sequence: 0,
      occurred_at: occurredAt,
      run_id: runId,
      thread_id: threadId,
      type: 'cover.asset_skipped',
      stage_id: 'cover',
      node_id: 'cover.metadata_only',
      chapter_id: '',
      status: 'completed',
      payload: { metadata_only: true },
      payload_ref: '',
      checkpoint_id: envelope.read_model.checkpoint_id,
    });
  }
  const terminalEvents = isTerminalRun(envelope.read_model.status) ? [completionEvent] : [];
  return [...terminalEvents, ...lifecycleEvents, ...chapterEvents, ...artifactEvents];
}

export function hydrateLocalRunControl(params: {
  activeRunId: string;
  events: RunEvent[];
  inputs?: RunInputs;
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
  stickyStageEvents?: RunEvent[];
}): HydratedRunState {
  const events = [...params.events].sort(compareNewestFirst);
  const latestDecision = events.find((event) => (
    event.type === 'decision.required' || event.type === 'decision.resolved'
  ));
  const pending = latestDecision?.type === 'decision.required' ? latestDecision : undefined;
  const stageId = pending?.stage_id || pending?.node_id?.split('.')[0] || '';
  return {
    activeRunId: params.activeRunId,
    inputs: isRunInputs(params.inputs) ? params.inputs : undefined,
    approvalPending: Boolean(pending),
    checkpointContinueReady: false,
    checkpointStageId: stageId,
    events,
    briefContinueReady: false,
    paused: params.paused,
    runControlState: params.runControlState,
    selectedId: stageId || params.selectedId || 'brief',
    stickyStageEvents: params.stickyStageEvents,
  };
}

function isGraphRunEnvelope(value: unknown, expectedRunId: string): value is GraphRunEnvelope {
  if (!value || typeof value !== 'object') return false;
  const envelope = value as Partial<GraphRunEnvelope>;
  return Boolean(
    envelope.definition
    && envelope.read_model
    && envelope.definition.architecture_version === 'phase27-vnext'
    && envelope.definition.run_id === expectedRunId
    && envelope.read_model.run_id === expectedRunId
    && envelope.read_model.thread_id === expectedRunId,
  );
}

function stageIdFromDecision(decision?: Record<string, unknown>) {
  if (!decision) return '';
  const nodeId = typeof decision.node_id === 'string' ? decision.node_id : '';
  return nodeId.split('.')[0] || '';
}

function controlStateFromProjection(projection: GraphRunReadModel): RunControlState {
  if (projection.status === 'completed') return 'completed';
  if (projection.status === 'failed' || projection.status === 'cancelled') return 'failed';
  if (projection.status === 'awaiting_decision') return 'paused';
  return projection.status === 'created' ? 'starting' : 'running';
}

function isTerminalRun(status: GraphRunEnvelope['read_model']['status']) {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

function compareNewestFirst(left: RunEvent, right: RunEvent) {
  const sequence = Number(right.sequence || 0) - Number(left.sequence || 0);
  if (sequence) return sequence;
  return eventTime(right) - eventTime(left);
}

function eventTime(event: RunEvent) {
  const timestamp = Date.parse(event.occurred_at);
  return Number.isFinite(timestamp) ? timestamp : 0;
}
