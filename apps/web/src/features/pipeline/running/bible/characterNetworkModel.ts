import { nodeTier } from '../characterGraphSemantics';
import { factionColor, unaffiliatedColor } from '../insights/characterGraphData';
import type {
  CharacterEdge,
  CharacterGraph,
  CharacterNode,
  CharacterTier,
  FactionStance,
  RelationKind,
  RelationPolarity,
} from '../../contracts';

export const tierOrder: CharacterTier[] = ['protagonist', 'major', 'supporting', 'minor', 'npc'];

export const tierLabels: Record<CharacterTier, string> = {
  protagonist: '主角',
  major: '核心角色',
  supporting: '配角',
  minor: '次要角色',
  npc: 'NPC',
};

export const kindLabels: Record<RelationKind, string> = {
  kinship: '亲缘', romance: '情感', ally: '同盟', rival: '对立', superior: '上下级', trade: '利益', secret: '秘密', other: '其他',
};

export const polarityLabels: Record<RelationPolarity, string> = {
  positive: '正向', negative: '负向', complex: '复杂', neutral: '中性',
};

export const stanceLabels: Record<FactionStance, string> = {
  protagonist_side: '主角阵营', antagonist_side: '敌对阵营', neutral: '中立', hidden: '隐藏立场',
};

const appearanceStageLabels: Record<string, string> = {
  info: '创作立项', info_recommend: '创作立项', summary: '全书梗概', outline: '分卷大纲',
  detail: '章节细纲', detail_outline: '章节细纲', text: '正文创作', chapter_text: '正文创作',
};

export function appearanceLabel(node: Pick<CharacterNode, 'first_appearance_stage' | 'first_appearance_chapter'>) {
  const stage = (node.first_appearance_stage ?? '').trim();
  const chapter = (node.first_appearance_chapter ?? '').trim();
  if (!stage && !chapter) return '';
  const stageLabel = stage ? appearanceStageLabels[stage] ?? stage : '';
  return [stageLabel, chapter].filter(Boolean).join(' · ');
}

/** Tiers that actually occur in the graph, in canonical order. */
export function tiersPresent(graph: CharacterGraph): CharacterTier[] {
  const present = new Set(graph.nodes.map((node) => nodeTier(node)));
  return tierOrder.filter((tier) => present.has(tier));
}

/** Hides nodes on the given tiers and drops edges that lose an endpoint. */
export function filterGraphByTiers(graph: CharacterGraph, hiddenTiers: ReadonlySet<CharacterTier>): CharacterGraph {
  if (!hiddenTiers.size) return graph;
  const nodes = graph.nodes.filter((node) => !hiddenTiers.has(nodeTier(node)));
  const visible = new Set(nodes.map((node) => node.id));
  return {
    ...graph,
    edges: graph.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)),
    nodes,
  };
}

export type FactionLegendEntry = {
  id: string;
  name: string;
  stance?: FactionStance;
  color: string;
  memberCount: number;
};

/** Legend entries from declared factions plus faction names only present on nodes; unaffiliated nodes get no entry. */
export function factionLegendEntries(graph: CharacterGraph): FactionLegendEntry[] {
  const entries = new Map<string, FactionLegendEntry>();
  (graph.factions ?? []).forEach((faction) => {
    if (!faction.name.trim()) return;
    entries.set(faction.name, { color: factionColor(faction.name), id: faction.id, memberCount: 0, name: faction.name, stance: faction.stance });
  });
  graph.nodes.forEach((node) => {
    const name = node.faction?.trim();
    if (!name) return;
    const entry = entries.get(name) ?? { color: factionColor(name), id: node.faction_id || `faction-${name}`, memberCount: 0, name };
    entry.memberCount += 1;
    entries.set(name, entry);
  });
  return Array.from(entries.values()).filter((entry) => entry.memberCount > 0);
}

export function nodeInFaction(node: Pick<CharacterNode, 'faction' | 'faction_id'>, entry: Pick<FactionLegendEntry, 'id' | 'name'>) {
  return node.faction_id === entry.id || node.faction?.trim() === entry.name;
}

/** Click toggles the highlighted faction; clicking the active one clears the highlight. */
export function toggleFactionHighlight(current: string, factionId: string) {
  return current === factionId ? '' : factionId;
}

export function nodeColor(node: Pick<CharacterNode, 'faction'>) {
  const name = node.faction?.trim();
  return name ? factionColor(name) : unaffiliatedColor;
}

export type CharacterRelationRow = {
  key: string;
  otherId: string;
  otherName: string;
  direction: 'out' | 'in';
  relation: string;
  kind?: RelationKind;
  polarity?: RelationPolarity;
  strength: number;
};

export type CharacterProfile = {
  node: CharacterNode;
  tier: CharacterTier;
  relations: CharacterRelationRow[];
};

export function characterProfile(graph: CharacterGraph, nodeId: string): CharacterProfile | null {
  const node = graph.nodes.find((item) => item.id === nodeId);
  if (!node) return null;
  const nameFor = (id: string) => graph.nodes.find((item) => item.id === id)?.name ?? id;
  const relations = graph.edges
    .filter((edge) => edge.source === nodeId || edge.target === nodeId)
    .map<CharacterRelationRow>((edge, index) => {
      const direction = edge.source === nodeId ? 'out' : 'in';
      const otherId = direction === 'out' ? edge.target : edge.source;
      return {
        direction,
        key: `${edge.source}-${edge.target}-${edge.relation}-${index}`,
        kind: edge.kind,
        otherId,
        otherName: nameFor(otherId),
        polarity: edge.polarity,
        relation: edge.relation,
        strength: edge.strength,
      };
    });
  return { node, relations, tier: nodeTier(node) };
}

/** Edge palette by polarity, shared by the 3D panorama; neutral doubles as the missing-data color. */
export const polarityColors: Record<RelationPolarity, string> = {
  positive: '#26c985', negative: '#e0596e', complex: '#e8b44c', neutral: '#8a94a6',
};

export function polarityColor(polarity?: RelationPolarity) {
  return polarityColors[polarity ?? 'neutral'];
}

export function relationSemantics(edge: Pick<CharacterEdge, 'kind' | 'polarity' | 'strength'>) {
  return [
    edge.kind ? kindLabels[edge.kind] : '',
    edge.polarity ? polarityLabels[edge.polarity] : '',
    `强度 ${Math.round(edge.strength * 100)}%`,
  ].filter(Boolean).join(' · ');
}

export function edgeHoverText(graph: CharacterGraph, edge: Pick<CharacterEdge, 'source' | 'target' | 'relation' | 'kind' | 'polarity' | 'strength'>) {
  const nameFor = (id: string) => graph.nodes.find((item) => item.id === id)?.name ?? id;
  return `${nameFor(edge.source)} → ${nameFor(edge.target)} · ${edge.relation} · ${relationSemantics(edge)}`;
}

/* ---- Chapter timeline replay (Phase 10.2b) ------------------------------ */

export type TimelineTick = {
  id: string;
  type: 'stage' | 'chapter' | 'current';
  label: string;
  chapter?: string;
};

export const currentTickId = 'current';

const timelineStageTicks: TimelineTick[] = [
  { id: 'stage:info', label: '基线 · 创作立项', type: 'stage' },
  { id: 'stage:summary', label: '全书梗概', type: 'stage' },
  { id: 'stage:outline', label: '分卷大纲', type: 'stage' },
  { id: 'stage:detail', label: '章节细纲', type: 'stage' },
];

/** Stage-name → fixed tick index (indices 0–3 of the four stage ticks). */
const stageTickIndex: Record<string, number> = {
  info: 0, info_recommend: 0, summary: 1, outline: 2, detail: 3, detail_outline: 3,
};

const textStageNames = new Set(['text', 'chapter_text']);

function chapterNumber(chapter: string) {
  const match = chapter.match(/\d+/);
  return match ? Number.parseInt(match[0], 10) : Number.MAX_SAFE_INTEGER;
}

function chapterTickLabel(chapter: string) {
  return /^\d+$/.test(chapter) ? `第${chapter}章` : chapter;
}

function collectChapter(target: Set<string>, value: string | undefined) {
  const chapter = (value ?? '').trim();
  if (chapter) target.add(chapter);
}

/**
 * Tick axis: four fixed stage ticks, then every chapter that appears in
 * first_appearance_chapter / valid_from_chapter / history[].chapter in natural
 * order, then「当前」(the full graph).
 */
export function networkTimelineTicks(graph: CharacterGraph): TimelineTick[] {
  const chapters = new Set<string>();
  graph.nodes.forEach((node) => collectChapter(chapters, node.first_appearance_chapter));
  graph.edges.forEach((edge) => {
    collectChapter(chapters, edge.valid_from_chapter);
    (edge.history ?? []).forEach((entry) => collectChapter(chapters, entry.chapter));
  });
  const chapterTicks = Array.from(chapters)
    .sort((left, right) => chapterNumber(left) - chapterNumber(right) || left.localeCompare(right, 'zh-Hans-CN'))
    .map<TimelineTick>((chapter) => ({ chapter, id: `chapter:${chapter}`, label: chapterTickLabel(chapter), type: 'chapter' }));
  return [...timelineStageTicks, ...chapterTicks, { id: currentTickId, label: '当前', type: 'current' }];
}

/**
 * Tick position of a temporal marker. Chapters win over stages; a text-stage
 * marker without a chapter only exists「当前」; empty markers (legacy runs)
 * degrade to the baseline tick — always visible, never fabricated.
 */
function markerTickIndex(ticks: TimelineTick[], stage: string | undefined, chapter: string | undefined) {
  const chapterKey = (chapter ?? '').trim();
  if (chapterKey) {
    const index = ticks.findIndex((tick) => tick.type === 'chapter' && tick.chapter === chapterKey);
    if (index >= 0) return index;
  }
  const stageKey = (stage ?? '').trim();
  if (stageKey in stageTickIndex) return stageTickIndex[stageKey];
  if (textStageNames.has(stageKey)) return ticks.length - 1;
  return 0;
}

/** True when any node/edge lacks temporal markers entirely — the UI must disclose baseline degradation. */
export function hasMissingTimelineMarkers(graph: CharacterGraph): boolean {
  const missing = (stage?: string, chapter?: string) => !(stage ?? '').trim() && !(chapter ?? '').trim();
  return (
    graph.nodes.some((node) => missing(node.first_appearance_stage, node.first_appearance_chapter))
    || graph.edges.some((edge) => missing(edge.valid_from_stage, edge.valid_from_chapter))
  );
}

/** Relation text as of the tick: the latest history change at or before it, else the edge's own relation. */
function relationAtTick(edge: CharacterEdge, ticks: TimelineTick[], tickIndex: number) {
  let relation = edge.relation;
  let latest = -1;
  (edge.history ?? []).forEach((entry) => {
    const change = (entry.change ?? '').trim();
    if (!change) return;
    const at = markerTickIndex(ticks, entry.stage, entry.chapter);
    if (at <= tickIndex && at >= latest) {
      latest = at;
      relation = change;
    }
  });
  return relation;
}

/**
 * Pure local filter: nodes/edges that already exist at the tick, with edge
 * relations replayed from history[]. The「当前」tick returns the graph as-is.
 */
export function graphAtTimelineTick(graph: CharacterGraph, ticks: TimelineTick[], tickId: string): CharacterGraph {
  const tickIndex = ticks.findIndex((tick) => tick.id === tickId);
  if (tickIndex < 0 || ticks[tickIndex].type === 'current') return graph;
  const nodes = graph.nodes.filter(
    (node) => markerTickIndex(ticks, node.first_appearance_stage, node.first_appearance_chapter) <= tickIndex,
  );
  const visible = new Set(nodes.map((node) => node.id));
  const edges = graph.edges
    .filter(
      (edge) => visible.has(edge.source) && visible.has(edge.target)
        && markerTickIndex(ticks, edge.valid_from_stage, edge.valid_from_chapter) <= tickIndex,
    )
    .map((edge) => ({ ...edge, relation: relationAtTick(edge, ticks, tickIndex) }));
  return { ...graph, edges, nodes };
}

/** Profile-panel viewpoint line, e.g.「视点：第3章」; empty for the current (full) view. */
export function timelineViewpointLabel(tick: TimelineTick | undefined): string {
  if (!tick || tick.type === 'current') return '';
  return `视点：${tick.label}`;
}
