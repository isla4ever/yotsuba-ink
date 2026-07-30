import { describe, expect, it } from 'vitest';
import { graphFromRecommendation, infoRecommendationReadiness, normalizeRecommendation, type InfoRecommendation } from './infoRecommendationModel';
import type { WorkflowStage } from '../contracts';

describe('info recommendation model', () => {
  it('maps named relationships onto stable draft node ids', () => {
    const graph = graphFromRecommendation(recommendation([
      { source: '沈砚', target: '林雾', relation: '互相试探', strength: 0.72 },
    ]));

    expect(graph.edges).toEqual([
      { source: 'draft-0', target: 'draft-1', relation: '互相试探', strength: 0.72, kind: 'other', polarity: 'neutral' },
    ]);
  });

  it('returns empty edges instead of fabricating protagonist spokes when no relationship exists', () => {
    const graph = graphFromRecommendation(recommendation([]));

    expect(graph.edges).toEqual([]);
    expect(graph.nodes).toHaveLength(2);
  });

  it('reads the real faction field instead of fabricating parity-based factions', () => {
    const withFaction = recommendation([]);
    withFaction.characters[0].faction = '雾港档案馆';
    withFaction.characters[0].faction_stance = 'protagonist_side';

    const graph = graphFromRecommendation(withFaction);

    expect(graph.nodes[0].faction).toBe('雾港档案馆');
    expect(graph.nodes[1].faction).toBe('');
    expect(graph.factions).toEqual([
      { id: 'faction-雾港档案馆', name: '雾港档案馆', stance: 'protagonist_side', first_appearance_stage: 'info' },
    ]);
  });

  it('passes through tier/kind/polarity and falls back to honest defaults', () => {
    const typed = recommendation([
      { source: '沈砚', target: '林雾', relation: '旧案搭档', strength: 0.6, kind: 'ally', polarity: 'complex' },
    ]);
    typed.characters[0].tier = 'protagonist';

    const graph = graphFromRecommendation(typed);

    expect(graph.nodes[0].tier).toBe('protagonist');
    expect(graph.nodes[1].tier).toBe('supporting');
    expect(graph.edges[0]).toMatchObject({ kind: 'ally', polarity: 'complex' });
  });

  it('preserves the approved Info contract fields while dropping legacy presentation fields', () => {
    const normalized = normalizeRecommendation(JSON.stringify({
      selected_title: '雾港旧声',
      title_candidates: ['雾港旧声'],
      synopsis: '旧磁带牵出被改写的证词。',
      worldbuilding_detail: '硬规则：记忆改写必须留下声纹痕迹。',
      characters: [{
        name: '沈砚',
        identity: '调查员',
        motivation: '追查旧案',
        relations: '与林雾互相试探',
        growth_direction: '从独断走向协作',
      }],
      relationships: [],
      tags: ['悬疑'],
      downstream_constraints: ['证据链必须可追溯'],
      risk_notes: ['避免万能记忆解释'],
      project_positioning: '旧字段不应回写',
      editable_fields: ['旧字段'],
    }), {} as WorkflowStage);

    expect(normalized.characters[0].growth_direction).toBe('从独断走向协作');
    expect(normalized.downstream_constraints).toEqual(['证据链必须可追溯']);
    expect(normalized.risk_notes).toEqual(['避免万能记忆解释']);
    expect(normalized).not.toHaveProperty('project_positioning');
    expect(normalized).not.toHaveProperty('editable_fields');
  });

  it('blocks confirmation when a required character field is missing', () => {
    const incomplete = recommendation([]);
    incomplete.characters[0].relations = '';

    expect(infoRecommendationReadiness(incomplete)).toMatchObject({
      ready: false,
      missingLabels: ['人物档案'],
    });
  });

  it('blocks confirmation when character names or relationship references are ambiguous', () => {
    const invalid = recommendation([
      { source: '沈砚', target: '不存在的人物', relation: '旧案证人与调查者', strength: 0.72 },
    ]);
    invalid.characters[1].name = '沈砚';

    expect(infoRecommendationReadiness(invalid)).toMatchObject({
      ready: false,
      missingLabels: ['人物档案', '人物关系'],
    });
  });

  it('does not invent a relationship label while normalizing an editable brief', () => {
    const normalized = normalizeRecommendation(JSON.stringify({
      ...recommendation([]),
      relationships: [{ source: '沈砚', target: '林雾', relation: '', strength: 0.5 }],
    }), {} as WorkflowStage);

    expect(normalized.relationships[0].relation).toBe('');
    expect(infoRecommendationReadiness(normalized).missingLabels).toContain('人物关系');
  });
});

function recommendation(relationships: InfoRecommendation['relationships']): InfoRecommendation {
  return {
    selected_title: '雾港旧声',
    title_candidates: ['雾港旧声'],
    tags: [],
    synopsis: '旧磁带牵出被改写的证词。',
    worldbuilding_detail: '硬规则：记忆改写必须留下声纹痕迹。',
    downstream_constraints: [],
    risk_notes: [],
    characters: [
      { name: '沈砚', identity: '调查员', background: '', motivation: '追查旧案', relations: '与林雾互相试探', growth_direction: '' },
      { name: '林雾', identity: '证人', background: '', motivation: '保护秘密', relations: '旧案搭档', growth_direction: '' },
    ],
    relationships,
  };
}
