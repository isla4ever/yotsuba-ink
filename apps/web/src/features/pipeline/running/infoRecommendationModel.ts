import type { CharacterGraph, FactionInfo, WorkflowStage } from '../contracts';
import { factionIdFor, normalizeFactionStance, normalizeRelationKind, normalizeRelationPolarity, normalizeTier } from './characterGraphSemantics';

export type InfoEditorTarget = 'worldbuilding' | 'character';

export type CharacterRecommendation = {
  name: string;
  identity: string;
  background: string;
  motivation: string;
  relations: string;
  growth_direction: string;
  tier?: string;
  faction?: string;
  faction_stance?: string;
};

export type VoiceCharacterSheet = {
  character: string;
  habits: string;
  catchphrase: string;
  speech_register: string;
  never_says: string;
};

export type VoiceSpec = {
  narration: string;
  rhythm: string;
  banned_words: string[];
  cliche_slots: string[];
  per_character: VoiceCharacterSheet[];
};

export type InfoRecommendation = {
  selected_title: string;
  title_candidates: string[];
  tags: string[];
  synopsis: string;
  worldbuilding_detail: string;
  characters: CharacterRecommendation[];
  relationships: Array<{ source: string; target: string; relation: string; strength: number; kind?: string; polarity?: string }>;
  downstream_constraints: string[];
  risk_notes: string[];
  voice_spec?: VoiceSpec;
};

export type InfoRecommendationReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export function normalizeRecommendation(draft: string, stage: WorkflowStage): InfoRecommendation {
  const parsed = unwrapInfoRecord(parseRecord(draft));
  void stage;
  return {
    selected_title: firstString(parsed?.selected_title, firstItem(parsed?.title_candidates)),
    title_candidates: stringList(parsed?.title_candidates, []),
    tags: stringList(parsed?.tags, fallbackTags(parsed)),
    synopsis: firstString(parsed?.synopsis),
    worldbuilding_detail: worldbuildingDetail(parsed),
    characters: characterRecommendations(parsed?.characters ?? parsed?.character_seeds),
    relationships: relationshipRecommendations(parsed?.relationships),
    downstream_constraints: stringList(parsed?.downstream_constraints, []),
    risk_notes: stringList(parsed?.risk_notes, []),
    voice_spec: voiceSpec(parsed?.voice_spec),
  };
}

export function infoRecommendationReadiness(recommendation: InfoRecommendation): InfoRecommendationReadiness {
  const characterNames = recommendation.characters.map((character) => character.name.trim()).filter(Boolean);
  const knownCharacters = new Set(characterNames);
  const checks = [
    { label: '书名', complete: Boolean(recommendation.selected_title.trim() && recommendation.title_candidates.length) },
    { label: '小说简介', complete: Boolean(recommendation.synopsis.trim()) },
    { label: '详细世界观', complete: Boolean(recommendation.worldbuilding_detail.trim()) },
    {
      label: '人物档案',
      complete: recommendation.characters.length > 0 && recommendation.characters.every((character) => (
        Boolean(character.name.trim())
        && Boolean(character.identity.trim())
        && Boolean(character.motivation.trim())
        && Boolean(character.relations.trim())
      )) && new Set(characterNames).size === characterNames.length,
    },
    {
      label: '人物关系',
      complete: recommendation.relationships.every((relationship) => (
        Boolean(relationship.relation.trim())
        && relationship.source !== relationship.target
        && knownCharacters.has(relationship.source)
        && knownCharacters.has(relationship.target)
      )),
    },
  ];
  const missingLabels = checks.filter((check) => !check.complete).map((check) => check.label);
  return {
    completed: checks.length - missingLabels.length,
    missingLabels,
    ready: missingLabels.length === 0,
    total: checks.length,
  };
}

export function graphFromRecommendation(recommendation: InfoRecommendation): CharacterGraph {
  const { characters, relationships } = recommendation;
  const factions = new Map<string, FactionInfo>();
  const nodes = characters.map((character, index) => {
    const faction = (character.faction ?? '').trim();
    const factionId = factionIdFor(faction);
    if (factionId && !factions.has(factionId)) {
      factions.set(factionId, { id: factionId, name: faction, stance: normalizeFactionStance(character.faction_stance), first_appearance_stage: 'info' });
    }
    return {
      id: `draft-${index}`,
      name: character.name,
      role: character.identity,
      tier: normalizeTier(character.tier),
      faction,
      faction_id: factionId,
      status: character.motivation,
    };
  });
  const byName = new Map(nodes.map((node) => [node.name, node.id]));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = relationships
    .map((edge) => ({
      source: byName.get(edge.source) ?? edge.source,
      target: byName.get(edge.target) ?? edge.target,
      relation: edge.relation,
      kind: normalizeRelationKind(edge.kind),
      polarity: normalizeRelationPolarity(edge.polarity),
      strength: edge.strength,
    }))
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  return { nodes, edges, factions: Array.from(factions.values()), updated_by: 'info-recommendation-draft' };
}

export function recommendationGraphSignature(recommendation: InfoRecommendation) {
  return JSON.stringify({
    characters: recommendation.characters,
    relationships: recommendation.relationships,
  });
}

function unwrapInfoRecord(record: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!record) return null;
  for (const key of ['artifact', 'result', 'info_recommend', 'brief']) {
    const nested = record[key];
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) return nested as Record<string, unknown>;
  }
  return record;
}

function parseRecord(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

function firstString(...values: unknown[]) {
  return values.map((value) => String(value ?? '').trim()).find(Boolean) ?? '';
}

function firstItem(value: unknown) {
  return Array.isArray(value) ? value[0] : '';
}

function stringList(value: unknown, fallback: string[]) {
  if (Array.isArray(value)) {
    const items = value.map((item) => String(item ?? '').trim()).filter(Boolean);
    if (items.length) return items;
  }
  return fallback;
}

function fallbackTags(parsed: Record<string, unknown> | null) {
  const source = [
    firstString(parsed?.project_positioning),
    firstString(parsed?.core_hook),
  ].join(' / ');
  const items = source
    .split(/[，,；;、/]/)
    .map((item) => item.trim())
    .filter((item) => item && item.length <= 12 && !item.includes('等待'))
    .slice(0, 6);
  return items;
}

function worldDetailFrom(value: unknown) {
  const record = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
  if (!record) return firstString(value);
  const sections = [
    sectionLine('硬规则', record.rules ?? record.hard_rules ?? record.constraints),
    sectionLine('地点与空间', record.places ?? record.locations ?? record.spatial_design),
    sectionLine('组织与势力', record.groups ?? record.organizations ?? record.factions),
    sectionLine('禁忌与风险', record.taboos ?? record.risks ?? record.forbidden_rules),
  ].filter(Boolean);
  if (sections.length) return sections.join('\n');
  const rules = Array.isArray(record.rules) ? record.rules.join('；') : '';
  return [record.summary, rules].map((item) => String(item ?? '').trim()).filter(Boolean).join('\n');
}

function worldbuildingDetail(parsed: Record<string, unknown> | null) {
  return firstString(
    parsed?.worldbuilding_detail,
    parsed?.detailed_worldbuilding,
    parsed?.worldbuilding,
    worldDetailFrom(parsed?.world_seed),
  );
}

function sectionLine(label: string, value: unknown) {
  const text = Array.isArray(value)
    ? value.map((item) => String(item ?? '').trim()).filter(Boolean).join('；')
    : firstString(value);
  return text ? `${label}：${text}` : '';
}

function characterRecommendations(value: unknown): CharacterRecommendation[] {
  if (Array.isArray(value)) {
    const items = value
      .map((item) => item && typeof item === 'object' ? item as Record<string, unknown> : null)
      .filter((item): item is Record<string, unknown> => Boolean(item))
      .map((item) => ({
        name: firstString(item.name),
        identity: firstString(item.identity, item.role),
        background: firstString(item.background),
        motivation: firstString(item.motivation, item.drive, item.goal),
        relations: firstString(item.relations),
        growth_direction: firstString(item.growth_direction, item.growth, item.arc),
        tier: firstString(item.tier),
        faction: firstString(item.faction, item.group),
        faction_stance: firstString(item.faction_stance),
      }));
    if (items.length) return items;
  }
  return [];
}

function relationshipRecommendations(value: unknown): InfoRecommendation['relationships'] {
  if (Array.isArray(value)) {
    const items = value
      .map((item) => item && typeof item === 'object' ? item as Record<string, unknown> : null)
      .filter((item): item is Record<string, unknown> => Boolean(item))
      .map((item) => ({
        source: firstString(item.source),
        target: firstString(item.target),
        relation: firstString(item.relation),
        strength: clampStrength(item.strength),
        kind: firstString(item.kind),
        polarity: firstString(item.polarity),
      }))
      .filter((item) => item.source && item.target);
    if (items.length) return items;
  }
  return [];
}

function clampStrength(value: unknown) {
  const strength = Number(value ?? 0.6);
  if (!Number.isFinite(strength)) return 0.6;
  return Math.min(1, Math.max(0, strength));
}

function voiceSpec(value: unknown): VoiceSpec | undefined {
  const record = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
  if (!record) return undefined;
  const perCharacter = Array.isArray(record.per_character)
    ? record.per_character
      .map((item) => (item && typeof item === 'object' ? item as Record<string, unknown> : null))
      .filter((item): item is Record<string, unknown> => Boolean(item))
      .map((item) => ({
        character: firstString(item.character),
        habits: firstString(item.habits),
        catchphrase: firstString(item.catchphrase),
        speech_register: firstString(item.speech_register),
        never_says: firstString(item.never_says),
      }))
      .filter((item) => item.character)
    : [];
  return {
    narration: firstString(record.narration),
    rhythm: firstString(record.rhythm),
    banned_words: stringList(record.banned_words, []),
    cliche_slots: stringList(record.cliche_slots, []),
    per_character: perCharacter,
  };
}
