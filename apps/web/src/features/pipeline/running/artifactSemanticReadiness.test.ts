import { describe, expect, it } from 'vitest';
import {
  characterBibleSemanticReadiness,
  coverSemanticReadiness,
  detailSemanticReadiness,
  outlineSemanticReadiness,
  summarySemanticReadiness,
} from './artifactSemanticReadiness';
import type { CharacterBibleArtifact } from './characterBibleArtifact';

const bible: CharacterBibleArtifact = {
  characters: [{
    id: 'char-lin',
    name: '林默',
    tier: 'protagonist',
    narrative_function: '调查母带失踪',
    external_goal: '找回母带',
    inner_need: '接受共同记忆',
    arc: { start: '拒绝合作', turning_point: '共享证据', end: '公开真相' },
    first_appearance_window: 'chapter:1',
    hard_boundaries: [],
  }],
  relationships: [],
  npc_slots: [{
    id: 'npc-archivist',
    function: '交付档案',
    first_appearance_window: 'chapter:2-3',
    limits: ['不得解决主冲突'],
  }],
};

describe('vNext Artifact semantic readiness', () => {
  it('requires a protagonist and bounded appearance windows', () => {
    const withoutProtagonist = {
      ...bible,
      characters: bible.characters.map((item) => ({ ...item, tier: 'major' as const })),
    };
    expect(characterBibleSemanticReadiness(withoutProtagonist, { characterBible: null }).missingLabels)
      .toContain('至少一名主角');
    expect(characterBibleSemanticReadiness(bible, { characterBible: null, totalChapters: 2 }).missingLabels)
      .toContain('首次出现窗口必须位于全书章节范围内');
  });

  it('rejects downstream character references outside the frozen Bible', () => {
    const result = {
      artifact: {
        beats: [{ id: 'beat-1', phase: 'opening', event: '母带失踪', consequence: '调查开始' }],
        climax: '公开母带',
        resolution: '港区恢复记忆',
        character_outcomes: [{ character_id: 'char-unknown', outcome: '离开' }],
      },
      errors: [],
    };
    expect(summarySemanticReadiness(result, { characterBible: bible }).missingLabels)
      .toContain('人物结局只能引用人物圣经');
  });

  it('requires Outline and Detail to cover the frozen plan exactly', () => {
    const outline = {
      artifact: {
        volumes: [{
          id: 'volume-1',
          chapter_window: 'chapter:1-2',
          objective: '找到母带',
          turns: [{ id: 'turn-1', event: '发现副本', consequence: '追捕升级' }],
          ending_state: '带着副本逃离',
          character_windows: [{ character_id: 'char-lin', entry_state: '独自调查', exit_state: '决定合作', turn_id: 'turn-1' }],
          thread_windows: [],
        }],
      },
      errors: [],
    };
    expect(outlineSemanticReadiness(outline, { characterBible: bible, totalChapters: 3 }).missingLabels)
      .toContain('分卷范围必须精确覆盖 1-3 章');

    const detail = {
      artifact: {
        chapters: [{
          id: 'chapter-1',
          number: 1,
          purpose: '取得档案',
          pov_character_id: 'char-lin',
          scenes: [{ id: 'scene-1', location: '档案室', goal: '取得登记簿', obstacle: '管理员拒绝', turn: '认出编号', outcome: '换得副本' }],
          obligations: [{ kind: 'character' as const, ref_id: 'npc-archivist', action: '交付档案' }],
          handoff: { unresolved_actions: [], emotional_carryover: [], next_pressure: '' },
        }],
      },
      errors: [],
    };
    expect(detailSemanticReadiness(detail, { characterBible: bible, totalChapters: 2 }).missingLabels)
      .toContain('施工图必须精确覆盖 2 章');
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

  it('blocks scale-dependent stages until the active Run definition loads', () => {
    const status = characterBibleSemanticReadiness(bible, { characterBible: null, requireFrozenScale: true });
    expect(status.ready).toBe(false);
    expect(status.missingLabels).toContain('冻结体量计划');
  });
});
