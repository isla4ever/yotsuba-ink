import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { runtimeArtifactProjection } from './runtimeArtifactProjection';

const info = JSON.stringify({
  title: '雾港母带',
  premise: '调查一卷会改写记忆的失踪母带。',
  story_promise: { genre: '悬疑', audience: '成人', tone: '克制' },
  world_rules: ['广播只会覆盖被明确标记的记忆'],
  thematic_question: '公开真相是否值得失去私人记忆？',
  ending_promise: '母带来源会在终章公开。',
  voice: { viewpoint: '第三人称有限视角', tense: '过去时', texture: '听觉细节', avoid: [] },
  cast_requirements: [],
});

const characters = JSON.stringify({
  characters: [{
    id: 'char-lin',
    name: '林默',
    tier: 'protagonist',
    narrative_function: '承担真相调查',
    external_goal: '找到母带',
    inner_need: '承认自己需要同伴',
    arc: { start: '独自调查', turning_point: '共享证据', end: '共同公开真相' },
    first_appearance_window: 'chapter:1',
    hard_boundaries: [],
  }],
  relationships: [],
  npc_slots: [],
});

const detail = JSON.stringify({
  chapters: [{
    id: 'chapter-1',
    number: 1,
    purpose: '取得第一份证据',
    pov_character_id: 'char-lin',
    scenes: [{
      id: 'scene-1',
      location: '旧港仓库',
      goal: '取回母带',
      obstacle: '仓库被封锁',
      turn: '发现一份副本',
      outcome: '带走副本',
    }],
    obligations: [
      { kind: 'character', ref_id: 'char-lin', action: '让林默主动共享线索' },
      { kind: 'world_rule', ref_id: 'rule-radio', action: '展示广播规则的代价' },
      { kind: 'thread', ref_id: 'thread-watch', action: '投放怀表线索' },
    ],
    handoff: { unresolved_actions: [], emotional_carryover: [], next_pressure: '追兵接近' },
  }],
});

describe('runtimeArtifactProjection', () => {
  it('projects only vNext artifacts and the latest stable writeback event', () => {
    const events: RunEvent[] = [
      runEvent('writeback.committed', { run_id: 'run-1', stage_id: 'detail', sequence: 4, payload: { transaction_id: 'tx-old' } }),
      runEvent('writeback.queued', { run_id: 'run-1', stage_id: 'detail', sequence: 5, payload: { transaction_id: 'tx-current' } }),
    ];

    const projection = runtimeArtifactProjection({
      activeStageType: 'detail',
      characters,
      detail,
      events,
      info,
      outline: '',
      summary: '',
    });

    expect(projection.characterGraph?.nodes).toHaveLength(1);
    expect(projection.characterGraph?.updated_by).toBe('characters-artifact');
    expect(projection.worldbuilding?.rules).toEqual(['广播只会覆盖被明确标记的记忆']);
    expect(projection.stage).toEqual({
      character: '1 条人物义务引用冻结角色',
      worldbuilding: '1 条世界规则义务，仅作章节约束提示',
      foreshadow: '1 条线索义务与 1 个章节交接',
    });
    expect(projection.writeback).toEqual({
      status: 'queued',
      label: '写回已进入事务队列',
      transactionId: 'tx-current',
    });
  });

  it('does not project old Detail fields or unrelated stage writebacks', () => {
    const projection = runtimeArtifactProjection({
      activeStageType: 'detail',
      characters,
      detail: JSON.stringify({ schema_version: 3, chapters: [], character_shift: [] }),
      events: [runEvent('writeback.failed', { run_id: 'run-1', stage_id: 'text', sequence: 2, payload: { transaction_id: 'tx-text' } })],
      info,
      outline: '',
      summary: '',
    });

    expect(projection.stage).toEqual({});
    expect(projection.writeback.status).toBe('not_proposed');
    expect(projection.writeback.transactionId).toBe('');
  });
});
