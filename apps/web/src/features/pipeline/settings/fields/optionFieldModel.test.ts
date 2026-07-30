import { describe, expect, it } from 'vitest';
import { groupOptionItems, prepareOptionItems, shouldSearchOptions } from './optionFieldModel';

describe('option field model', () => {
  it('deduplicates values and preserves a current value missing from discovery', () => {
    expect(prepareOptionItems([
      { value: 'a', label: 'A' },
      { value: 'a', label: 'A duplicate' },
    ], 'custom-model')).toEqual([
      { value: 'a', label: 'A' },
      { value: 'custom-model', label: 'custom-model', meta: '当前配置' },
    ]);
  });

  it('uses search for long, grouped, or descriptive option sets', () => {
    expect(shouldSearchOptions(Array.from({ length: 8 }, (_, index) => ({ value: `${index}`, label: `${index}` })))).toBe(true);
    expect(shouldSearchOptions([{ value: 'a', label: 'A', group: '官方直连' }])).toBe(true);
    expect(shouldSearchOptions([{ value: 'a', label: 'A', description: '服务描述' }])).toBe(true);
    expect(shouldSearchOptions([{ value: 'a', label: 'A' }])).toBe(false);
  });

  it('keeps source order while collecting named and ungrouped options', () => {
    expect(groupOptionItems([
      { value: 'official', label: 'Official', group: '官方直连' },
      { value: 'custom', label: 'Custom' },
      { value: 'official-2', label: 'Official 2', group: '官方直连' },
    ])).toEqual([
      { value: '官方直连', label: '官方直连', items: [
        { value: 'official', label: 'Official', group: '官方直连' },
        { value: 'official-2', label: 'Official 2', group: '官方直连' },
      ] },
      { value: '其他', label: '其他', items: [{ value: 'custom', label: 'Custom' }] },
    ]);
  });
});
