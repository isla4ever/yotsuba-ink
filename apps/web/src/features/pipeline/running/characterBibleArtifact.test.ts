import { describe, expect, it } from 'vitest';
import { characterBibleReadiness, nextCharacterId, parseCharacterBibleArtifact, type CharacterBibleArtifact } from './characterBibleArtifact';

const artifact: CharacterBibleArtifact = {
  characters: [{
    id: 'character-1',
    name: '林默',
    tier: 'protagonist',
    narrative_function: '承担真相调查',
    external_goal: '找到失踪母带',
    inner_need: '承认自己害怕被遗忘',
    arc: { start: '拒绝合作', turning_point: '主动共享证据', end: '接受共同记忆' },
    first_appearance_window: 'chapter:1',
    hard_boundaries: ['不得无证据背叛同伴'],
  }],
  relationships: [],
  npc_slots: [],
};

describe('CharacterBibleArtifact vNext', () => {
  it('accepts the exact vNext contract', () => {
    const parsed = parseCharacterBibleArtifact(JSON.stringify(artifact));
    expect(parsed.errors).toEqual([]);
    expect(parsed.artifact?.characters[0].id).toBe('character-1');
    expect(characterBibleReadiness(parsed.artifact).ready).toBe(true);
  });

  it('rejects old or unknown fields instead of normalizing them', () => {
    const parsed = parseCharacterBibleArtifact(JSON.stringify({ ...artifact, schema_version: 2 }));
    expect(parsed.artifact).toBeNull();
    expect(parsed.errors[0]).toContain('未支持字段');
  });

  it('rejects relationships outside the frozen registry', () => {
    const parsed = parseCharacterBibleArtifact(JSON.stringify({
      ...artifact,
      relationships: [{
        source_id: 'character-1',
        target_id: 'missing',
        nature: '盟友',
        initial_state: '陌生',
        pressure: '互不信任',
      }],
    }));
    expect(parsed.artifact).toBeNull();
    expect(parsed.errors).toContain('关系 1 引用了未登记人物');
  });

  it('rejects an unstructured or reversed first-appearance window', () => {
    const unstructured = structuredClone(artifact);
    unstructured.characters[0].first_appearance_window = '第一卷中段';
    expect(parseCharacterBibleArtifact(JSON.stringify(unstructured)).artifact).toBeNull();

    const reversed = structuredClone(artifact);
    reversed.characters[0].first_appearance_window = 'chapter:8-3';
    expect(parseCharacterBibleArtifact(JSON.stringify(reversed)).artifact).toBeNull();
  });

  it('allocates a stable local id without reusing registry ids', () => {
    expect(nextCharacterId(artifact)).toBe('character-2');
  });
});
