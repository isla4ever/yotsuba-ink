import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import {
  continuationStartedState,
  decisionStateForPausedStream,
  exportReadyState,
  initialStageDecisionState,
  stageDecisionStateForEvent,
  stageConfirmedState,
} from './stageDecisionState';

describe('stage decision state', () => {
  it('blocks on the newest Graph interrupt', () => {
    const state = decisionStateForPausedStream(initialStageDecisionState, [
      runEvent('decision.required', { stage_id: 'info', node_id: 'info.human_decision' }),
    ]);
    expect(state).toMatchObject({ approvalPending: true, checkpointStageId: 'info', checkpointContinueReady: false });
  });

  it('loads an Info candidate from payload while preserving the interrupt', () => {
    const pending = stageDecisionStateForEvent(
      initialStageDecisionState,
      runEvent('decision.required', { stage_id: 'info', node_id: 'info.human_decision' }),
    );
    const candidate = stageDecisionStateForEvent(pending, runEvent('artifact.candidate_ready', {
      stage_id: 'info',
      node_id: 'info.generate_candidate',
      payload: { title: '候选标题' },
    }));
    expect(candidate.approvalPending).toBe(true);
    expect(candidate.approvalDraft).toContain('候选标题');
  });

  it('moves committed stages into explicit local navigation gates', () => {
    const info = stageDecisionStateForEvent(initialStageDecisionState, runEvent('artifact.committed', { stage_id: 'info' }));
    const outline = stageDecisionStateForEvent(initialStageDecisionState, runEvent('artifact.committed', { stage_id: 'outline' }));
    expect(info.infoContinueReady).toBe(true);
    expect(outline).toMatchObject({ checkpointContinueReady: true, checkpointStageId: 'outline' });
  });

  it('clears local navigation flags and restores the export return gate', () => {
    const continued = continuationStartedState(stageConfirmedState(initialStageDecisionState, 'cover'));
    expect(continued.checkpointContinueReady).toBe(false);
    expect(exportReadyState(continued)).toMatchObject({ checkpointContinueReady: true, checkpointStageId: 'export' });
  });
});
