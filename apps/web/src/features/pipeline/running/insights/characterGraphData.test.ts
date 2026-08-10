import { describe, expect, it } from 'vitest';
import { factionColor, tierNodeValue, tierRingLayout, unaffiliatedColor } from './characterGraphData';

describe('character graph data', () => {
  it('maps a faction name to a stable palette color and unaffiliated nodes to neutral gray', () => {
    expect(factionColor('雾港档案馆')).toBe(factionColor('雾港档案馆'));
    expect(factionColor('雾港档案馆')).toMatch(/^#[0-9a-f]{6}$/);
    expect(factionColor('')).toBe(unaffiliatedColor);
    expect(factionColor('  ')).toBe(unaffiliatedColor);
    expect(factionColor(undefined)).toBe(unaffiliatedColor);
  });

  it('places tiers on concentric rings: protagonist center, major inner, supporting mid, minor/npc outer', () => {
    const positions = tierRingLayout([
      { tier: 'protagonist' },
      { tier: 'major' },
      { tier: 'supporting' },
      { tier: 'minor' },
      { tier: 'npc' },
    ]);
    const radius = (index: number) => Math.hypot(positions[index].initialX, positions[index].initialY);

    expect(radius(0)).toBe(0);
    expect(radius(1)).toBeGreaterThan(0);
    expect(radius(2)).toBeGreaterThan(radius(1));
    expect(radius(3)).toBeGreaterThan(radius(2));
    expect(Math.round(radius(4))).toBe(Math.round(radius(3)));
  });

  it('spreads any node count uniformly within a ring instead of reusing 7 hardcoded points', () => {
    const positions = tierRingLayout(Array.from({ length: 12 }, () => ({ tier: 'supporting' as const })));

    const keys = new Set(positions.map((point) => `${point.initialX},${point.initialY}`));
    expect(keys.size).toBe(12);
    positions.forEach((point) => {
      expect(Math.hypot(point.initialX, point.initialY)).toBeGreaterThan(200);
    });
  });

  it('sizes nodes only from the required tier contract', () => {
    expect(tierNodeValue({ tier: 'protagonist' })).toBeGreaterThan(tierNodeValue({ tier: 'major' }));
    expect(tierNodeValue({ tier: 'major' })).toBeGreaterThan(tierNodeValue({ tier: 'npc' }));
  });
});
