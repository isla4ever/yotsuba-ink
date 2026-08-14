import { describe, expect, it } from 'vitest';
import {
  characterProfile,
  currentTickId,
  edgeHoverText,
  factionLegendEntries,
  filterGraphByTiers,
  graphAtTimelineTick,
  networkTimelineTicks,
  tiersPresent,
  timelineViewpointLabel,
  toggleFactionHighlight,
} from './characterNetworkModel';
import type { CharacterGraph, CharacterTier } from '../../contracts';

const graph: CharacterGraph = {
  nodes: [
    { id: 'p1', name: '沈默', role: '主角', faction: '调查组', faction_id: 'faction-调查组', status: '追查中', tier: 'protagonist', first_appearance_stage: 'text', first_appearance_chapter: '1' },
    { id: 'm1', name: '林岚', role: '搭档', faction: '调查组', faction_id: 'faction-调查组', status: '', tier: 'major', first_appearance_stage: 'text', first_appearance_chapter: '1' },
    { id: 'n1', name: '摊贩', role: '街头线人', faction: '', status: '', tier: 'npc', first_appearance_stage: 'detail', first_appearance_chapter: '第3章' },
  ],
  edges: [
    { source: 'p1', target: 'm1', relation: '搭档', strength: 0.8, kind: 'ally', polarity: 'positive', valid_from_stage: 'cast' },
    { source: 'n1', target: 'p1', relation: '递情报', strength: 0.3, kind: 'trade', valid_from_stage: 'detail' },
  ],
  factions: [{ id: 'faction-调查组', name: '调查组', stance: 'protagonist_side' }],
  updated_by: 'test',
};

describe('filterGraphByTiers', () => {
  it('hides the selected tiers and drops edges that lose an endpoint', () => {
    const filtered = filterGraphByTiers(graph, new Set<CharacterTier>(['npc']));
    expect(filtered.nodes.map((node) => node.id)).toEqual(['p1', 'm1']);
    expect(filtered.edges).toHaveLength(1);
    expect(filtered.edges[0].relation).toBe('搭档');
  });

  it('returns the graph unchanged with no hidden tiers and lists present tiers in order', () => {
    expect(filterGraphByTiers(graph, new Set())).toBe(graph);
    expect(tiersPresent(graph)).toEqual(['protagonist', 'major', 'npc']);
  });
});

describe('factionLegendEntries', () => {
  it('builds legend entries with stance and member counts, skipping unaffiliated nodes', () => {
    const legend = factionLegendEntries(graph);
    expect(legend).toHaveLength(1);
    expect(legend[0]).toMatchObject({ id: 'faction-调查组', memberCount: 2, name: '调查组', stance: 'protagonist_side' });
  });

  it('toggles the highlighted faction and clears it on a second click', () => {
    expect(toggleFactionHighlight('', 'faction-调查组')).toBe('faction-调查组');
    expect(toggleFactionHighlight('faction-调查组', 'faction-调查组')).toBe('');
    expect(toggleFactionHighlight('faction-调查组', 'faction-别组')).toBe('faction-别组');
  });
});

describe('characterProfile', () => {
  it('collects both edge directions with kind, polarity and strength for the selected node', () => {
    const profile = characterProfile(graph, 'p1');
    expect(profile?.tier).toBe('protagonist');
    expect(profile?.relations).toHaveLength(2);
    expect(profile?.relations[0]).toMatchObject({ direction: 'out', kind: 'ally', otherName: '林岚', polarity: 'positive' });
    expect(profile?.relations[1]).toMatchObject({ direction: 'in', otherName: '摊贩' });
    expect(characterProfile(graph, 'missing')).toBeNull();
  });

  it('renders edge hover text with names and relation semantics', () => {
    expect(edgeHoverText(graph, graph.edges[0])).toBe('沈默 → 林岚 · 搭档 · 同盟 · 正向 · 强度 80%');
  });
});

const timelineGraph: CharacterGraph = {
  nodes: [
    { id: 'p1', name: '沈默', role: '主角', faction: '', status: '', tier: 'protagonist', first_appearance_stage: 'brief' },
    { id: 's1', name: '陆遥', role: '卷一对手', faction: '', status: '', tier: 'supporting', first_appearance_stage: 'volumes' },
    { id: 'n1', name: '茶馆掌柜', role: '线人', faction: '', status: '', tier: 'npc', first_appearance_stage: 'detail', first_appearance_chapter: '第3章' },
    { id: 'n2', name: '巡夜人', role: '路人', faction: '', status: '', tier: 'npc', first_appearance_stage: 'detail', first_appearance_chapter: '12' },
  ],
  edges: [
    {
      source: 'p1', target: 's1', relation: '暗中较劲', strength: 0.6, valid_from_stage: 'volumes',
      history: [{ change: '初次交锋', stage: 'volumes' }, { change: '结为盟友', chapter: '第5章' }],
    },
    { source: 'n1', target: 'p1', relation: '递情报', strength: 0.3, valid_from_stage: 'detail', valid_from_chapter: '第3章' },
  ],
  updated_by: 'test',
};

describe('networkTimelineTicks', () => {
  it('derives five fixed planning ticks, naturally sorted chapter ticks and a trailing current tick', () => {
    const ticks = networkTimelineTicks(timelineGraph);
    expect(ticks.map((tick) => tick.label)).toEqual([
      '基线 · 创作立项', '故事脊柱', '人物编排', '分卷架构', '章节施工图', '第3章', '第5章', '第12章', '当前',
    ]);
    expect(ticks[ticks.length - 1].id).toBe(currentTickId);
  });

  it('collects chapters from first_appearance, valid_from and history without duplicates', () => {
    const ticks = networkTimelineTicks(timelineGraph);
    expect(ticks.filter((tick) => tick.type === 'chapter').map((tick) => tick.chapter)).toEqual(['第3章', '第5章', '12']);
  });
});

describe('graphAtTimelineTick', () => {
  const ticks = networkTimelineTicks(timelineGraph);

  it('shows only nodes and edges that already exist at a stage tick', () => {
    const atSpine = graphAtTimelineTick(timelineGraph, ticks, 'stage:spine');
    expect(atSpine.nodes.map((node) => node.id)).toEqual(['p1']);
    expect(atSpine.edges).toHaveLength(0);
    const atVolumes = graphAtTimelineTick(timelineGraph, ticks, 'stage:volumes');
    expect(atVolumes.nodes.map((node) => node.id)).toEqual(['p1', 's1']);
    expect(atVolumes.edges).toHaveLength(1);
  });

  it('replays edge relations from the latest history entry at or before the tick', () => {
    const atVolumes = graphAtTimelineTick(timelineGraph, ticks, 'stage:volumes');
    expect(atVolumes.edges[0].relation).toBe('初次交锋');
    const atChapter3 = graphAtTimelineTick(timelineGraph, ticks, 'chapter:第3章');
    expect(atChapter3.edges.map((edge) => edge.relation)).toEqual(['初次交锋', '递情报']);
    const atChapter5 = graphAtTimelineTick(timelineGraph, ticks, 'chapter:第5章');
    expect(atChapter5.edges[0].relation).toBe('结为盟友');
  });

  it('returns the graph unchanged on the current tick', () => {
    expect(graphAtTimelineTick(timelineGraph, ticks, currentTickId)).toBe(timelineGraph);
  });

});

describe('timelineViewpointLabel', () => {
  it('labels stage and chapter viewpoints and stays silent on the current tick', () => {
    const ticks = networkTimelineTicks(timelineGraph);
    expect(timelineViewpointLabel(ticks[1])).toBe('视点：故事脊柱');
    expect(timelineViewpointLabel(ticks.find((tick) => tick.chapter === '12'))).toBe('视点：第12章');
    expect(timelineViewpointLabel(ticks[ticks.length - 1])).toBe('');
    expect(timelineViewpointLabel(undefined)).toBe('');
  });
});
