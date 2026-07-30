import type { RunControlState, RunEvent, WorkflowDefinition } from '../contracts';
import { hasRunningNodeFromEvents } from './runSelectors';

export { canSwitchMode, canSwitchModeFromFacts, hasRecoverableRun, hasRunningNodeFromEvents } from './runSelectors';

export type StoredRunSnapshot = {
  run_id?: string;
  /** Phase 11: owning project id from run.json; legacy runs carry project_id == run_id. */
  project_id?: string;
  events?: RunEvent[];
  approval?: {
    required?: boolean;
    node_id?: string;
    artifact?: unknown;
  };
  paused?: boolean;
  state?: {
    approval_required?: boolean;
    approved_artifacts?: Record<string, unknown>;
    artifacts?: Record<string, unknown>;
    completed_stage_ids?: string[];
    execution_mode?: string;
    current_checkpoint_stage_id?: string;
    current_stage_id?: string;
    runtime_phase?: string;
    pending_export_return?: boolean;
    recovery_state?: {
      status?: 'closed' | 'degraded' | 'open';
      needs_recovery?: boolean;
      last_stable_checkpoint?: Record<string, unknown>;
    };
    stage_display_artifacts?: Record<string, unknown>;
    stage_confirmation_state?: Record<string, { status?: string; node_id?: string }>;
  };
  workflow?: WorkflowDefinition;
};

export type HydratedRunState = ReturnType<typeof hydrateRunFromStoredState>;
export type RunRecoveryDiscardReason = 'completed' | 'empty' | 'failed' | 'invalid' | 'not_found';
export type RunRecoveryResolution =
  | { kind: 'discard'; reason: RunRecoveryDiscardReason }
  | { kind: 'restore'; hydrated: HydratedRunState; reconnect: boolean; source: 'server' | 'cache' };

export function resolveHistoricalRunOpen(
  snapshot: StoredRunSnapshot,
  fallbackRunId: string,
): RunRecoveryResolution {
  if (!snapshot || typeof snapshot !== 'object') return { kind: 'discard', reason: 'invalid' };
  if (snapshot.run_id && snapshot.run_id !== fallbackRunId) return { kind: 'discard', reason: 'invalid' };
  const hydrated = hydrateRunFromStoredState(snapshot, fallbackRunId);
  if (!hydrated.activeRunId || !hydrated.events.length) return { kind: 'discard', reason: 'empty' };
  const phase = snapshot.state?.runtime_phase ?? '';
  const completed = phase === 'completed'
    || hydrated.events.some((event) => event.type === 'run_completed');
  const checkpointOpen = Boolean(
    snapshot.state?.pending_export_return
    || snapshot.state?.approval_required
    || phase === 'awaiting_stage_confirmation'
    || phase === 'stage_ready_to_continue'
    || phase === 'checkpoint_recovery'
  );
  if (completed) return { kind: 'discard', reason: 'completed' };
  if (checkpointOpen) {
    return {
      kind: 'restore',
      hydrated: { ...hydrated, paused: true, runControlState: 'paused' },
      reconnect: false,
      source: 'server',
    };
  }
  if (hydrated.runControlState === 'failed') return { kind: 'discard', reason: 'failed' };
  return {
    kind: 'restore',
    hydrated: { ...hydrated, paused: true, runControlState: 'paused' },
    reconnect: false,
    source: 'server',
  };
}

export function hydrateRunFromStoredState(snapshot: StoredRunSnapshot, fallbackRunId: string) {
  const chronological = stageFactsFromSnapshot(
    Array.isArray(snapshot.events) ? snapshot.events : [],
    snapshot,
    fallbackRunId,
  );
  const events = [...chronological].reverse();
  return hydrateNewestFirstEvents(events, snapshot, fallbackRunId);
}

const snapshotArtifactKeys: Record<string, string> = {
  cover: 'cover',
  detail: 'detail_outline',
  export: 'export',
  info: 'info_recommend',
  outline: 'outline',
  summary: 'summary',
  text: 'chapters',
};

function stageFactsFromSnapshot(events: RunEvent[], snapshot: StoredRunSnapshot, fallbackRunId: string) {
  const completed = new Set(snapshot.state?.completed_stage_ids ?? []);
  const artifacts = [
    snapshot.state?.stage_display_artifacts,
    snapshot.state?.approved_artifacts,
    snapshot.state?.artifacts,
  ].find((candidate) => candidate && Object.keys(candidate).length) ?? {};
  if (!completed.size && !Object.keys(artifacts).length) return events;

  const runId = snapshot.run_id || fallbackRunId;
  const next = [...events];
  for (const [stageId, artifactKey] of Object.entries(snapshotArtifactKeys)) {
    const artifact = artifacts[artifactKey];
    const stageEvents = events.filter((event) => event.node_id === stageId);
    const hasCompleted = stageEvents.some((event) => event.type === 'node_completed');
    // Persisted state is the backend's latest stable fact. Always append it after
    // the historical event stream so stale validation failures cannot hide a
    // successfully stored artifact during recovery.
    if (artifact != null) {
      next.push({ artifact, node_id: stageId, run_id: runId, type: 'artifact_validated' });
    }
    if (completed.has(stageId) && !hasCompleted) {
      next.push({ artifact, node_id: stageId, run_id: runId, type: 'node_completed' });
    }
  }
  return next;
}

export function hydrateLocalRunControl(params: {
  activeRunId: string;
  events: RunEvent[];
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
}) {
  const events = [...params.events].sort((left, right) => eventTime(right) - eventTime(left));
  const checkpointStageId = latestCheckpointStage(events);
  const confirmationStatus = confirmationStatusFromEvents(events, checkpointStageId);
  const runtimePhase = confirmationStatus === 'confirmed'
    ? 'stage_ready_to_continue'
    : confirmationStatus === 'pending'
      ? 'awaiting_stage_confirmation'
      : '';
  return hydrateNewestFirstEvents(events, {
    run_id: params.activeRunId,
    paused: params.paused,
    approval: confirmationStatus === 'pending' && checkpointStageId
      ? {
          required: true,
          node_id: checkpointStageId,
          artifact: latestApprovalArtifact(events, checkpointStageId),
        }
      : undefined,
    state: {
      current_checkpoint_stage_id: checkpointStageId,
      current_stage_id: latestStageId(events),
      runtime_phase: runtimePhase,
      stage_confirmation_state: checkpointStageId && confirmationStatus
        ? { [checkpointStageId]: { status: confirmationStatus, node_id: checkpointStageId } }
        : {},
    },
  }, params.activeRunId, params.selectedId);
}

function hydrateNewestFirstEvents(events: RunEvent[], snapshot: StoredRunSnapshot, fallbackRunId: string, fallbackSelectedId = 'info') {
  const state = snapshot.state;
  const runtimePhase = state?.runtime_phase ?? '';
  const latestStageEvent = events.find((event) => event.node_id);
  const checkpointStage = checkpointStageFrom(snapshot, events);
  const storedConfirmation = state?.stage_confirmation_state?.[checkpointStage]?.status;
  const confirmationStatus = storedConfirmation || confirmationStatusFromEvents(events, checkpointStage);
  const approvalPending = snapshot.approval?.required
    ?? state?.approval_required
    ?? confirmationStatus === 'pending';
  const checkpointPhase = runtimePhase === 'awaiting_stage_confirmation'
    || runtimePhase === 'stage_ready_to_continue';
  const checkpointActive = Boolean(
    checkpointStage
    && (
      approvalPending
      || state?.pending_export_return
      || checkpointPhase
      || (!runtimePhase && (confirmationStatus === 'pending' || confirmationStatus === 'confirmed'))
    )
  );
  const checkpointConfirmed = confirmationStatus === 'confirmed'
    || (checkpointStage === 'export' && Boolean(state?.pending_export_return));
  const stageReady = Boolean(
    checkpointActive
    && (checkpointConfirmed || runtimePhase === 'stage_ready_to_continue' || state?.pending_export_return)
  );
  const hasRunCompleted = runtimePhase === 'completed'
    || events.some((event) => event.type === 'run_completed');
  const historicalRecoveryRequired = events.some(
    (event) => event.type === 'run_recovery_required' || event.recovery_state?.needs_recovery,
  );
  const recoveryRequired = Boolean(
    state?.recovery_state?.needs_recovery
    || runtimePhase === 'recovery_required'
    || (!runtimePhase && historicalRecoveryRequired),
  );
  const historicalFailure = events.some(
    (event) => event.type === 'node_failed' || event.type === 'run_failed' || event.type === 'run_error',
  );
  const hasFailed = !recoveryRequired
    && (runtimePhase ? runtimePhase === 'failed' : historicalFailure);
  const hasRunning = ['cockpit_streaming', 'info_generating', 'stage_streaming'].includes(runtimePhase)
    || hasRunningNodeFromEvents(events);
  const selectedId = approvalPending && snapshot.approval?.node_id
    ? snapshot.approval.node_id
    : checkpointActive
      ? checkpointStage
      : state?.current_stage_id || latestStageEvent?.node_id || fallbackSelectedId || 'info';
  const infoContinueReady = stageReady && checkpointStage === 'info' && !approvalPending;
  const checkpointContinueReady = stageReady
    && checkpointStage !== 'info'
    && !hasRunCompleted
    && checkpointConfirmed;
  const paused = Boolean(
    snapshot.paused
    || approvalPending
    || checkpointActive
    || runtimePhase === 'awaiting_stage_confirmation'
    || runtimePhase === 'stage_ready_to_continue'
    || runtimePhase === 'checkpoint_recovery'
    || runtimePhase === 'recovery_required'
    || recoveryRequired
  );
  const runControlState: RunControlState = hasFailed
    ? 'failed'
    : hasRunCompleted
      ? 'completed'
      : paused
        ? 'paused'
        : hasRunning
          ? 'running'
          : 'paused';
  const approvalDraft = snapshot.approval?.artifact ? formatArtifact(snapshot.approval.artifact) : '';
  return {
    activeRunId: snapshot.run_id || fallbackRunId,
    approvalDraft,
    approvalPending: Boolean(approvalPending),
    approvalSource: approvalDraft,
    automationCockpitReady: events.some((event) => event.node_id && event.node_id !== 'info'),
    checkpointContinueReady,
    checkpointStageId: checkpointActive ? checkpointStage : '',
    events,
    infoContinueReady,
    paused,
    runControlState,
    selectedId,
  };
}

export function resolveServerRunRecovery(
  snapshot: StoredRunSnapshot,
  fallbackRunId: string,
): RunRecoveryResolution {
  if (!snapshot || typeof snapshot !== 'object') return { kind: 'discard', reason: 'invalid' };
  if (snapshot.run_id && snapshot.run_id !== fallbackRunId) return { kind: 'discard', reason: 'invalid' };
  const hydrated = hydrateRunFromStoredState(snapshot, fallbackRunId);
  if (!hydrated.activeRunId || !hydrated.events.length) return { kind: 'discard', reason: 'empty' };
  if (hydrated.runControlState === 'completed') return { kind: 'discard', reason: 'completed' };
  if (hydrated.runControlState === 'failed') return { kind: 'discard', reason: 'failed' };
  return {
    kind: 'restore',
    hydrated,
    reconnect: hydrated.runControlState === 'running' && !hydrated.paused,
    source: 'server',
  };
}

export function resolveCachedRunRecovery(params: {
  activeRunId: string;
  events: RunEvent[];
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
}): RunRecoveryResolution {
  const hydrated = hydrateLocalRunControl(params);
  if (!hydrated.activeRunId || !hydrated.events.length) return { kind: 'discard', reason: 'empty' };
  if (hydrated.runControlState === 'completed') return { kind: 'discard', reason: 'completed' };
  if (hydrated.runControlState === 'failed') return { kind: 'discard', reason: 'failed' };
  return {
    kind: 'restore',
    hydrated: { ...hydrated, paused: true, runControlState: 'paused' },
    reconnect: false,
    source: 'cache',
  };
}

function eventTime(event: RunEvent) {
  const createdAt = event.created_at ? Date.parse(event.created_at) : 0;
  return Number.isFinite(createdAt) ? createdAt : 0;
}

function latestCheckpointStage(events: RunEvent[]) {
  return events.find((event) => event.type === 'stage_checkpoint_ready')?.node_id ?? '';
}

function latestStageId(events: RunEvent[]) {
  return events.find((event) => event.node_id)?.node_id ?? 'info';
}

function formatArtifact(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value ?? '', null, 2);
}

function checkpointStageFrom(snapshot: StoredRunSnapshot, events: RunEvent[]) {
  const state = snapshot.state;
  if (state?.current_checkpoint_stage_id) return state.current_checkpoint_stage_id;
  const pending = Object.entries(state?.stage_confirmation_state ?? {}).find(([, value]) => value?.status === 'pending');
  if (pending?.[0]) return pending[0];
  return latestCheckpointStage(events) || state?.current_stage_id || '';
}

function confirmationStatusFromEvents(events: RunEvent[], stageId: string) {
  if (!stageId) return '';
  const event = events.find((item) => (
    item.node_id === stageId
    && (
      item.type === 'stage_artifact_confirmed'
      || item.type === 'artifact_approved'
      || item.type === 'approval_required'
      || item.type === 'stage_checkpoint_ready'
    )
  ));
  if (!event) return '';
  return event.type === 'stage_artifact_confirmed' || event.type === 'artifact_approved'
    ? 'confirmed'
    : 'pending';
}

function latestApprovalArtifact(events: RunEvent[], stageId: string) {
  return events.find((event) => (
    event.node_id === stageId
    && (event.type === 'approval_required' || event.type === 'stage_checkpoint_ready')
  ))?.artifact;
}
