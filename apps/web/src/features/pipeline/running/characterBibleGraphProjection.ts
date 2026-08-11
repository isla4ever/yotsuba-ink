import type { CharacterGraph, CharacterTier as GraphTier } from '../contracts';
import type { CharacterBibleArtifact, CharacterTier } from './characterBibleArtifact';

const graphTier: Record<CharacterTier, GraphTier> = {
  functional: 'supporting',
  major: 'major',
  protagonist: 'protagonist',
};

/** Rebuildable browsing projection. It never writes coordinates or graph edits back to the Artifact. */
export function projectCharacterBibleGraph(artifact: CharacterBibleArtifact): CharacterGraph {
  return {
    edges: artifact.relationships.map((relationship) => ({
      relation: relationship.nature,
      source: relationship.source_id,
      strength: 0.72,
      target: relationship.target_id,
      valid_from_stage: 'characters',
    })),
    nodes: artifact.characters.map((character) => ({
      faction: '',
      first_appearance_chapter: firstChapter(character.first_appearance_window),
      first_appearance_stage: 'characters',
      id: character.id,
      name: character.name,
      role: character.narrative_function,
      status: 'frozen',
      tier: graphTier[character.tier],
    })),
    updated_by: 'character-bible-artifact',
  };
}

function firstChapter(window: string) {
  const match = /^chapter:([1-9][0-9]*)/.exec(window);
  return match?.[1] ?? '';
}
