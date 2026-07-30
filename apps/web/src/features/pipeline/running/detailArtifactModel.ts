import type { CharacterGraph, CharacterNode } from '../contracts';
import { outlineArtifact, parseArtifactRecord, type DetailOutlineArtifact } from './stageArtifacts';

export type DetailBaseline = {
  characters: Array<{ name: string; identity: string }>;
  relationships: Array<{ source: string; target: string; relation: string }>;
  worldbuildingDetail: string;
  worldAnchors: string[];
  foreshadows: string[];
};

export type DetailReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export function detailBaseline(infoValue: string, outlineValue: string): DetailBaseline {
  const info = parseArtifactRecord(infoValue);
  const outline = outlineArtifact(outlineValue);
  const characters = records(info?.characters).map((item) => ({
    identity: text(item.identity, '身份待定'),
    name: text(item.name),
  })).filter((item) => item.name);
  const relationships = records(info?.relationships).map((item) => ({
    relation: text(item.relation),
    source: text(item.source),
    target: text(item.target),
  })).filter((item) => item.source && item.target);
  const worldbuildingDetail = text(info?.worldbuilding_detail);
  const outlineAnchors = outline.volumes.flatMap((volume) => volume.world_reveal.map((item) => item.anchor));
  const infoAnchors = worldbuildingDetail.split(/[\n。；;]/).map((item) => item.trim()).filter(Boolean);
  return {
    characters,
    relationships,
    worldbuildingDetail,
    worldAnchors: Array.from(new Set([...outlineAnchors, ...infoAnchors])).filter(Boolean),
    foreshadows: Array.from(new Set(outline.volumes.flatMap((volume) => volume.foreshadow_plan.map((item) => item.name)))).filter(Boolean),
  };
}

export function detailReadiness(artifact: DetailOutlineArtifact, baseline: DetailBaseline): DetailReadiness {
  const chapterNames = artifact.chapters.map((chapter) => chapter.chapter.trim());
  const checks = artifact.chapters.flatMap((chapter, index) => chapterChecks(chapter, baseline, index, chapterNames));
  if (!artifact.chapters.length) checks.push({ label: '章节施工列表', complete: false });
  return readinessFrom(checks);
}

export function detailChapterReadiness(
  chapter: DetailOutlineArtifact['chapters'][number],
  baseline: DetailBaseline,
  index = 0,
  chapterNames: string[] = [chapter.chapter],
): DetailReadiness {
  return readinessFrom(chapterChecks(chapter, baseline, index, chapterNames));
}

function chapterChecks(
  chapter: DetailOutlineArtifact['chapters'][number],
  baseline: DetailBaseline,
  index: number,
  chapterNames: string[],
) {
  const names = new Set(baseline.characters.map((item) => item.name));
  const knownWorld = (anchor: string) => Boolean(anchor && (baseline.worldAnchors.includes(anchor) || baseline.worldbuildingDetail.includes(anchor)));
  const label = chapter.chapter || `第 ${index + 1} 章`;
  const chapterName = chapter.chapter.trim();
  const uniqueChapter = Boolean(chapterName) && chapterNames.filter((name) => name.trim() === chapterName).length === 1;
  const shift = chapter.character_shift;
  const relationReady = (!shift.related_to && !shift.relation)
    || (shift.related_to !== shift.character && names.has(shift.related_to) && Boolean(shift.relation));
  const factsUnique = uniqueText(chapter.fact_reveals.map((item) => item.fact));
  const wikiTitlesUnique = uniqueText(chapter.wiki_candidates.map((item) => item.title));
  const clueNamesUnique = uniqueText(chapter.foreshadow.map((item) => item.name));
  return [
    { label: `${label}施工蓝图`, complete: uniqueChapter && filled(chapter.chapter, chapter.pov, chapter.scene, chapter.goal, chapter.entry_state, chapter.conflict, chapter.stakes, chapter.hook, chapter.continuity_notes) && names.has(chapter.pov) },
    { label: `${label}人物变化`, complete: names.has(shift.character) && relationReady && filled(shift.pressure, shift.motivation, shift.change, shift.impact) },
    { label: `${label}事实揭示`, complete: factsUnique && chapter.fact_reveals.length > 0 && chapter.fact_reveals.every((item) => knownWorld(item.anchor) && filled(item.fact, item.impact)) },
    { label: `${label}Wiki 候选`, complete: wikiTitlesUnique && chapter.wiki_candidates.length > 0 && chapter.wiki_candidates.every((item) => knownWorld(item.source_anchor) && filled(item.title, item.fact)) },
    { label: `${label}伏笔动作`, complete: clueNamesUnique && chapter.foreshadow.length > 0 && chapter.foreshadow.every((item) => ['投放', '推进', '回收', '延后'].includes(item.status) && filled(item.name, item.status, item.note)) },
  ];
}

function readinessFrom(checks: Array<{ label: string; complete: boolean }>): DetailReadiness {
  const missingLabels = checks.filter((item) => !item.complete).map((item) => item.label);
  return { completed: checks.length - missingLabels.length, missingLabels, ready: missingLabels.length === 0, total: checks.length };
}

export function detailWritebackSummary(artifact: DetailOutlineArtifact) {
  const counts = artifact.chapters.reduce((total, chapter) => ({
    character: total.character + (chapter.character_shift.character ? 1 : 0),
    foreshadow: total.foreshadow + chapter.foreshadow.length,
    worldbuilding: total.worldbuilding + chapter.fact_reveals.length + chapter.wiki_candidates.length,
  }), { character: 0, foreshadow: 0, worldbuilding: 0 });
  return {
    character: counts.character ? `${counts.character} 章人物变化，定稿后写回` : '',
    foreshadow: counts.foreshadow ? `${counts.foreshadow} 条伏笔动作，定稿后写回` : '',
    worldbuilding: counts.worldbuilding ? `${counts.worldbuilding} 条事实 / Wiki 候选，定稿后写回` : '',
  };
}

export function graphWithDetailShifts(graph: CharacterGraph, artifact: DetailOutlineArtifact): CharacterGraph {
  const shifts = new Map(artifact.chapters.map((chapter) => [chapter.character_shift.character, chapter.character_shift]));
  const nodes = graph.nodes.map((node) => ({ ...node, status: shifts.get(node.name)?.change || shifts.get(node.name)?.pressure || node.status }));
  const knownNames = new Set(nodes.map((node) => node.name));
  const added: CharacterNode[] = [];
  artifact.chapters.forEach((chapter) => (chapter.new_npcs ?? []).forEach((item) => {
    const name = item.name.trim();
    if (!name || knownNames.has(name)) return;
    knownNames.add(name);
    added.push({
      id: `detail-npc-${added.length}`,
      name,
      role: item.role.trim(),
      tier: 'minor',
      faction: (item.faction ?? '').trim(),
      status: (item.note ?? '').trim(),
      first_appearance_stage: 'detail_outline',
      first_appearance_chapter: chapter.chapter.trim(),
    });
  }));
  return {
    ...graph,
    nodes: [...nodes, ...added],
    updated_by: 'detail-artifact-draft',
  };
}

function records(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
}

function text(value: unknown, fallback = '') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function filled(...values: string[]) {
  return values.every((value) => Boolean(value.trim()));
}

function uniqueText(values: string[]) {
  const normalized = values.map((value) => value.trim()).filter(Boolean);
  return normalized.length === new Set(normalized).size;
}
