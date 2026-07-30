import { describe, expect, it } from 'vitest';
import { splitStreamWords, syncStreamWordVariants, type StreamWordVariant } from './streamWords';

const MIXED = '雾港的旧声在电台里复活。顾遥用React工具修复了母带，She whispered “hold on”，然后……\n\n第二段从这里开始，节奏更快。';

describe('splitStreamWords', () => {
  it('chunks Chinese into 2-4 character word blocks instead of single characters', () => {
    const tokens = splitStreamWords('雾港旧声在电台里复活着');
    expect(tokens.length).toBeGreaterThan(2);
    tokens.slice(0, -1).forEach((token) => {
      expect(token.text.length).toBeGreaterThanOrEqual(2);
      expect(token.text.length).toBeLessThanOrEqual(4);
    });
  });

  it('keeps English words whole and bundles leading whitespace into the next token', () => {
    const tokens = splitStreamWords('Hello brave new world');
    expect(tokens.map((token) => token.text)).toEqual(['Hello', ' brave', ' new', ' world']);
  });

  it('attaches punctuation to the neighbour word block instead of emitting bare punctuation tokens', () => {
    const tokens = splitStreamWords('他停了下来。她说：“没有。”');
    expect(tokens.every((token) => /[^\s，。！？；：、“”]/.test(token.text))).toBe(true);
    expect(tokens.some((token) => token.text.endsWith('。'))).toBe(true);
  });

  it('reassembles losslessly, preserving whitespace and paragraph breaks', () => {
    const tokens = splitStreamWords(MIXED);
    expect(tokens.map((token) => token.text).join('')).toBe(MIXED);
    expect(tokens.some((token) => token.text.includes('\n\n'))).toBe(true);
  });

  it('keeps revealed token keys stable while the stream grows, so mounted spans never replay', () => {
    const full = splitStreamWords(MIXED);
    for (let cut = 1; cut <= MIXED.length; cut += 1) {
      const prefix = splitStreamWords(MIXED.slice(0, cut));
      prefix.forEach((token, index) => {
        expect(full[index].key).toBe(token.key);
        expect(full[index].text.startsWith(token.text)).toBe(true);
      });
    }
  });
});

describe('syncStreamWordVariants', () => {
  it('freezes the entry variant per word and assigns the current gear only to new words', () => {
    const variants = new Map<number, StreamWordVariant>();
    const first = splitStreamWords('雾港旧声');
    syncStreamWordVariants(variants, first, 'fade');
    const grown = splitStreamWords('雾港旧声在电台里复活。');
    syncStreamWordVariants(variants, grown, 'blur');
    expect(variants.get(first[0].key)).toBe('fade');
    grown
      .filter((token) => !first.some((prev) => prev.key === token.key))
      .forEach((token) => expect(variants.get(token.key)).toBe('blur'));
  });

  it('prunes keys that disappear after a stream reset', () => {
    const variants = new Map<number, StreamWordVariant>();
    syncStreamWordVariants(variants, splitStreamWords('雾港旧声'), 'fade');
    syncStreamWordVariants(variants, [], 'fade');
    expect(variants.size).toBe(0);
  });
});
