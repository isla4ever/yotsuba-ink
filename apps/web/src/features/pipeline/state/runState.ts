import type {
  GraphRunEnvelope,
  GraphRunReadModel,
  RunControlState,
  RunEvent,
  RunInputs,
} from '../contracts';
import { isRunInputs } from './runInputSnapshot';

export { canSwitchMode, canSwitchModeFromFacts, hasRecoverableRun, hasRunningNodeFromEvents } from './runSelectors';

export type HydratedRunState = {
  activeRunId: string;
  inputs?: RunInputs;
  approvalDraft: string;
  approvalPending: boolean;
  approvalSource: string;
  automationCockpitReady: boolean;
  checkpointContinueReady: boolean;
  checkpointStageId: string;
  events: RunEvent[];
  infoContinueReady: boolean;
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
};

export type RunRecoveryDiscardReason = 'completed' | 'failed' | 'invalid' | 'not_found';
export type RunRecoveryResolution =
  | { kind: 'discard'; reason: RunRecoveryDiscardReason }
  | { kind: 'restore'; hydrated: HydratedRunState; reconnect: true; source: 'server' };

export function resolveServerRunRecovery(
  envelope: GraphRunEnvelope,
  fallbackRunId: string,
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
    hydrated: hydrateGraphRun(envelope),
    reconnect: true,
    source: 'server',
  };
}

export function hydrateGraphRun(envelope: GraphRunEnvelope): HydratedRunState {
  const projection = envelope.read_model;
  const pending = projection.pending_decisions[0];
  const pendingStage = stageIdFromDecision(pending);
  const awaitingDecision = projection.status === 'awaiting_decision';
  return {
    activeRunId: projection.run_id,
    inputs: isRunInputs(envelope.definition.inputs) ? envelope.definition.inputs : undefined,
    approvalDraft: '',
    approvalPending: awaitingDecision && Boolean(pending),
    approvalSource: '',
    automationCockpitReady: projection.active_stage_id !== 'info'
      || Object.values(projection.stage_status).some((status) => status === 'completed'),
    checkpointContinueReady: false,
    checkpointStageId: awaitingDecision ? pendingStage || projection.active_stage_id : '',
    events: [],
    infoContinueReady: false,
    paused: awaitingDecision,
    runControlState: controlStateFromProjection(projection),
    selectedId: pendingStage || projection.active_stage_id,
  };
}

export function hydrateLocalRunControl(params: {
  activeRunId: string;
  events: RunEvent[];
  inputs?: RunInputs;
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
}): HydratedRunState {
  const events = [...params.events].sort(compareNewestFirst);
  const latestDecision = events.find((event) => (
    event.type === 'decision.required' || event.type === 'decision.resolved'
  ));
  const pending = latestDecision?.type === 'decision.required' ? latestDecision : undefined;
  const stageId = pending?.stage_id || pending?.node_id?.split('.')[0] || '';
  const candidate = stageId
    ? events.find((event) => event.type === 'artifact.candidate_ready' && event.stage_id === stageId)
    : undefined;
  const draft = candidate?.payload ? formatArtifact(candidate.payload) : '';
  return {
    activeRunId: params.activeRunId,
    inputs: isRunInputs(params.inputs) ? params.inputs : undefined,
    approvalDraft: draft,
    approvalPending: Boolean(pending),
    approvalSource: draft,
    automationCockpitReady: events.some((event) => event.stage_id && event.stage_id !== 'info'),
    checkpointContinueReady: false,
    checkpointStageId: stageId,
    events,
    infoContinueReady: false,
    paused: params.paused,
    runControlState: params.runControlState,
    selectedId: stageId || params.selectedId || 'info',
  };
}

function isGraphRunEnvelope(value: unknown, expectedRunId: string): value is GraphRunEnvelope {
  if (!value || typeof value !== 'object') return false;
  const envelope = value as Partial<GraphRunEnvelope>;
  return Boolean(
    envelope.definition
    && envelope.read_model
    && envelope.definition.architecture_version === 'phase26-vnext'
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

function compareNewestFirst(left: RunEvent, right: RunEvent) {
  const sequence = Number(right.sequence || 0) - Number(left.sequence || 0);
  if (sequence) return sequence;
  return eventTime(right) - eventTime(left);
}

function eventTime(event: RunEvent) {
  const timestamp = Date.parse(event.occurred_at);
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function formatArtifact(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value ?? '', null, 2);
}
