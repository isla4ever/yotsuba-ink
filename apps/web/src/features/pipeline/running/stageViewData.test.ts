import { describe, expect, it } from 'vitest';
import {
  activeIndexFor,
  deltasBySection,
  firstText,
  splitLines,
  valueText,
} from './stageViewData';

describe('stage view data', () => {
  it('merges streamed deltas by section in arrival order', () => {
    const deltas = deltasBySection([
      { section: '第一卷', delta: '开端' },
      { section: '第二卷', delta: '转折' },
      { section: '第一卷', delta: '高潮' },
    ]);

    expect(deltas.get('第一卷')).toBe('开端\n高潮');
    expect(deltas.get('第二卷')).toBe('转折');
  });

  it('selects the latest stage item that has streamed content', () => {
    const deltas = new Map([['第二章', '生成中']]);

    expect(activeIndexFor(['第一章', '第二章', '第三章'], deltas)).toBe(1);
    expect(activeIndexFor(['第一章'], new Map())).toBe(0);
  });

  it('formats structured writeback values without exposing raw objects', () => {
    expect(valueText({ character: '沈砚', change: '开始怀疑自己的记忆' }))
      .toBe('沈砚：开始怀疑自己的记忆');
    expect(valueText({ target_chapter: '第 3 章', status: '投放', name: '旧船票', note: '留下水渍' }))
      .toBe('第 3 章 投放 旧船票：留下水渍');
    expect(valueText({ chapter_range: '第 4-5 章', status: '推进', name: '备用电源', note: '卷末确认' }))
      .toBe('第 4-5 章 推进 备用电源：卷末确认');
    const fallback = valueText({ relation: '盟友', pressure: '信任动摇', schema_version: 'internal-v1' });
    expect(fallback).toBe('关系：盟友；关系压力：信任动摇');
    expect(fallback).not.toContain('schema_version');
  });

  it('normalizes list previews and editable lines', () => {
    expect(firstText(['第一条', '第二条'])).toBe('第一条');
    expect(splitLines('第一条\n\n 第二条 ')).toEqual(['第一条', '第二条']);
  });
});
