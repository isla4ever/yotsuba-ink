import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { currentDraftCandidates, draftCandidateHistory } from './stageCandidateModel';

describe('stage candidate model', () => {
  it('uses the requested candidate count and keeps older candidates in history', () => {
    const events: RunEvent[] = [
      generated('request-2-candidate-1', 'request-2', '候选 1', 5),
      requested('request-2', 4, 2),
      generated('request-1-candidate-2', 'request-1', '候选 2', 3),
      generated('request-1-candidate-1', 'request-1', '候选 1', 2),
      requested('request-1', 1, 2),
    ];

    const current = currentDraftCandidates(events, 'info');
    const history = draftCandidateHistory(events, 'info');

    expect(current).toHaveLength(2);
    expect(current[0]).toMatchObject({ id: 'request-2-candidate-1', ready: true });
    expect(current[1]).toMatchObject({ id: 'pending-2', ready: false, status: 'generating' });
    expect(history.map((candidate) => candidate.id)).toEqual([
      'request-1-candidate-2',
      'request-1-candidate-1',
    ]);
  });

  it('does not invent candidate columns when a legacy request has no count', () => {
    const events: RunEvent[] = [requested('legacy-request', 1)];

    expect(currentDraftCandidates(events, 'info')).toEqual([]);
  });

  it('marks a requested slot as failed when its artifact contract is invalid', () => {
    const events: RunEvent[] = [
      {
        type: 'artifact_validation_failed',
        run_id: 'candidate-test',
        node_id: 'info',
        request_id: 'request-3',
        candidate_id: 'request-3-candidate-1',
        section: '候选 1',
        errors: ['人物档案缺失'],
        created_at: '2026-07-18T00:00:02Z',
      },
      requested('request-3', 1, 1),
    ];

    expect(currentDraftCandidates(events, 'info')[0]).toMatchObject({
      preview: '人物档案缺失',
      ready: false,
      status: 'failed',
    });
  });
});

function requested(requestId: string, second: number, count?: number): RunEvent {
  return {
    type: 'draft_regeneration_requested',
    run_id: 'candidate-test',
    node_id: 'info',
    request_id: requestId,
    candidate_count: count,
    created_at: `2026-07-18T00:00:0${second}Z`,
  };
}

function generated(candidateId: string, requestId: string, section: string, second: number): RunEvent {
  return {
    type: 'draft_candidate_generated',
    run_id: 'candidate-test',
    node_id: 'info',
    candidate_id: candidateId,
    request_id: requestId,
    section,
    artifact: { selected_title: candidateId },
    created_at: `2026-07-18T00:00:0${second}Z`,
  };
}
