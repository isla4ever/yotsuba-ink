import { describe, expect, it } from 'vitest';
import {
  graphWithOutlineProgressions,
  outlineBaseline,
  outlineReadiness,
  outlineVolumeReadiness,
  outlineWritebackSummary,
} from './outlineArtifactModel';
import type { OutlineArtifact } from './stageArtifacts';

const info = JSON.stringify({
  worldbuilding_detail: '旧港雾钟系统记录声纹证词；蓝潮实验只能筛选既有声纹。',
  characters: [
    { name: '林澈', identity: '声纹修复师' },
    { name: '许望舒', identity: '调查记者' },
  ],
  relationships: [{ source: '林澈', target: '许望舒', relation: '调查同盟', strength: 0.7 }],
});
const summary = JSON.stringify({
  character_arcs: [{ name: '林澈', arc: '开始公开证据', pressure: '证人可能暴露', next: '确认公开节奏' }],
});

describe('outline artifact model', () => {
  it('accepts a complete structured outline and derives writeback previews', () => {
    const artifact = completeOutline();
    const baseline = outlineBaseline(info, summary);

    const status = outlineReadiness(artifact, baseline);

    expect(status.ready).toBe(true);
    expect(status.missingLabels).toEqual([]);
    expect(outlineWritebackSummary(artifact)).toEqual({
      character: '1 条分卷人物承接，定稿后写回',
      foreshadow: '1 条伏笔计划，定稿后写回',
      worldbuilding: '1 条世界观揭示，定稿后写回',
    });
    expect(outlineVolumeReadiness(artifact.volumes[0], baseline)).toEqual({
      completed: 5,
      missingLabels: [],
      ready: true,
      total: 5,
    });
  });

  it('blocks missing beats, unknown references and incomplete dependency arrays', () => {
    const artifact = completeOutline();
    artifact.volumes[0].midpoint = '';
    artifact.volumes[0].character_progression[0].related_to = '陌生角色';
    artifact.volumes[0].world_reveal[0].anchor = '不存在的锚点';
    artifact.volumes[0].foreshadow_plan = [];

    const status = outlineReadiness(artifact, outlineBaseline(info, summary));

    expect(status.ready).toBe(false);
    expect(status.missingLabels).toEqual([
      '第一卷五段节拍',
      '第一卷人物承接',
      '第一卷世界观揭示',
      '第一卷伏笔账本',
    ]);
  });

  it('projects the current draft pressure onto the character graph', () => {
    const graph = {
      nodes: [{ id: 'lin', name: '林澈', role: '声纹修复师', faction: '', status: '旧状态' }],
      edges: [],
      updated_by: 'summary',
    };

    const next = graphWithOutlineProgressions(graph, completeOutline());

    expect(next.nodes[0].status).toBe('证据公开可能让许望舒失去证人');
    expect(next.updated_by).toBe('outline-artifact-draft');
  });

  it('keeps tier/faction/history fields and previews new_characters as supporting tier', () => {
    const graph = {
      nodes: [{ id: 'lin', name: '林澈', role: '声纹修复师', tier: 'protagonist' as const, faction: '雾港档案馆', faction_id: 'faction-雾港档案馆', status: '旧状态' }],
      edges: [{ source: 'lin', target: 'xu', relation: '调查同盟', strength: 0.7, kind: 'ally' as const, polarity: 'positive' as const, history: [{ stage: 'info', chapter: '', change: '建立同盟' }] }],
      factions: [{ id: 'faction-雾港档案馆', name: '雾港档案馆' }],
      updated_by: 'summary',
    };
    const artifact = completeOutline();
    artifact.volumes[0].new_characters = [
      { name: '陈默', role: '档案科长', faction: '航运公会', stance: '暗中阻挠' },
      { name: '林澈', role: '重复姓名不应加入' },
    ];

    const next = graphWithOutlineProgressions(graph, artifact);

    expect(next.nodes[0]).toMatchObject({ tier: 'protagonist', faction: '雾港档案馆', faction_id: 'faction-雾港档案馆' });
    expect(next.edges[0]).toMatchObject({ kind: 'ally', polarity: 'positive', history: [{ stage: 'info', chapter: '', change: '建立同盟' }] });
    expect(next.factions).toEqual(graph.factions);
    expect(next.nodes).toHaveLength(2);
    expect(next.nodes[1]).toMatchObject({ name: '陈默', tier: 'supporting', faction: '航运公会', status: '暗中阻挠', first_appearance_stage: 'outline' });
  });
});

function completeOutline(): OutlineArtifact {
  return {
    volumes: [{
      title: '第一卷',
      chapter_range: '第1-3章',
      volume_goal: '完成旧案入口',
      rhythm: '悬念递进',
      opening: '发现母带',
      development: '追查删改日志',
      midpoint: '证词被筛选',
      climax: '雾钟提前响起',
      resolution: '公开第一批证据',
      character_progression: [{
        character: '林澈',
        related_to: '许望舒',
        relation: '调查同盟',
        pressure: '证据公开可能让许望舒失去证人',
        change: '从回避转向公开',
        impact: '下一卷重新确认信任边界',
      }],
      world_reveal: [{
        anchor: '旧港雾钟系统记录声纹证词',
        reveal: '雾钟是证词装置',
        rule: '只能记录既有声纹',
        impact: '细纲保留技术证据链',
      }],
      foreshadow_plan: [{ name: '父亲签章', status: '投放', chapter_range: '第3章', note: '卷尾露出' }],
    }],
  };
}
