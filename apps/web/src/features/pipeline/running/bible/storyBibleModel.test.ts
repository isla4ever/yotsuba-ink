import { describe, expect, it } from 'vitest';
import { defaultWorkflow } from '../../state/defaultWorkflow';
import type { RunEvent } from '../../contracts';
import { runEvent } from '../../contracts/runEventTestFactory';
import { bibleCanonRows, bibleCharacterGraph, bibleForeshadowRows, bibleWorldView } from './storyBibleModel';

const event = (stageId: string, artifact: Record<string, unknown>): RunEvent => runEvent('artifact.committed', {
  payload: artifact,
  run_id: 'run-1',
  stage_id: stageId as RunEvent['stage_id'],
});

describe('vNext Story Bible projection', () => {
  it('reads frozen characters instead of enriching them from later stages', () => {
    const characters = {
      characters: [{ id: 'char-lin', name: '林默', tier: 'protagonist', narrative_function: '调查者', external_goal: '找到母带', inner_need: '承认恐惧', arc: { start: '独行', turning_point: '共享证据', end: '合作' }, first_appearance_window: 'chapter:1', hard_boundaries: [] }],
      relationships: [],
      npc_slots: [],
    };

    const result = bibleCharacterGraph([event('characters', characters)], defaultWorkflow);

    expect(result.source).toBe('committed');
    expect(result.graph.nodes.map((item) => item.id)).toEqual(['char-lin']);
    expect(result.graph.updated_by).toBe('characters-artifact');
  });

  it('projects world rules and detail obligations from current artifacts', () => {
    const info = { title: '雾港', premise: '追查母带', story_promise: { genre: '悬疑', audience: '成人', tone: '克制' }, world_rules: ['广播覆盖记忆'], thematic_question: '真相的代价？', ending_promise: '公开真相', voice: { viewpoint: '第三人称', tense: '过去时', texture: '听觉', avoid: [] }, cast_requirements: [] };
    const detail = { chapters: [{ id: 'chapter-1', number: 1, purpose: '调查', pov_character_id: 'char-lin', scenes: [{ id: 'scene-1', location: '港口', goal: '取证', obstacle: '广播', turn: '发现副本', outcome: '拿到证据' }], obligations: [{ kind: 'world_rule', ref_id: 'rule-broadcast', action: '展示规则代价' }], handoff: { unresolved_actions: [], emotional_carryover: [], next_pressure: '' } }] };

    const world = bibleWorldView([event('detail', detail), event('info', info)]);

    expect(world.rules[0].text).toBe('广播覆盖记忆');
    expect(world.anchors[0]).toMatchObject({ anchor: 'rule-broadcast', source: '章节施工图 · chapter-1' });
  });

  it('projects foreshadow windows and stable writeback events', () => {
    const outline = { volumes: [{ id: 'volume-1', chapter_window: 'chapter:1-2', objective: '取证', turns: [{ id: 'turn-1', event: '找到母带', consequence: '追捕升级' }], ending_state: '逃离', character_windows: [], thread_windows: [{ thread_id: 'thread-watch', kind: 'foreshadow', action: '投放怀表', chapter_window: 'chapter:1-2' }] }] };
    const writeback = runEvent('writeback.committed', { run_id: 'run-1', stage_id: 'text', chapter_id: 'chapter-1', event_id: 'wb-1', payload: { transaction_id: 'canon-chapter-1' } });

    expect(bibleForeshadowRows([event('outline', outline)])[0]).toMatchObject({ name: 'thread-watch', status: '投放' });
    expect(bibleCanonRows([writeback])[0]).toMatchObject({ status: 'active', target: 'canon-chapter-1' });
  });
});
