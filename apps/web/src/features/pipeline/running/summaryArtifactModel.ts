import type { CharacterGraph } from '../contracts';
import { parseArtifactRecord, type SummaryArtifact } from './stageArtifacts';

export type SummaryInfoBaseline = {
  characters: Array<{ name: string; identity: string }>;
  relationships: Array<{ source: string; target: string; relation: string; strength: number }>;
  synopsis: string;
  worldbuildingDetail: string;
};

export type SummaryReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export function summaryInfoBaseline(value: string): SummaryInfoBaseline {
  const record = parseArtifactRecord(value);
  const characters = recordList(record?.characters).map((item) => ({
    identity: text(item.identity, '身份待定'),
    name: text(item.name, '角色'),
  }));
  const relationships = recordList(record?.relationships)
    .map((item) => ({
      relation: text(item.relation, '关系待定'),
      source: text(item.source),
      strength: clampStrength(item.strength),
      target: text(item.target),
    }))
    .filter((item) => item.source && item.target);
  return {
    characters,
    relationships,
    synopsis: text(record?.synopsis),
    worldbuildingDetail: text(record?.worldbuilding_detail),
  };
}

export function summaryReadiness(artifact: SummaryArtifact, baselineNames: string[] = []): SummaryReadiness {
  const knownNames = new Set(baselineNames.filter(Boolean));
  const arcsComplete = artifact.character_arcs.length > 0 && artifact.character_arcs.every((arc) => (
    Boolean(arc.name.trim())
    && Boolean(arc.arc.trim())
    && Boolean(arc.pressure?.trim())
    && Boolean(arc.next?.trim())
    && (!knownNames.size || knownNames.has(arc.name.trim()))
  ));
  const checks = [
    { label: '故事核心', complete: Boolean(artifact.one_liner.trim()) },
    { label: '完整梗概', complete: Boolean(artifact.full_synopsis.trim()) },
    { label: '结构节拍', complete: artifact.act_structure.length > 0 && artifact.act_structure.every((act) => Boolean(act.title.trim() && act.goal.trim() && act.turn.trim())) },
    { label: '主线冲突', complete: Boolean(artifact.core_conflict.trim()) },
    { label: '人物弧', complete: arcsComplete },
    { label: '关键转折', complete: artifact.key_turns.length > 0 && artifact.key_turns.every((turn) => Boolean(turn.label.trim() && turn.detail.trim())) },
    { label: '结局承诺', complete: Boolean(artifact.ending_resolution.trim()) },
    { label: '一致性检查', complete: artifact.consistency_checks.some((item) => Boolean(item.trim())) },
  ];
  const missingLabels = checks.filter((check) => !check.complete).map((check) => check.label);
  return {
    completed: checks.length - missingLabels.length,
    missingLabels,
    ready: missingLabels.length === 0,
    total: checks.length,
  };
}

export function graphWithSummaryArcs(graph: CharacterGraph, artifact: SummaryArtifact): CharacterGraph {
  const arcsByName = new Map(artifact.character_arcs.map((arc) => [arc.name.trim(), arc]));
  return {
    ...graph,
    nodes: graph.nodes.map((node) => {
      const arc = arcsByName.get(node.name.trim());
      if (!arc) return node;
      return { ...node, status: arc.pressure?.trim() || arc.arc.trim() || node.status };
    }),
    updated_by: 'summary-artifact-draft',
  };
}

export function summaryWritebackDetail(artifact: SummaryArtifact) {
  const complete = artifact.character_arcs.filter((arc) => arc.name.trim() && arc.arc.trim());
  if (!complete.length) return '';
  const pressureCount = complete.filter((arc) => arc.pressure?.trim()).length;
  const impactCount = complete.filter((arc) => arc.next?.trim()).length;
  return `${complete.length} 条人物弧 · ${pressureCount} 条关系压力 · ${impactCount} 条后续影响`;
}

function recordList(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    : [];
}

function text(value: unknown, fallback = '') {
  const next = String(value ?? '').trim();
  return next || fallback;
}

function clampStrength(value: unknown) {
  const strength = Number(value ?? 0.58);
  return Number.isFinite(strength) ? Math.min(1, Math.max(0, strength)) : 0.58;
}
