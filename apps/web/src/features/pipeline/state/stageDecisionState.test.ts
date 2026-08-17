import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import {
  continuationStartedState,
  decisionStateForPausedStream,
  initialStageDecisionState,
  stageDecisionStateForEvent,
  stageConfirmedState,
} from './stageDecisionState';

describe('stage decision state', () => {
  it('blocks on the newest Graph interrupt', () => {
    const state = decisionStateForPausedStream(initialStageDecisionState, [
      runEvent('decision.required', { stage_id: 'brief', node_id: 'brief.human_decision' }),
    ]);
    expect(state).toMatchObject({ approvalPending: true, checkpointStageId: 'brief', checkpointContinueReady: false });
  });

  it('keeps the Brief candidate out of decision state while preserving the interrupt', () => {
    const pending = stageDecisionStateForEvent(
      initialStageDecisionState,
      runEvent('decision.required', { stage_id: 'brief', node_id: 'brief.human_decision' }),
    );
    const candidate = stageDecisionStateForEvent(pending, runEvent('artifact.candidate_ready', {
      stage_id: 'brief',
      node_id: 'brief.generate_candidate',
      payload: { title: '候选标题' },
    }));
    expect(candidate.approvalPending).toBe(true);
    expect(candidate).toEqual(pending);
  });

  it('moves committed stages into explicit local navigation gates', () => {
    const brief = stageDecisionStateForEvent(initialStageDecisionState, runEvent('artifact.committed', { stage_id: 'brief' }));
    const volumes = stageDecisionStateForEvent(initialStageDecisionState, runEvent('artifact.committed', { stage_id: 'volumes' }));
    expect(brief.briefContinueReady).toBe(true);
    expect(volumes).toMatchObject({ checkpointContinueReady: true, checkpointStageId: 'volumes' });
  });

  it('clears local navigation flags after continuation begins', () => {
    const continued = continuationStartedState(stageConfirmedState(initialStageDecisionState, 'cover'));
    expect(continued.checkpointContinueReady).toBe(false);
  });
});
