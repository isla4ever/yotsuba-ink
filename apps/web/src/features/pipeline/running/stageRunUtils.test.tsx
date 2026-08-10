import { describe, expect, it } from 'vitest';
import { runEvent } from '../contracts/runEventTestFactory';
import { latestResult, statusText } from './stageRunUtils';

describe('stage Graph projections', () => {
  it('does not call Cover complete before a selected asset exists', () => {
    const events = [runEvent('artifact.committed', {
      stage_id: 'cover',
      node_id: 'cover.commit_artifact',
      payload: { brief: { concept: '简报', image_prompt: '雾港', palette: ['灰'], negative_constraints: [] }, selected_asset_id: '' },
    })];
    expect(statusText({ id: 'cover', type: 'cover' }, events)).toBe('待完善');
  });

  it('reads the current vNext Artifact from payload', () => {
    const artifact = { beats: [{ id: 'beat-1', phase: 'setup', event: '发现线索', consequence: '开始调查' }], climax: '公开真相', resolution: '调查结束', character_outcomes: [] };
    const events = [runEvent('artifact.candidate_ready', {
      stage_id: 'summary',
      node_id: 'summary.generate_candidate',
      payload: artifact,
    })];
    expect(latestResult(events, 'summary')).toBe(JSON.stringify(artifact));
  });
});
