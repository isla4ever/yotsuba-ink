import { describe, expect, it } from 'vitest';
import type { RunEvent, WorkflowStage } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { currentStageArtifact, stageArtifactState } from './stageArtifactState';

describe('current stage artifact', () => {
  it('uses the edited artifact while its source is still current', () => {
    expect(currentStageArtifact('generated-v1', {
      source: 'generated-v1',
      value: 'edited-v1',
    })).toBe('edited-v1');
  });

  it('drops an edited artifact after candidate selection changes the source', () => {
    expect(currentStageArtifact('generated-v2', {
      source: 'generated-v1',
      value: 'edited-v1',
    })).toBe('generated-v2');
  });

  it('reads the current Summary candidate from the stable Artifact event', () => {
    const stage = {
      id: 'summary',
      type: 'summary',
    } as WorkflowStage;
    const artifact = {
      beats: [{ id: 'beat-1', phase: 'setup', event: '发现母带', consequence: '开始调查' }],
      climax: '公开母带',
      resolution: '港区恢复记忆',
      character_outcomes: [],
    };
    const events = [
      runEvent('artifact.candidate_ready', { payload: artifact, stage_id: 'summary', node_id: 'summary.generate_candidate', run_id: 'run' }),
      runEvent('node.completed', { stage_id: 'summary', node_id: 'summary.validate_contract', run_id: 'run' }),
    ];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'ready',
      result: JSON.stringify(artifact),
      source: 'live',
    });
  });
});
