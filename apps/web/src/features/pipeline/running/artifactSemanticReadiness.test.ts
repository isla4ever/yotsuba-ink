import { describe, expect, it } from 'vitest';
import {
  characterBibleSemanticReadiness,
  coverSemanticReadiness,
  detailSemanticReadiness,
  spineSemanticReadiness,
  volumeSemanticReadiness,
} from './artifactSemanticReadiness';
import type { StorySpineArtifact, VolumeArchitectureArtifact } from './artifactsVnext';
import type { CharacterBibleArtifact } from './characterBibleArtifact';

const bible: CharacterBibleArtifact = {
  subjects: [{
    id: 'subject-lin',
    name: '林默',
    kind: 'protagonist',
    function: '调查母带失踪',
    background: '旧港公共档案修复师，曾参与事故母带的初次修复。',
    conflict_history: '她亲眼见过事故母带被替换，却因证据不足保持沉默。',
    present_stakes: '若证据失效，她会失去职业资格和追查母亲去向的最后机会。',
    temperament: '受压时先核对记录，再逼迫对方作出明确选择。',
    speech_style: '短句，少下判断，习惯复述记录原文。',
    drive: '找回母带',
    change: '接受共同记忆',
    debut: 'chapter:1',
    limits: ['不得无证据背叛同伴'],
    demand_refs: ['demand-investigator'],
  }],
  relations: [],
};

const spine: StorySpineArtifact = {
  turns: [
    { id: 'turn-1', cause: '母带失踪', change: '调查开始', progress_type: 'information', milestones: ['inciting', 'commitment', 'midpoint_reversal'] },
    { id: 'turn-2', cause: '副本被发现', change: '追捕公开化', progress_type: 'internal', milestones: ['crisis', 'climax', 'aftermath'] },
  ],
  ending: '港区共同公开原始录音',
  open_questions: [],
  progress_types: ['information', 'internal'],
};

const volumes: VolumeArchitectureArtifact = {
  volumes: [{
    id: 'volume-1',
    title: '雾港残响',
    promise: '找到母带来源',
    conflict: '广播站封锁证据',
    climax: '在全港广播原始录音',
    climax_turn_ref: 'turn-2',
    closure: '林默接受共同作证',
    turn_refs: ['turn-1', 'turn-2'],
    cast_ids: ['subject-lin'],
    length_hint: 'medium',
  }],
};

describe('Phase 27 artifact semantic readiness', () => {
  it('requires a valid frozen Character Bible', () => {
    expect(characterBibleSemanticReadiness(null).missingLabels).toContain('有效的人物圣经');
    expect(characterBibleSemanticReadiness(bible).ready).toBe(true);
  });

  it('accepts a valid causal Spine contract', () => {
    expect(spineSemanticReadiness({ artifact: spine, errors: [] }).ready).toBe(true);
  });

  it('rejects unknown references and incomplete or reordered Spine coverage in Volumes', () => {
    const unknownRefs = structuredClone(volumes);
    unknownRefs.volumes[0].cast_ids = ['subject-unknown'];
    unknownRefs.volumes[0].turn_refs = ['turn-1', 'turn-unknown'];
    const unknownStatus = volumeSemanticReadiness({ artifact: unknownRefs, errors: [] }, { characterBible: bible, spine });
    expect(unknownStatus.missingLabels).toContain('每卷人物只能引用人物圣经中的主体');
    expect(unknownStatus.missingLabels).toContain('每卷转折只能引用已冻结的故事脊柱');

    const reordered = structuredClone(volumes);
    reordered.volumes[0].turn_refs = ['turn-2', 'turn-1'];
    expect(volumeSemanticReadiness({ artifact: reordered, errors: [] }, { characterBible: bible, spine }).missingLabels)
      .toContain('分卷必须按顺序完整覆盖故事脊柱，不能重叠或漏掉转折');
  });

  it('rejects Detail POV references outside the frozen Character Bible', () => {
    const result = {
      artifact: {
        chapters: [{
          ref: 'chapter-1',
          volume_ref: 'volume-1',
          title: '档案余烬',
          target_characters: 3000,
          turn_refs: ['turn-1'],
          purpose: '取得档案',
          pov: 'subject-unknown',
          cast_ids: ['subject-unknown'],
          scenes: [
            { place: '档案室', objective: '取得登记簿', conflict: '管理员拒绝', turn: '认出编号', result: '换得副本' },
            { place: '旧潮道', objective: '转移副本', conflict: '出口被封', turn: '找到暗门', result: '带走副本' },
          ],
          handoff: '广播站开始清理档案',
        }],
      },
      errors: [],
    };
    expect(detailSemanticReadiness(result, { characterBible: bible }).missingLabels)
      .toContain('本章出场人物只能引用人物圣经中的主体');
  });

  it('checks Detail scene counts against the current run capacity instead of a fixed product quota', () => {
    const chapter = {
      ref: 'chapter-1', volume_ref: 'volume-1', title: '档案余烬', target_characters: 2400,
      turn_refs: ['turn-1'], purpose: '取得档案', pov: 'subject-lin', cast_ids: ['subject-lin'],
      scenes: [{ place: '档案室', objective: '取得登记簿', conflict: '管理员拒绝', turn: '认出编号', result: '换得副本' }],
      handoff: '广播站开始清理档案',
    };
    const result = { artifact: { chapters: [chapter] }, errors: [] };

    expect(detailSemanticReadiness(result, { characterBible: bible, detailSceneRange: [1, 4] }).ready).toBe(true);
    expect(detailSemanticReadiness(result, { characterBible: bible, detailSceneRange: [2, 6] }).missingLabels)
      .toContain('每章场景数必须落在本次运行动态推导的 2-6 场容量区间内');
  });

  it('requires an active immutable candidate before Cover commit', () => {
    const result = {
      artifact: {
        brief: { concept: '雾港', image_prompt: '广播塔与雾', palette: ['#111111'], negative_constraints: [] },
        selected_asset_id: 'cover-stale',
      },
      errors: [],
    };
    expect(coverSemanticReadiness(result, { characterBible: bible, coverAssetIds: new Set(['cover-current']) }).missingLabels)
      .toContain('正式封面必须来自当前不可变候选');
  });

  it('accepts committed Cover metadata when this Run deliberately skips image generation', () => {
    const result = {
      artifact: {
        brief: { concept: '急救中心', image_prompt: '夜班调度室', palette: ['#111111'], negative_constraints: [] },
        selected_asset_id: '',
      },
      errors: [],
    };
    expect(coverSemanticReadiness(result, { characterBible: bible, coverAssetRequired: false }).ready).toBe(true);
  });
});
