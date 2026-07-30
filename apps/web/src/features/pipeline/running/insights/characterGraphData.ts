import type { CharacterNode, CharacterTier } from '../../contracts';
import { nodeTier } from '../characterGraphSemantics';

const factionPalette = ['#2f7df6', '#18b6c8', '#26c985', '#e8b44c', '#9b7cff'];

/** Neutral gray for nodes without an annotated faction — missing data stays visibly missing. */
export const unaffiliatedColor = '#8a94a6';

/** Stable name-hash palette mapping: same faction name always gets the same color. */
export function factionColor(faction: string | undefined) {
  const name = (faction ?? '').trim();
  if (!name) return unaffiliatedColor;
  return factionPalette[stableHash(name) % factionPalette.length];
}

function stableHash(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

const tierRingRadius: Record<CharacterTier, number> = {
  protagonist: 0,
  major: 132,
  supporting: 232,
  minor: 324,
  npc: 324,
};

const tierNodeSize: Record<CharacterTier, number> = {
  protagonist: 5.8,
  major: 4.9,
  supporting: 4.2,
  minor: 3.5,
  npc: 3,
};

/** Node display size bucketed by tier (protagonist largest, npc smallest). */
export function tierNodeValue(node: Pick<CharacterNode, 'tier' | 'role'>) {
  return tierNodeSize[nodeTier(node)];
}

export type InitialPosition = { initialX: number; initialY: number; x: number; y: number };

/**
 * Generic polar layout by tier ring: protagonist at the center, major on the
 * inner ring, supporting mid ring, minor/npc outer ring. Nodes sharing a ring
 * are spread at uniform angles, so any node count is supported.
 */
export function tierRingLayout(nodes: Array<Pick<CharacterNode, 'tier' | 'role'>>): InitialPosition[] {
  const rings = new Map<number, number[]>();
  nodes.forEach((node, index) => {
    const radius = tierRingRadius[nodeTier(node)];
    const members = rings.get(radius) ?? [];
    members.push(index);
    rings.set(radius, members);
  });
  const positions: InitialPosition[] = new Array(nodes.length);
  rings.forEach((members, radius) => {
    members.forEach((nodeIndex, order) => {
      const effectiveRadius = radius === 0 && members.length > 1 ? 56 : radius;
      const angle = (order / members.length) * Math.PI * 2 - Math.PI / 2 + radius * 0.004;
      const x = Math.round(Math.cos(angle) * effectiveRadius);
      const y = Math.round(Math.sin(angle) * effectiveRadius);
      positions[nodeIndex] = { initialX: x, initialY: y, x, y };
    });
  });
  return positions;
}
