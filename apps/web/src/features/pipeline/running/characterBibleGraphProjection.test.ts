import { describe, expect, it } from 'vitest';
import type { CharacterBibleArtifact } from './characterBibleArtifact';
import { projectCharacterBibleGraph } from './characterBibleGraphProjection';

const artifact: CharacterBibleArtifact = {
  characters: [
    {
      arc: { end: '共同承担', start: '拒绝协作', turning_point: '共享证据' },
      external_goal: '找到原始母带',
      first_appearance_window: 'chapter:2-4',
      hard_boundaries: ['不销毁原始记录'],
      id: 'character-lin',
      inner_need: '承认记忆会失真',
      name: '林岚',
      narrative_function: '追查者',
      tier: 'protagonist',
    },
    {
      arc: { end: '交付档案', start: '隐藏线索', turning_point: '被迫表态' },
      external_goal: '保住档案室',
      first_appearance_window: 'chapter:3',
      hard_boundaries: [],
      id: 'character-zhou',
      inner_need: '承认旁观也是选择',
      name: '周屿',
      narrative_function: '证据守门人',
      tier: 'functional',
    },
  ],
  npc_slots: [],
  relationships: [{
    initial_state: '互相试探',
    nature: '有条件的同盟',
    pressure: '公开期限逼近',
    source_id: 'character-lin',
    target_id: 'character-zhou',
  }],
};

describe('Character Bible graph projection', () => {
  it('derives graph identity and appearance without storing layout coordinates', () => {
    const graph = projectCharacterBibleGraph(artifact);

    expect(graph.updated_by).toBe('character-bible-artifact');
    expect(graph.nodes[0]).toMatchObject({ first_appearance_chapter: '2', id: 'character-lin', tier: 'protagonist' });
    expect(graph.nodes[1]).toMatchObject({ id: 'character-zhou', tier: 'supporting' });
    expect(graph.edges[0]).toMatchObject({ relation: '有条件的同盟', source: 'character-lin', target: 'character-zhou' });
    expect(graph.nodes.some((node) => 'x' in node || 'y' in node || 'z' in node)).toBe(false);
  });
});
