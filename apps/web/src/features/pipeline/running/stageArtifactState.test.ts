import { describe, expect, it } from 'vitest';
import type { RunEvent, WorkflowStage } from '../contracts';
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

  it('prefers the persisted snapshot artifact over an older validation failure', () => {
    const stage = {
      id: 'summary',
      type: 'summary',
    } as WorkflowStage;
    const artifact = {
      act_structure: [{ title: '起' }],
      full_synopsis: '完整梗概',
      key_turns: [{ label: '转折' }],
    };
    const events = [
      { artifact, node_id: 'summary', run_id: 'run', type: 'artifact_validated' },
      { errors: ['旧校验失败'], node_id: 'summary', run_id: 'run', type: 'artifact_validation_failed' },
    ] as RunEvent[];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'ready',
      result: JSON.stringify(artifact),
      source: 'live',
    });
  });
});
