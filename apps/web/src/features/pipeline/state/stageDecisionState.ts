import type { RunEvent } from '../contracts';
import { formatResult } from '../lib/workflow';
import type { HydratedRunState } from './runState';

export type StageDecisionState = {
  approvalDraft: string;
  approvalPending: boolean;
  approvalSource: string;
  checkpointContinueReady: boolean;
  checkpointStageId: string;
  briefContinueReady: boolean;
};

export const initialStageDecisionState: StageDecisionState = {
  approvalDraft: '',
  approvalPending: false,
  approvalSource: '',
  checkpointContinueReady: false,
  checkpointStageId: '',
  briefContinueReady: false,
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
    briefContinueReady: hydrated.briefContinueReady,
  };
}

export function briefApprovedState(
  state: StageDecisionState,
): StageDecisionState {
  return {
    ...state,
    approvalPending: false,
    checkpointContinueReady: false,
    checkpointStageId: '',
    briefContinueReady: true,
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
    briefContinueReady: false,
  };
}

export function continuationStartedState(
  state: StageDecisionState,
): StageDecisionState {
  return {
    ...state,
    checkpointContinueReady: false,
    checkpointStageId: '',
    briefContinueReady: false,
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
    briefContinueReady: false,
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
    briefContinueReady: false,
  };
}

export function stageDecisionStateForEvent(
  state: StageDecisionState,
  event: RunEvent,
): StageDecisionState {
  if (event.type === 'decision.required') {
    const stageId = event.stage_id || event.node_id?.split('.')[0] || 'brief';
    return {
      ...state,
      approvalPending: true,
      checkpointContinueReady: false,
      checkpointStageId: stageId,
      briefContinueReady: false,
    };
  }
  if (event.type === 'artifact.candidate_ready' && event.stage_id === 'brief' && event.payload) {
    const approvalDraft = formatResult(event.payload);
    return { ...state, approvalDraft, approvalSource: approvalDraft };
  }
  if (event.type === 'artifact.committed' && event.stage_id) {
    return event.stage_id === 'brief'
      ? briefApprovedState(state)
      : stageConfirmedState(state, event.stage_id);
  }
  return state;
}
