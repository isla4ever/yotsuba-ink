import { describe, expect, it } from 'vitest';
import type { OutlineCharacterProgression, OutlineWorldReveal } from './stageArtifacts';
import { saveCharacterProgression, saveWorldReveal } from './outlineDependencyDrafts';

describe('outline dependency drafts', () => {
  it('replaces an existing character carry in place', () => {
    const first = characterCarry('顾遥', '林澈', '旧压力');
    const second = characterCarry('顾遥', '周既白', '待更新');
    const third = characterCarry('林澈', '周既白', '后续关系');
    const updated = characterCarry('周既白', '顾遥', '新压力');

    const result = saveCharacterProgression([first, second, third], updated);

    expect(result).toEqual([first, updated, third]);
  });

  it('replaces an existing world reveal in place', () => {
    const first = worldReveal('旧港', '旧港档案');
    const second = worldReveal('雾钟', '待更新');
    const third = worldReveal('潮汐塔', '塔顶规则');
    const updated = worldReveal('雾钟', '新的声纹证据');

    const result = saveWorldReveal([first, second, third], updated);

    expect(result).toEqual([first, updated, third]);
  });

  it('appends only when the dependency is new', () => {
    const character = characterCarry('顾遥', '林澈', '原关系');
    const addedCharacter = characterCarry('顾遥', '周既白', '新增关系');
    const world = worldReveal('旧港', '旧港档案');
    const addedWorld = worldReveal('雾钟', '新的声纹证据');

    expect(saveCharacterProgression([character], addedCharacter)).toEqual([character, addedCharacter]);
    expect(saveWorldReveal([world], addedWorld)).toEqual([world, addedWorld]);
  });
});

function characterCarry(character: string, relatedTo: string, pressure: string): OutlineCharacterProgression {
  return {
    change: `${character}改变选择`,
    character,
    impact: '进入下一卷',
    pressure,
    related_to: relatedTo,
    relation: '合作关系',
  };
}

function worldReveal(anchor: string, reveal: string): OutlineWorldReveal {
  return { anchor, impact: '改变后续调查', reveal, rule: '证据不可复制' };
}
