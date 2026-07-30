import type { CharacterGraph, CharacterNode } from '../contracts';
import { normalizeTier } from './characterGraphSemantics';
import { parseArtifactRecord, type OutlineArtifact, type SummaryArtifact } from './stageArtifacts';

export type OutlineBaseline = {
  characters: Array<{ name: string; identity: string }>;
  relationships: Array<{ source: string; target: string; relation: string; strength: number; kind?: string; polarity?: string }>;
  summaryArcs: SummaryArtifact['character_arcs'];
  worldbuildingDetail: string;
  worldAnchors: string[];
};

export type OutlineReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export function outlineBaseline(infoValue: string, summaryValue = ''): OutlineBaseline {
  const info = parseArtifactRecord(infoValue);
  const summary = parseArtifactRecord(summaryValue);
  const characters = records(info?.characters).map((item) => ({
    identity: text(item.identity, '身份待定'),
    name: text(item.name),
  })).filter((item) => item.name);
  const relationships = records(info?.relationships).map((item) => ({
    relation: text(item.relation, '关系待定'),
    kind: text(item.kind),
    polarity: text(item.polarity),
    source: text(item.source),
    strength: strength(item.strength),
    target: text(item.target),
  })).filter((item) => item.source && item.target);
  const worldbuildingDetail = text(info?.worldbuilding_detail);
  return {
    characters,
    relationships,
    summaryArcs: records(summary?.character_arcs).map((item) => ({
      arc: text(item.arc),
      name: text(item.name),
      next: text(item.next),
      pressure: text(item.pressure),
    })),
    worldAnchors: worldAnchors(worldbuildingDetail),
    worldbuildingDetail,
  };
}

export function outlineReadiness(artifact: OutlineArtifact, baseline: OutlineBaseline): OutlineReadiness {
  const checks = artifact.volumes.flatMap((volume, index) => volumeChecks(volume, baseline, index));
  if (!artifact.volumes.length) checks.push({ label: '分卷列表', complete: false });
  return readinessFrom(checks);
}

export function outlineVolumeReadiness(volume: OutlineArtifact['volumes'][number], baseline: OutlineBaseline, index = 0): OutlineReadiness {
  return readinessFrom(volumeChecks(volume, baseline, index));
}

function volumeChecks(volume: OutlineArtifact['volumes'][number], baseline: OutlineBaseline, index: number) {
  const knownNames = new Set(baseline.characters.map((item) => item.name));
  const name = volume.title.trim() || `第 ${index + 1} 卷`;
  const relationKeys = new Set<string>();
  const clueNames = new Set<string>();
  const charactersReady = volume.character_progression.length > 0 && volume.character_progression.every((item) => {
      const key = [item.character, item.related_to].sort().join('::');
      const unique = !relationKeys.has(key);
      relationKeys.add(key);
      return unique
        && item.character !== item.related_to
        && knownNames.has(item.character)
        && knownNames.has(item.related_to)
        && filled(item.relation, item.pressure, item.change, item.impact);
  });
  const worldReady = volume.world_reveal.length > 0 && volume.world_reveal.every((item) => (
      baseline.worldbuildingDetail.includes(item.anchor) && filled(item.anchor, item.reveal, item.rule, item.impact)
  ));
  const foreshadowReady = volume.foreshadow_plan.length > 0 && volume.foreshadow_plan.every((item) => {
      const unique = !clueNames.has(item.name);
      clueNames.add(item.name);
      return unique && filled(item.name, item.status, item.chapter_range, item.note);
  });
  return [
    { label: `${name}基础信息`, complete: filled(volume.title, volume.chapter_range, volume.volume_goal, volume.rhythm ?? '') },
    { label: `${name}五段节拍`, complete: filled(volume.opening ?? '', volume.development ?? '', volume.midpoint ?? '', volume.climax ?? '', volume.resolution ?? '') },
    { label: `${name}人物承接`, complete: charactersReady },
    { label: `${name}世界观揭示`, complete: worldReady },
    { label: `${name}伏笔账本`, complete: foreshadowReady },
  ];
}

function readinessFrom(checks: Array<{ label: string; complete: boolean }>): OutlineReadiness {
  const missingLabels = checks.filter((check) => !check.complete).map((check) => check.label);
  return { completed: checks.length - missingLabels.length, missingLabels, ready: missingLabels.length === 0, total: checks.length };
}

export function outlineWritebackSummary(artifact: OutlineArtifact) {
  const counts = artifact.volumes.reduce((total, volume) => ({
    character: total.character + volume.character_progression.length,
    foreshadow: total.foreshadow + volume.foreshadow_plan.length,
    worldbuilding: total.worldbuilding + volume.world_reveal.length,
  }), { character: 0, foreshadow: 0, worldbuilding: 0 });
  return {
    character: counts.character ? `${counts.character} 条分卷人物承接，定稿后写回` : '',
    foreshadow: counts.foreshadow ? `${counts.foreshadow} 条伏笔计划，定稿后写回` : '',
    worldbuilding: counts.worldbuilding ? `${counts.worldbuilding} 条世界观揭示，定稿后写回` : '',
  };
}

export function graphWithOutlineProgressions(graph: CharacterGraph, artifact: OutlineArtifact): CharacterGraph {
  const pressureByName = new Map<string, string>();
  artifact.volumes.forEach((volume) => volume.character_progression.forEach((item) => {
    pressureByName.set(item.character, item.pressure || item.change);
  }));
  const nodes = graph.nodes.map((node) => ({ ...node, status: pressureByName.get(node.name) || node.status }));
  const knownNames = new Set(nodes.map((node) => node.name));
  const added: CharacterNode[] = [];
  artifact.volumes.forEach((volume) => (volume.new_characters ?? []).forEach((item) => {
    const name = item.name.trim();
    if (!name || knownNames.has(name)) return;
    knownNames.add(name);
    added.push({
      id: `outline-new-${added.length}`,
      name,
      role: item.role.trim(),
      tier: normalizeTier(item.tier, 'supporting'),
      faction: (item.faction ?? '').trim(),
      status: (item.stance ?? '').trim() || (item.relation_to_protagonist ?? '').trim(),
      first_appearance_stage: 'outline',
    });
  }));
  return {
    ...graph,
    nodes: [...nodes, ...added],
    updated_by: 'outline-artifact-draft',
  };
}

function worldAnchors(detail: string) {
  const anchors = detail.split(/[\n。；;]/).map((item) => item.trim()).filter(Boolean);
  return Array.from(new Set(anchors.length ? anchors : detail ? [detail] : [])).slice(0, 12);
}

function records(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
}

function text(value: unknown, fallback = '') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function strength(value: unknown) {
  const next = Number(value ?? 0.58);
  return Number.isFinite(next) ? Math.min(1, Math.max(0, next)) : 0.58;
}

function filled(...values: string[]) {
  return values.every((value) => Boolean(value.trim()));
}
