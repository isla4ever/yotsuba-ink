import type { CharacterGraph, CharacterTier as GraphTier } from '../contracts';
import type { CharacterBibleArtifact, CharacterKind } from './characterBibleArtifact';

const graphTier: Record<CharacterKind, GraphTier> = { protagonist: 'protagonist', major: 'major', functional: 'supporting', npc: 'npc', historical_record: 'npc' };

/** Rebuildable browsing projection. Coordinates and graph interaction never write back to the Artifact. */
export function projectCharacterBibleGraph(artifact: CharacterBibleArtifact): CharacterGraph {
  return {
    nodes: artifact.subjects.map((subject) => ({ faction: '', first_appearance_chapter: firstChapter(subject.debut), first_appearance_stage: 'cast', id: subject.id, name: subject.name, role: subject.function, status: subject.kind, tier: graphTier[subject.kind] })),
    edges: artifact.relations.map((relation) => ({ relation: relation.type, source: relation.a, strength: 0.72, target: relation.b, valid_from_stage: 'cast' })),
    updated_by: 'character-bible-artifact',
  };
}

function firstChapter(window: string) { return /^chapter:([1-9][0-9]*)/.exec(window)?.[1] ?? ''; }
