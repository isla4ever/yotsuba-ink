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

  it('reads the current Spine candidate from the stable Artifact event', () => {
    const stage = {
      id: 'spine',
      type: 'spine',
    } as WorkflowStage;
    const artifact = {
      turns: [{ id: 'turn-1', cause: '母带被删除', change: '主角决定调查' }],
      ending: '公开母带并承担记忆损失',
      open_questions: ['谁签署了删除令？'],
      progress_types: ['information', 'external', 'internal'],
    };
    const events = [
      runEvent('artifact.candidate_ready', { payload: artifact, stage_id: 'spine', node_id: 'spine.generate_candidate', run_id: 'run' }),
      runEvent('node.completed', { stage_id: 'spine', node_id: 'spine.validate_contract', run_id: 'run' }),
    ];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'ready',
      result: JSON.stringify(artifact),
      source: 'live',
    });
  });

  it('rejects the deleted Summary-shaped Spine artifact', () => {
    const stage = { id: 'spine', type: 'spine' } as WorkflowStage;
    const events = [runEvent('artifact.candidate_ready', {
      payload: {
        beats: [{ id: 'beat-1', event: '发现母带' }],
        climax: '公开母带',
        resolution: '港区恢复记忆',
      },
      stage_id: 'spine',
      node_id: 'spine.generate_candidate',
      run_id: 'run',
    })];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'invalid',
      message: '模型返回内容未满足当前阶段的结构要求。',
    });
  });

  it('keeps a persisted Brief candidate visible while post-candidate control nodes request a decision', () => {
    const stage = {
      id: 'brief',
      type: 'brief',
    } as WorkflowStage;
    const artifact = {
      title: '雾港旧声',
      premise: '一名录音修复师追查被港区共同遗忘的广播。',
      promise: '每次修复都会揭开一层被人为抹去的城市记忆。',
      world_rules: ['旧广播只能在退潮时被听见'],
      theme: '记住真相是否值得失去安稳',
      ending_promise: '主角必须决定公开母带或永久封存。',
      voice: '克制的近距离第三人称',
      length_envelope: { word_target_soft: 80000, chapter_target_soft: 12 },
    };
    const events = [
      runEvent('decision.required', { sequence: 13, stage_id: 'brief', node_id: 'brief.human_decision', run_id: 'run' }),
      runEvent('node.started', { sequence: 12, stage_id: 'brief', node_id: 'brief.decision_policy', run_id: 'run' }),
      runEvent('node.completed', { sequence: 11, stage_id: 'brief', node_id: 'brief.validate_contract', run_id: 'run' }),
      runEvent('node.started', { sequence: 10, stage_id: 'brief', node_id: 'brief.validate_contract', run_id: 'run' }),
      runEvent('node.completed', { sequence: 9, stage_id: 'brief', node_id: 'brief.generate_candidate', run_id: 'run' }),
      runEvent('artifact.candidate_ready', { sequence: 8, payload: artifact, stage_id: 'brief', node_id: 'brief.generate_candidate', run_id: 'run' }),
      runEvent('node.started', { sequence: 7, stage_id: 'brief', node_id: 'brief.generate_candidate', run_id: 'run' }),
    ];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'ready',
      result: JSON.stringify(artifact),
      source: 'live',
    });
  });

  it('hides the previous candidate once regeneration starts a new candidate cycle', () => {
    const stage = {
      id: 'brief',
      type: 'brief',
    } as WorkflowStage;
    const oldArtifact = {
      title: '雾港旧声',
      premise: '旧候选',
      world_rules: ['旧规则'],
    };
    const events = [
      runEvent('node.started', { sequence: 18, stage_id: 'brief', node_id: 'brief.generate_candidate', run_id: 'run' }),
      runEvent('node.completed', { sequence: 17, stage_id: 'brief', node_id: 'brief.prepare_regeneration', run_id: 'run' }),
      runEvent('node.started', { sequence: 16, stage_id: 'brief', node_id: 'brief.prepare_regeneration', run_id: 'run' }),
      runEvent('artifact.candidate_ready', { sequence: 8, payload: oldArtifact, stage_id: 'brief', node_id: 'brief.generate_candidate', run_id: 'run' }),
    ];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'streaming',
      sections: ['generate candidate', 'prepare regeneration'],
    });
  });

  it('keeps a Chapter candidate visible throughout review and author decision nodes', () => {
    const stage = { id: 'text', type: 'text' } as WorkflowStage;
    const artifact = {
      chapter_id: 'chapter-1',
      version_id: 'chapter-1-v1',
      title: '第1章',
      content: '退潮时，修复室收到一盘没有登记记录的母带。',
      author_status: 'candidate',
    };
    const events = [
      runEvent('decision.required', { sequence: 18, stage_id: 'text', node_id: 'text.author_decision', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('node.started', { sequence: 17, stage_id: 'text', node_id: 'text.author_decision', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('node.completed', { sequence: 16, stage_id: 'text', node_id: 'text.evaluate_review_gate', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('node.started', { sequence: 15, stage_id: 'text', node_id: 'text.evaluate_review_gate', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('review.completed', { sequence: 14, stage_id: 'text', node_id: 'text.review_chapter', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('node.started', { sequence: 13, stage_id: 'text', node_id: 'text.review_chapter', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('node.started', { sequence: 12, stage_id: 'text', node_id: 'text.plan_review_roles', chapter_id: 'chapter-1', run_id: 'run' }),
      runEvent('artifact.candidate_ready', { sequence: 11, payload: artifact, stage_id: 'text', node_id: 'text.generate_prose', chapter_id: 'chapter-1', run_id: 'run' }),
    ];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'ready',
      result: JSON.stringify(artifact),
      source: 'live',
    });
  });

  it('does not carry a committed Chapter artifact into the next chapter cycle', () => {
    const stage = { id: 'text', type: 'text' } as WorkflowStage;
    const events = [
      runEvent('node.started', { sequence: 22, stage_id: 'text', node_id: 'text.compile_context', chapter_id: 'chapter-2', run_id: 'run' }),
      runEvent('artifact.committed', {
        sequence: 21,
        payload: { chapter_id: 'chapter-1', version_id: 'chapter-1-v1', title: '第1章', content: '第一章正文', author_status: 'accepted' },
        stage_id: 'text',
        node_id: 'text.commit_chapter',
        chapter_id: 'chapter-1',
        run_id: 'run',
      }),
    ];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'streaming',
      sections: ['compile context'],
    });
  });

  it('keeps an unselected Cover candidate visible so the author can choose an immutable asset', () => {
    const stage = { id: 'cover', type: 'cover' } as WorkflowStage;
    const artifact = {
      brief: {
        concept: '雾港中的旧录音',
        image_prompt: '雾港、旧录音带、克制悬疑',
        palette: ['深蓝', '锈红'],
        negative_constraints: ['无文字'],
      },
      selected_asset_id: '',
    };
    const events = [runEvent('artifact.candidate_ready', {
      payload: artifact,
      stage_id: 'cover',
      node_id: 'cover.generate_candidate',
      run_id: 'run',
    })];

    expect(stageArtifactState(stage, events)).toEqual({
      status: 'ready',
      result: JSON.stringify(artifact),
      source: 'live',
    });
  });
});
