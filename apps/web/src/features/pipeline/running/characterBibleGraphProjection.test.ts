import { describe, expect, it } from 'vitest';
import type { CharacterBibleArtifact } from './characterBibleArtifact';
import { projectCharacterBibleGraph } from './characterBibleGraphProjection';

const artifact: CharacterBibleArtifact = {
  subjects: [
    { id: 'subject-lin', name: '林岚', kind: 'protagonist', function: '追查者', drive: '找到原始母带', change: '承认记忆会失真', debut: 'chapter:2-4', limits: ['不销毁原始记录'], demand_refs: ['demand-investigator'] },
    { id: 'subject-zhou', name: '周屿', kind: 'functional', function: '证据守门人', drive: '保住档案室', change: '承认旁观也是选择', debut: 'chapter:3', limits: [], demand_refs: ['demand-gatekeeper'] },
    { id: 'subject-su-he', name: '前任档案员苏禾', kind: 'historical_record', function: '通过值班记录留下证据', drive: '保留原始记录', change: '由缺席证据改变当下判断', debut: 'chapter:4', limits: ['不得产生当下行动'], demand_refs: ['demand-record'] },
  ],
  relations: [{ a: 'subject-lin', b: 'subject-zhou', type: '有条件的同盟', pressure: '公开期限逼近' }],
};

describe('Character Bible graph projection', () => {
  it('derives graph identity and appearance without storing layout coordinates', () => {
    const graph = projectCharacterBibleGraph(artifact);

    expect(graph.updated_by).toBe('character-bible-artifact');
    expect(graph.nodes[0]).toMatchObject({ first_appearance_chapter: '2', id: 'subject-lin', tier: 'protagonist' });
    expect(graph.nodes[1]).toMatchObject({ id: 'subject-zhou', tier: 'supporting' });
    expect(graph.nodes[2]).toMatchObject({ id: 'subject-su-he', name: '前任档案员苏禾', status: 'historical', tier: 'npc' });
    expect(graph.edges[0]).toMatchObject({ relation: '有条件的同盟', source: 'subject-lin', target: 'subject-zhou' });
    expect(graph.nodes.some((node) => 'x' in node || 'y' in node || 'z' in node)).toBe(false);
  });
});
