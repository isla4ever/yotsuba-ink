import { describe, expect, it } from 'vitest';
import { infoWorldbuildingDigest } from './infoWorldbuildingDigest';

describe('info worldbuilding digest', () => {
  it('does not let shorter aliases truncate the named section', () => {
    const digest = infoWorldbuildingDigest([
      '硬规则：记忆改写必须留下声纹痕迹。',
      '地点与空间：故事发生在旧港和潮汐隧道。',
      '组织与势力：档案局与救援队争夺原始录音。',
      '禁忌与风险：公开完整声纹会伤害幸存者。',
    ].join('\n'));

    expect(digest).toEqual([
      { key: 'rules', label: '硬规则', value: '记忆改写必须留下声纹痕迹。' },
      { key: 'places', label: '地点与空间', value: '故事发生在旧港和潮汐隧道。' },
      { key: 'groups', label: '组织与势力', value: '档案局与救援队争夺原始录音。' },
      { key: 'risks', label: '禁忌与风险', value: '公开完整声纹会伤害幸存者。' },
    ]);
  });

  it('supports the shorter fallback labels without inventing content', () => {
    const digest = infoWorldbuildingDigest('规则：证据必须可追溯。\n地点：旧港。');

    expect(digest.map((item) => item.value)).toEqual([
      '证据必须可追溯。',
      '旧港。',
      '待补充',
      '待补充',
    ]);
  });
});
