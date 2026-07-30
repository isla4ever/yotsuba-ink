import type { WorkflowStage } from '../contracts';
import { normalizeRecommendation, type InfoRecommendation } from './infoRecommendationModel';
import { list, numberValue, objectList, objectRecord, parseArtifactRecord, text } from './artifactParsing';
export { parseArtifactRecord } from './artifactParsing';
export { coverArtifact, type CoverArtifact } from './coverArtifact';
export { exportArtifact, type ExportArtifact } from './exportArtifact';

export type SummaryArtifact = {
  one_liner: string;
  full_synopsis: string;
  act_structure: Array<{ title: string; goal: string; turn: string }>;
  core_conflict: string;
  key_turns: Array<{ label: string; detail: string }>;
  character_arcs: Array<{ name: string; arc: string; pressure?: string; next?: string }>;
  ending_resolution: string;
  consistency_checks: string[];
};

export type OutlineArtifact = {
  volumes: Array<{
    title: string;
    volume_goal: string;
    goal?: string;
    rhythm?: string;
    chapter_range: string;
    opening?: string;
    development?: string;
    midpoint?: string;
    climax?: string;
    resolution?: string;
    foreshadow_plan: OutlineForeshadow[];
    mid_twist?: string;
    volume_cliffhanger?: string;
    character_progression: OutlineCharacterProgression[];
    world_reveal: OutlineWorldReveal[];
    new_characters?: OutlineNewCharacter[];
  }>;
};

export type OutlineCharacterProgression = {
  character: string;
  related_to: string;
  relation: string;
  kind?: string;
  polarity?: string;
  strength?: number;
  pressure: string;
  change: string;
  impact: string;
};

export type OutlineNewCharacter = {
  name: string;
  role: string;
  tier?: string;
  faction?: string;
  faction_stance?: string;
  stance?: string;
  relation_to_protagonist?: string;
};

export type OutlineWorldReveal = {
  anchor: string;
  reveal: string;
  rule: string;
  impact: string;
};

export type OutlineForeshadow = {
  name: string;
  status: '投放' | '推进' | '回收' | '延后';
  chapter_range: string;
  note: string;
};

export type DetailOutlineArtifact = {
  chapters: Array<{
    chapter: string;
    pov: string;
    goal: string;
    scene: string;
    entry_state: string;
    conflict: string;
    stakes: string;
    fact_reveals: DetailFactReveal[];
    wiki_candidates: DetailWikiCandidate[];
    foreshadow: DetailForeshadow[];
    character_shift: DetailCharacterShift;
    hook: string;
    continuity_notes: string;
    new_npcs?: DetailNewNpc[];
  }>;
  coverage: {
    planned: number;
    generated: number;
    complete: boolean;
  };
};

export type DetailCharacterShift = {
  character: string;
  related_to: string;
  relation: string;
  kind?: string;
  polarity?: string;
  strength?: number;
  pressure: string;
  motivation: string;
  change: string;
  impact: string;
};

export type DetailNewNpc = { name: string; role: string; faction?: string; note?: string };
export type DetailFactReveal = { anchor: string; fact: string; impact: string };
export type DetailWikiCandidate = { title: string; fact: string; source_anchor: string; claim_key?: string };
export type DetailForeshadow = { name: string; status: '投放' | '推进' | '回收' | '延后'; note: string };


export function infoArtifact(value: string, stage: WorkflowStage): InfoRecommendation {
  return normalizeRecommendation(value, stage);
}

export function summaryArtifact(value: string): SummaryArtifact {
  const record = parseArtifactRecord(value);
  return {
    one_liner: text(record?.one_liner, ''),
    full_synopsis: text(record?.full_synopsis, ''),
    act_structure: objectList(record?.act_structure, []),
    core_conflict: text(record?.core_conflict, ''),
    key_turns: objectList(record?.key_turns, []),
    character_arcs: objectList(record?.character_arcs, []),
    ending_resolution: text(record?.ending_resolution ?? record?.ending_promise, ''),
    consistency_checks: list(record?.consistency_checks, []),
  };
}

export function outlineArtifact(value: string): OutlineArtifact {
  const record = parseArtifactRecord(value);
  return {
    volumes: objectList<Record<string, unknown>>(record?.volumes, []).map((volume) => ({
      title: text(volume.title, ''),
      chapter_range: text(volume.chapter_range, ''),
      volume_goal: text(volume.volume_goal ?? volume.goal, ''),
      goal: text(volume.goal, ''),
      rhythm: text(volume.rhythm, ''),
      opening: text(volume.opening, ''),
      development: text(volume.development, ''),
      midpoint: text(volume.midpoint ?? volume.mid_twist, ''),
      climax: text(volume.climax, ''),
      resolution: text(volume.resolution ?? volume.volume_cliffhanger, ''),
      mid_twist: text(volume.mid_twist, ''),
      volume_cliffhanger: text(volume.volume_cliffhanger, ''),
      character_progression: objectList<OutlineCharacterProgression>(volume.character_progression, []).map((item) => ({
        character: text(item.character, ''),
        related_to: text(item.related_to, ''),
        relation: text(item.relation, ''),
        kind: text(item.kind, ''),
        polarity: text(item.polarity, ''),
        strength: optionalNumber(item.strength),
        pressure: text(item.pressure, ''),
        change: text(item.change, ''),
        impact: text(item.impact, ''),
      })),
      new_characters: objectList<Record<string, unknown>>(volume.new_characters, []).map((item) => ({
        name: text(item.name, ''),
        role: text(item.role ?? item.identity, ''),
        tier: text(item.tier, ''),
        faction: text(item.faction, ''),
        faction_stance: text(item.faction_stance, ''),
        stance: text(item.stance, ''),
        relation_to_protagonist: text(item.relation_to_protagonist, ''),
      })).filter((item) => item.name).slice(0, 4),
      world_reveal: objectList<OutlineWorldReveal>(volume.world_reveal, []).map((item) => ({
        anchor: text(item.anchor, ''),
        reveal: text(item.reveal, ''),
        rule: text(item.rule, ''),
        impact: text(item.impact, ''),
      })),
      foreshadow_plan: objectList<OutlineForeshadow>(volume.foreshadow_plan, []).map((item) => ({
        name: text(item.name, ''),
        status: foreshadowStatus(item.status),
        chapter_range: text(item.chapter_range ?? (item as unknown as Record<string, unknown>).target_chapter, ''),
        note: text(item.note, ''),
      })),
    })),
  };
}

export function detailArtifact(value: string): DetailOutlineArtifact {
  const record = parseArtifactRecord(value);
  const chapters = objectList<Record<string, unknown>>(record?.chapters, []).map((chapter) => ({
    chapter: text(chapter.chapter, ''),
    pov: text(chapter.pov, ''),
    scene: text(chapter.scene, ''),
    goal: text(chapter.goal, ''),
    entry_state: text(chapter.entry_state, ''),
    conflict: text(chapter.conflict, ''),
    stakes: text(chapter.stakes, ''),
    fact_reveals: normalizeDetailFacts(chapter.fact_reveals ?? chapter.fact),
    foreshadow: normalizeDetailForeshadows(chapter.foreshadow),
    character_shift: normalizeDetailShift(chapter.character_shift, chapter.pov),
    hook: text(chapter.hook, ''),
    continuity_notes: text(chapter.continuity_notes ?? chapter.continuity, ''),
    wiki_candidates: normalizeDetailWiki(chapter.wiki_candidates),
    new_npcs: normalizeDetailNpcs(chapter.new_npcs),
  }));
  return {
    chapters,
    coverage: {
      planned: numberValue((record?.coverage as Record<string, unknown> | undefined)?.planned, chapters.length),
      generated: numberValue((record?.coverage as Record<string, unknown> | undefined)?.generated, chapters.length),
      complete: Boolean((record?.coverage as Record<string, unknown> | undefined)?.complete ?? chapters.length > 0),
    },
  };
}

function normalizeDetailShift(value: unknown, pov: unknown): DetailCharacterShift {
  const record = objectRecord(value);
  return {
    character: text(record?.character, text(pov, '')),
    related_to: text(record?.related_to, ''),
    relation: text(record?.relation, ''),
    kind: text(record?.kind, ''),
    polarity: text(record?.polarity, ''),
    strength: optionalNumber(record?.strength),
    pressure: text(record?.pressure, ''),
    motivation: text(record?.motivation, ''),
    change: text(record?.change, typeof value === 'string' ? value : ''),
    impact: text(record?.impact, ''),
  };
}

function normalizeDetailNpcs(value: unknown): DetailNewNpc[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const record = objectRecord(item);
    return {
      name: text(record?.name, ''),
      role: text(record?.role ?? record?.identity, ''),
      faction: text(record?.faction, ''),
      note: text(record?.note, ''),
    };
  }).filter((item) => item.name).slice(0, 2);
}

function normalizeDetailFacts(value: unknown): DetailFactReveal[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const record = objectRecord(item);
    return { anchor: text(record?.anchor, ''), fact: text(record?.fact, typeof item === 'string' ? item : ''), impact: text(record?.impact, '') };
  }).filter((item) => item.anchor || item.fact || item.impact);
}

function normalizeDetailWiki(value: unknown): DetailWikiCandidate[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const record = objectRecord(item);
    const legacy = typeof item === 'string' ? item : '';
    return { title: text(record?.title, legacy), fact: text(record?.fact, legacy), source_anchor: text(record?.source_anchor, ''), claim_key: text(record?.claim_key, '') };
  }).filter((item) => item.title || item.fact || item.source_anchor);
}

function normalizeDetailForeshadows(value: unknown): DetailForeshadow[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    const record = objectRecord(item);
    return { name: text(record?.name, typeof item === 'string' ? item : ''), status: foreshadowStatus(record?.status), note: text(record?.note, '') };
  }).filter((item) => item.name || item.note);
}


function foreshadowStatus(value: unknown): OutlineForeshadow['status'] {
  return ['投放', '推进', '回收', '延后'].includes(String(value)) ? value as OutlineForeshadow['status'] : '投放';
}

function optionalNumber(value: unknown) {
  return value === undefined || value === null || value === '' ? undefined : numberValue(value, 0);
}
