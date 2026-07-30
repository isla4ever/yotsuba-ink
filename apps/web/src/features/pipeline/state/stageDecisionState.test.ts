import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import {
  continuationStartedState,
  decisionStateForPausedStream,
  exportReadyState,
  infoApprovedState,
  initialStageDecisionState,
  stageDecisionStateForEvent,
  stageConfirmedState,
} from './stageDecisionState';

describe('stage decision state', () => {
  it('keeps an approval checkpoint blocked until the user confirms', () => {
    const state = decisionStateForPausedStream(initialStageDecisionState, [
      event('approval_required', 'info'),
      event('stage_checkpoint_ready', 'info'),
    ]);

    expect(state.approvalPending).toBe(true);
    expect(state.checkpointStageId).toBe('info');
    expect(state.infoContinueReady).toBe(false);
    expect(state.checkpointContinueReady).toBe(false);
  });

  it('applies approval events without granting continue permission early', () => {
    const pending = stageDecisionStateForEvent(initialStageDecisionState, {
      ...event('approval_required', 'info'),
      artifact: { title: '候选标题' },
    });
    const approved = stageDecisionStateForEvent(pending, {
      ...event('artifact_approved', 'info'),
      artifact: { title: '定稿标题' },
    });

    expect(pending).toMatchObject({
      approvalPending: true,
      checkpointContinueReady: false,
      checkpointStageId: 'info',
      infoContinueReady: false,
    });
    expect(approved).toMatchObject({
      approvalPending: false,
      checkpointContinueReady: false,
      checkpointStageId: '',
      infoContinueReady: true,
    });
  });

  it('keeps regenerated drafts pending and confirms deep stages explicitly', () => {
    const regenerated = stageDecisionStateForEvent(initialStageDecisionState, {
      ...event('brief_regenerated', 'info'),
      artifact: { title: '新版标题' },
    });
    const confirmed = stageDecisionStateForEvent(regenerated, event('stage_artifact_confirmed', 'summary'));

    expect(regenerated.approvalPending).toBe(true);
    expect(regenerated.approvalDraft).toContain('新版标题');
    expect(confirmed).toMatchObject({
      approvalPending: false,
      checkpointContinueReady: true,
      checkpointStageId: 'summary',
      infoContinueReady: false,
    });
  });

  it('writes a selected Info candidate back into the still-blocked approval draft', () => {
    const pending = stageDecisionStateForEvent(initialStageDecisionState, {
      ...event('approval_required', 'info'),
      artifact: { selected_title: '当前稿' },
    });
    const selected = stageDecisionStateForEvent(pending, {
      ...event('draft_candidate_selected', 'info'),
      artifact: { selected_title: '候选定稿' },
    });

    expect(selected.approvalDraft).toContain('候选定稿');
    expect(selected).toMatchObject({
      approvalPending: true,
      checkpointStageId: 'info',
      infoContinueReady: false,
    });
  });

  it('does not revive an old checkpoint during an ordinary safe pause', () => {
    const previous = stageConfirmedState(initialStageDecisionState, 'summary');
    const continued = continuationStartedState(previous);
    const paused = decisionStateForPausedStream(continued, [
      event('run_paused', 'detail'),
      event('approval_required', 'summary'),
    ]);

    expect(paused).toEqual(continued);
  });

  it('makes Info continuable only after approval succeeds', () => {
    const pending = {
      ...initialStageDecisionState,
      approvalDraft: '{"title":"Draft"}',
      approvalPending: true,
      checkpointStageId: 'info',
    };

    expect(infoApprovedState(pending)).toEqual({
      approvalDraft: '{"title":"Draft"}',
      approvalPending: false,
      approvalSource: '',
      checkpointContinueReady: false,
      checkpointStageId: '',
      infoContinueReady: true,
    });
  });

  it('moves a confirmed deep stage into the explicit continue state', () => {
    const confirmed = stageConfirmedState(initialStageDecisionState, 'outline');

    expect(confirmed.checkpointStageId).toBe('outline');
    expect(confirmed.checkpointContinueReady).toBe(true);
    expect(confirmed.infoContinueReady).toBe(false);
  });

  it('clears checkpoint flags when continuing and restores the export return gate', () => {
    const confirmed = stageConfirmedState(initialStageDecisionState, 'cover');
    const continued = continuationStartedState(confirmed);
    const exportReady = exportReadyState(continued);

    expect(continued.checkpointStageId).toBe('');
    expect(continued.checkpointContinueReady).toBe(false);
    expect(exportReady.checkpointStageId).toBe('export');
    expect(exportReady.checkpointContinueReady).toBe(true);
  });
});

function event(type: string, nodeId: string): RunEvent {
  return { type, run_id: 'decision-test', node_id: nodeId };
}
