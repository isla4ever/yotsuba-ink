import type { CharacterNode, CharacterTier, FactionStance, RelationKind, RelationPolarity } from '../contracts';

const CHARACTER_TIERS: CharacterTier[] = ['protagonist', 'major', 'supporting', 'minor', 'npc'];
const RELATION_KINDS: RelationKind[] = ['kinship', 'romance', 'ally', 'rival', 'superior', 'trade', 'secret', 'other'];
const RELATION_POLARITIES: RelationPolarity[] = ['positive', 'negative', 'complex', 'neutral'];
const FACTION_STANCES: FactionStance[] = ['protagonist_side', 'antagonist_side', 'neutral', 'hidden'];

export function normalizeTier(value: unknown, fallback: CharacterTier = 'supporting'): CharacterTier {
  const tier = String(value ?? '').trim().toLowerCase() as CharacterTier;
  return CHARACTER_TIERS.includes(tier) ? tier : fallback;
}

export function normalizeRelationKind(value: unknown): RelationKind {
  const kind = String(value ?? '').trim().toLowerCase() as RelationKind;
  return RELATION_KINDS.includes(kind) ? kind : 'other';
}

export function normalizeRelationPolarity(value: unknown): RelationPolarity {
  const polarity = String(value ?? '').trim().toLowerCase() as RelationPolarity;
  return RELATION_POLARITIES.includes(polarity) ? polarity : 'neutral';
}

export function normalizeFactionStance(value: unknown): FactionStance {
  const stance = String(value ?? '').trim().toLowerCase() as FactionStance;
  return FACTION_STANCES.includes(stance) ? stance : 'neutral';
}

export function factionIdFor(name: string) {
  const slug = name.trim().replace(/\s+/g, '-');
  return slug ? `faction-${slug}` : '';
}

/** Effective tier with lazy compatibility for legacy nodes without a tier field. */
export function nodeTier(node: Pick<CharacterNode, 'tier' | 'role'>): CharacterTier {
  if (node.tier && CHARACTER_TIERS.includes(node.tier)) return node.tier;
  return node.role?.includes('主角') ? 'protagonist' : 'supporting';
}
