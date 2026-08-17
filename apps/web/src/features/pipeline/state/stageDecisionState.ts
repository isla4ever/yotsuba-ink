import type { RunEvent } from '../contracts';
import type { HydratedRunState } from './runState';

export type StageDecisionState = {
  approvalPending: boolean;
  checkpointContinueReady: boolean;
  checkpointStageId: string;
  briefContinueReady: boolean;
};

export const initialStageDecisionState: StageDecisionState = {
  approvalPending: false,
  checkpointContinueReady: false,
  checkpointStageId: '',
  briefContinueReady: false,
};

export function restoreStageDecisionState(
  hydrated: HydratedRunState,
): StageDecisionState {
  return {
    approvalPending: hydrated.approvalPending,
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
  if (event.type === 'artifact.committed' && event.stage_id) {
    return event.stage_id === 'brief'
      ? briefApprovedState(state)
      : stageConfirmedState(state, event.stage_id);
  }
  return state;
}
