import { describe, expect, it } from 'vitest';
import {
  appendDetailDraftRow,
  createDetailDraftRows,
  detailDraftValues,
  removeDetailDraftRow,
  updateDetailDraftRow,
} from './detailWritebackRows';

describe('detail writeback draft rows', () => {
  it('creates deterministic unique ids for duplicate artifact rows', () => {
    const value = { anchor: '雾钟', fact: '母带存在', impact: '获得物证' };
    const first = createDetailDraftRows('fact', [value, value]);
    const second = createDetailDraftRows('fact', [value, value]);
    expect(first.map((row) => row.id)).toEqual(second.map((row) => row.id));
    expect(new Set(first.map((row) => row.id)).size).toBe(2);
  });

  it('keeps surviving row ids stable through edits, deletion, and insertion', () => {
    const initial = createDetailDraftRows('wiki', [
      { title: '母带', fact: '保存证词', source_anchor: '雾钟' },
      { title: '签章', fact: '确认来源', source_anchor: '旧港' },
    ]);
    const survivingId = initial[1].id;
    const updated = updateDetailDraftRow(initial, initial[0].id, { ...initial[0].value, fact: '保存十年前证词' });
    const removed = removeDetailDraftRow(updated, initial[0].id);
    const appended = appendDetailDraftRow(removed, 'wiki', { title: '', fact: '', source_anchor: '' });
    expect(appended[0].id).toBe(survivingId);
    expect(appended[1].id).not.toBe(survivingId);
  });

  it('strips local ids when converting rows back to the artifact contract', () => {
    const rows = createDetailDraftRows('clue', [{ name: '父亲签章', status: '投放' as const, note: '保留疑问' }]);
    expect(detailDraftValues(rows)).toEqual([{ name: '父亲签章', status: '投放', note: '保留疑问' }]);
    expect(detailDraftValues(rows)[0]).not.toHaveProperty('id');
  });
});
