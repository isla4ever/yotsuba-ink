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
    (event) => event.type === 'decision.required',
  );
  if (!pauseEvent) return state;
  return {
    ...state,
    approvalPending: true,
    checkpointContinueReady: false,
      checkpointStageId: pauseEvent.stage_id ?? '',
    infoContinueReady: false,
  };
}

export function stageDecisionStateForEvent(
  state: StageDecisionState,
  event: RunEvent,
): StageDecisionState {
  if (event.type === 'decision.required') {
    const stageId = event.stage_id || event.node_id?.split('.')[0] || 'info';
    return {
      ...state,
      approvalPending: true,
      checkpointContinueReady: false,
      checkpointStageId: stageId,
      infoContinueReady: false,
    };
  }
  if (event.type === 'artifact.candidate_ready' && event.stage_id === 'info' && event.payload) {
    const approvalDraft = formatResult(event.payload);
    return { ...state, approvalDraft, approvalSource: approvalDraft };
  }
  if (event.type === 'artifact.committed' && event.stage_id) {
    return event.stage_id === 'info'
      ? infoApprovedState(state)
      : stageConfirmedState(state, event.stage_id);
  }
  return state;
}
