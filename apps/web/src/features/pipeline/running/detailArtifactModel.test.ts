import { describe, expect, it } from 'vitest';
import { detailBaseline, detailChapterReadiness, detailReadiness, detailWritebackSummary, graphWithDetailShifts } from './detailArtifactModel';
import { detailArtifact } from './stageArtifacts';

const info = JSON.stringify({
  worldbuilding_detail: '旧港雾钟系统记录声纹证词，蓝潮实验筛选关键证词。',
  characters: [{ name: '林澈', identity: '声纹修复师' }, { name: '许望舒', identity: '调查记者' }],
  relationships: [{ source: '林澈', target: '许望舒', relation: '调查同盟' }],
});
const outline = JSON.stringify({ volumes: [{
  title: '第一卷', chapter_range: '第1-3章', volume_goal: '查明旧案',
  character_progression: [], world_reveal: [{ anchor: '雾钟', reveal: '记录装置', rule: '只能记录既有声纹', impact: '保留证据链' }],
  foreshadow_plan: [{ name: '父亲签章', status: '投放', chapter_range: '第3章', note: '卷尾露出' }],
}] });
const detail = JSON.stringify({ chapters: [{
  chapter: '第1章', pov: '林澈', scene: '旧港档案馆', goal: '修复母带', entry_state: '回避旧案',
  conflict: '证据即将被封存', stakes: '旧案入口消失', hook: '母带喊出姓名', continuity_notes: '保持技术设定',
  character_shift: { character: '林澈', related_to: '许望舒', relation: '调查同盟', pressure: '物证可能消失', motivation: '保住母带', change: '主动追查', impact: '下一章调查来源' },
  fact_reveals: [{ anchor: '雾钟', fact: '母带真实存在', impact: '获得物证入口' }],
  wiki_candidates: [{ title: '7A-13 母带', fact: '保存十年前证词', source_anchor: '雾钟' }],
  foreshadow: [{ name: '父亲签章', status: '投放', note: '保留来源疑问' }],
}] });

describe('detail artifact model', () => {
  it('derives confirmed references and marks a complete draft ready', () => {
    const baseline = detailBaseline(info, outline);
    const readiness = detailReadiness(detailArtifact(detail), baseline);
    expect(baseline.characters.map((item) => item.name)).toEqual(['林澈', '许望舒']);
    expect(baseline.worldAnchors).toContain('雾钟');
    expect(baseline.foreshadows).toContain('父亲签章');
    expect(readiness.ready).toBe(true);
    expect(detailChapterReadiness(detailArtifact(detail).chapters[0], baseline)).toEqual({
      completed: 5,
      missingLabels: [],
      ready: true,
      total: 5,
    });
  });

  it('marks every duplicated chapter name incomplete', () => {
    const artifact = detailArtifact(detail);
    artifact.chapters.push(structuredClone(artifact.chapters[0]));
    const names = artifact.chapters.map((chapter) => chapter.chapter);
    const baseline = detailBaseline(info, outline);

    expect(detailChapterReadiness(artifact.chapters[0], baseline, 0, names).missingLabels).toContain('第1章施工蓝图');
    expect(detailChapterReadiness(artifact.chapters[1], baseline, 1, names).missingLabels).toContain('第1章施工蓝图');
    expect(detailReadiness(artifact, baseline).ready).toBe(false);
  });

  it('blocks unknown references and incomplete writebacks', () => {
    const artifact = detailArtifact(detail);
    artifact.chapters[0].pov = '陌生角色';
    artifact.chapters[0].wiki_candidates[0].source_anchor = '';
    expect(detailReadiness(artifact, detailBaseline(info, outline)).missingLabels).toEqual(expect.arrayContaining(['第1章施工蓝图', '第1章Wiki 候选']));
  });

  it('blocks duplicate fact, Wiki, and foreshadow entries within a chapter', () => {
    const artifact = detailArtifact(detail);
    artifact.chapters[0].fact_reveals.push(structuredClone(artifact.chapters[0].fact_reveals[0]));
    artifact.chapters[0].wiki_candidates.push(structuredClone(artifact.chapters[0].wiki_candidates[0]));
    artifact.chapters[0].foreshadow.push(structuredClone(artifact.chapters[0].foreshadow[0]));
    const readiness = detailChapterReadiness(artifact.chapters[0], detailBaseline(info, outline));
    expect(readiness.missingLabels).toEqual(expect.arrayContaining(['第1章事实揭示', '第1章Wiki 候选', '第1章伏笔动作']));
  });

  it('projects current draft shifts and summaries without mutating the base graph', () => {
    const artifact = detailArtifact(detail);
    const graph = { nodes: [{ id: 'a', name: '林澈', role: '主角', faction: '', status: '回避' }], edges: [], updated_by: 'info' };
    const projected = graphWithDetailShifts(graph, artifact);
    expect(projected.nodes[0].status).toBe('主动追查');
    expect(graph.nodes[0].status).toBe('回避');
    expect(detailWritebackSummary(artifact).worldbuilding).toContain('2 条');
  });

  it('previews parsed new_npcs as minor-tier nodes while preserving graph fields', () => {
    const artifact = detailArtifact(JSON.stringify({ chapters: [{
      chapter: '第1章', pov: '林澈', scene: '档案馆', goal: '追查', entry_state: '回避', conflict: '封存', stakes: '失去证据',
      character_shift: { character: '林澈', pressure: '物证可能消失', motivation: '保住母带', change: '主动追查', impact: '追查来源' },
      fact_reveals: [], wiki_candidates: [], foreshadow: [], hook: '异响', continuity_notes: '承接',
      new_npcs: [{ name: '守夜人老周', role: '档案馆看守', faction: '航运公会', note: '目击封存过程' }],
    }] }));
    const graph = {
      nodes: [{ id: 'a', name: '林澈', role: '主角', tier: 'protagonist' as const, faction: '雾港档案馆', status: '回避' }],
      edges: [],
      updated_by: 'outline',
    };

    const projected = graphWithDetailShifts(graph, artifact);

    expect(projected.nodes[0]).toMatchObject({ tier: 'protagonist', faction: '雾港档案馆' });
    expect(projected.nodes).toHaveLength(2);
    expect(projected.nodes[1]).toMatchObject({
      name: '守夜人老周',
      tier: 'minor',
      faction: '航运公会',
      status: '目击封存过程',
      first_appearance_stage: 'detail_outline',
      first_appearance_chapter: '第1章',
    });
  });

  it('normalizes legacy strings but keeps them incomplete for confirmation', () => {
    const artifact = detailArtifact(JSON.stringify({ chapters: [{
      chapter: '第1章', pov: '林澈', scene: '档案馆', goal: '追查', entry_state: '回避', conflict: '封存', stakes: '失去证据',
      fact_reveals: ['母带存在'], wiki_candidates: ['母带'], foreshadow: ['父亲签章'], character_shift: '主动追查', hook: '异响', continuity_notes: '承接',
    }] }));
    expect(artifact.chapters[0].character_shift.change).toBe('主动追查');
    expect(detailReadiness(artifact, detailBaseline(info, outline)).ready).toBe(false);
  });
});
