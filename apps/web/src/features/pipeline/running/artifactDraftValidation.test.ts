import { describe, expect, it } from 'vitest';
import {
  draftErrorCount,
  duplicateTrimmedValueIndexes,
  normalizedDraftLines,
  requiredDraftFieldErrors,
} from './artifactDraftValidation';

describe('artifact draft validation', () => {
  it('reports trimmed required fields by stable key', () => {
    const errors = requiredDraftFieldErrors([
      { key: 'title', label: '节拍名称', value: '  ' },
      { key: 'goal', label: '推进目标', value: '保住证据' },
    ]);
    expect(errors).toEqual({ title: '请填写节拍名称' });
    expect(draftErrorCount(errors)).toBe(1);
  });

  it('finds every duplicate non-empty ledger value', () => {
    expect([...duplicateTrimmedValueIndexes(['潮汐表', ' 旧磁带 ', '潮汐表', ''])]).toEqual([0, 2]);
  });

  it('normalizes line-based fields before writeback', () => {
    expect(normalizedDraftLines('  对齐人物身份\n\n  保留物证链  ')).toEqual(['对齐人物身份', '保留物证链']);
  });
});
