import { describe, expect, it } from 'vitest';
import { graphWithSummaryArcs, summaryInfoBaseline, summaryReadiness, summaryWritebackDetail } from './summaryArtifactModel';
import type { SummaryArtifact } from './stageArtifacts';

describe('summary artifact model', () => {
  it('keeps the confirmed Info identities and relationship edges as the Summary baseline', () => {
    const baseline = summaryInfoBaseline(JSON.stringify({
      synopsis: '旧案从一盘母带重新浮现。',
      worldbuilding_detail: '雾钟只能记录声纹证词。',
      characters: [{ name: '林澈', identity: '声纹修复师' }],
      relationships: [{ source: '林澈', target: '许望舒', relation: '调查同盟', strength: 1.4 }],
    }));

    expect(baseline.characters).toEqual([{ name: '林澈', identity: '声纹修复师' }]);
    expect(baseline.relationships[0]).toMatchObject({ source: '林澈', target: '许望舒', strength: 1 });
  });

  it('blocks confirmation when a character arc does not reference an Info character', () => {
    const artifact = fixture();
    artifact.character_arcs[0].name = '陌生角色';

    expect(summaryReadiness(artifact, ['林澈'])).toMatchObject({ ready: false, missingLabels: ['人物弧'] });
  });

  it('requires relationship pressure and downstream impact before confirmation', () => {
    const artifact = fixture();
    artifact.character_arcs[0].pressure = '';
    artifact.character_arcs[0].next = '';

    expect(summaryReadiness(artifact, ['林澈'])).toMatchObject({ ready: false, missingLabels: ['人物弧'] });
  });

  it('projects confirmed character pressure into the graph without changing relationship edges', () => {
    const artifact = fixture();
    const graph = graphWithSummaryArcs({
      nodes: [{ id: 'c1', name: '林澈', role: '声纹修复师', faction: '调查组', status: '追查旧案' }],
      edges: [{ source: 'c1', target: 'c2', relation: '调查同盟', strength: 0.7 }],
      updated_by: 'info',
    }, artifact);

    expect(graph.nodes[0].status).toBe('父亲可能参与蓝潮实验');
    expect(graph.edges[0].relation).toBe('调查同盟');
    expect(summaryWritebackDetail(artifact)).toBe('1 条人物弧 · 1 条关系压力 · 1 条后续影响');
  });
});

function fixture(): SummaryArtifact {
  return {
    one_liner: '一盘旧磁带重新打开旧港失踪案。',
    full_synopsis: '林澈追查旧案，最终公开第一层真相并承担代价。',
    act_structure: [{ title: '入局', goal: '确认旧案存在', turn: '证词被改写' }],
    core_conflict: '个人记忆与公共档案冲突。',
    character_arcs: [{ name: '林澈', arc: '从修复档案到公开档案', pressure: '父亲可能参与蓝潮实验', next: '判断亲情和证据的边界' }],
    key_turns: [{ label: '缺页名单', detail: '三人确认删改记录。' }],
    ending_resolution: '公开第一层真相，保留父亲签章长线。',
    consistency_checks: ['雾钟仍是技术装置'],
  };
}
