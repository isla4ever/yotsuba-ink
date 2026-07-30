import type { RunEvent } from '../contracts';
import { formatResult } from '../lib/workflow';
import type { HydratedRunState } from './runState';

export type StageDecisionState = {
  approvalDraft: string;
  approvalPending: boolean;
  approvalSource: string;
  checkpointContinueReady: boolean;
  checkpointStageId: string;
  infoContinueReady: boolean;
};

export const initialStageDecisionState: StageDecisionState = {
  approvalDraft: '',
  approvalPending: false,
  approvalSource: '',
  checkpointContinueReady: false,
  checkpointStageId: '',
  infoContinueReady: false,
};

export function restoreStageDecisionState(
  hydrated: HydratedRunState,
): StageDecisionState {
  return {
    approvalDraft: hydrated.approvalDraft,
    approvalPending: hydrated.approvalPending,
    approvalSource: hydrated.approvalSource,
    checkpointContinueReady: hydrated.checkpointContinueReady,
    checkpointStageId: hydrated.checkpointStageId,
    infoContinueReady: hydrated.infoContinueReady,
  };
}

export function infoApprovedState(
  state: StageDecisionState,
): StageDecisionState {
  return {
    ...state,
    approvalPending: false,
    checkpointContinueReady: false,
    checkpointStageId: '',
    infoContinueReady: true,
  };
}

export function stageConfirmedState(
  state: StageDecisionState,
  stageId: string,
): StageDecisionState {
  return {
    ...state,
    approvalPending: false,
    checkpointContinueReady: true,
    checkpointStageId: stageId,
    infoContinueReady: false,
  };
}

export function continuationStartedState(
  state: StageDecisionState,
): StageDecisionState {
  return {
    ...state,
    checkpointContinueReady: false,
    checkpointStageId: '',
    infoContinueReady: false,
  };
}

export function exportReadyState(
  state: StageDecisionState,
): StageDecisionState {
  return {
    ...state,
    approvalPending: false,
    checkpointContinueReady: true,
    checkpointStageId: 'export',
    infoContinueReady: false,
  };
}

export function decisionStateForPausedStream(
  state: StageDecisionState,
  events: RunEvent[],
): StageDecisionState {
  const pauseEvent = events.find(
    (event) => event.type === 'approval_required' || event.type === 'run_paused',
  );
  if (!pauseEvent || pauseEvent.type === 'run_paused') return state;
  return {
    ...state,
    approvalPending: true,
    checkpointContinueReady: false,
    checkpointStageId: pauseEvent.node_id ?? '',
    infoContinueReady: false,
  };
}

export function stageDecisionStateForEvent(
  state: StageDecisionState,
  event: RunEvent,
): StageDecisionState {
  if (event.type === 'approval_required') {
    const approvalDraft = formatResult(event.artifact ?? event.result ?? '');
    return {
      ...state,
      approvalDraft,
      approvalPending: true,
      approvalSource: event.node_id === 'info' ? approvalDraft : state.approvalSource,
      checkpointContinueReady: false,
      checkpointStageId: event.node_id ?? 'info',
      infoContinueReady: false,
    };
  }
  if (event.type === 'artifact_approved') {
    const approvalDraft = formatResult(event.artifact ?? state.approvalDraft);
    return {
      ...infoApprovedState(state),
      approvalDraft,
      approvalSource: event.node_id === 'info' ? approvalDraft : state.approvalSource,
    };
  }
  if (event.type === 'stage_artifact_confirmed' && event.node_id) {
    return event.node_id === 'info'
      ? infoApprovedState(state)
      : stageConfirmedState(state, event.node_id);
  }
  if (event.type === 'brief_regenerated') {
    const approvalDraft = formatResult(event.artifact ?? '');
    return {
      ...state,
      approvalDraft,
      approvalPending: true,
      approvalSource: approvalDraft,
      checkpointContinueReady: false,
      checkpointStageId: event.node_id ?? 'info',
      infoContinueReady: false,
    };
  }
  if (event.type === 'draft_candidate_selected' && event.node_id === 'info') {
    const approvalDraft = formatResult(event.artifact ?? state.approvalDraft);
    return {
      ...state,
      approvalDraft,
      approvalPending: true,
      approvalSource: approvalDraft,
      checkpointContinueReady: false,
      checkpointStageId: 'info',
      infoContinueReady: false,
    };
  }
  return state;
}
