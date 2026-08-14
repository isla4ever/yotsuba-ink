import { describe, expect, it } from 'vitest';
import {
  briefApprovalSourceSignature,
  clearBriefApprovalDraft,
  loadBriefApprovalDraft,
  saveBriefApprovalDraft,
  type BriefApprovalDraftStorage,
} from './briefApprovalDraftStorage';

describe('Brief approval draft storage', () => {
  it('restores a draft only for the same run and canonical source artifact', () => {
    const storage = memoryStorage();
    const source = '{"title":"原稿","characters":[{"name":"林一"}]}';
    const reorderedSource = '{"characters":[{"name":"林一"}],"title":"原稿"}';
    const draft = '{"title":"人工修改","characters":[{"name":"林一"}]}';

    saveBriefApprovalDraft('run-1', source, draft, storage);

    expect(loadBriefApprovalDraft('run-1', reorderedSource, storage)).toBe(draft);
    expect(loadBriefApprovalDraft('run-2', reorderedSource, storage)).toBe('');
  });

  it('rejects an old draft after the server source changes', () => {
    const storage = memoryStorage();
    saveBriefApprovalDraft('run-1', '{"title":"第一稿"}', '{"title":"人工稿"}', storage);

    expect(loadBriefApprovalDraft('run-1', '{"title":"候选第二稿"}', storage)).toBe('');
    expect(storage.size()).toBe(0);
  });

  it('removes clean and explicitly cleared drafts', () => {
    const storage = memoryStorage();
    const source = '{"title":"原稿"}';
    saveBriefApprovalDraft('run-1', source, '{"title":"人工稿"}', storage);
    expect(storage.size()).toBe(1);

    saveBriefApprovalDraft('run-1', source, '{ "title": "原稿" }', storage);
    expect(storage.size()).toBe(0);

    saveBriefApprovalDraft('run-1', source, '{"title":"第二次修改"}', storage);
    clearBriefApprovalDraft('run-1', storage);
    expect(storage.size()).toBe(0);
  });

  it('uses a stable source signature across object key order', () => {
    expect(briefApprovalSourceSignature('{"a":1,"b":2}'))
      .toBe(briefApprovalSourceSignature('{"b":2,"a":1}'));
  });
});

function memoryStorage(): BriefApprovalDraftStorage & { size: () => number } {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => { values.delete(key); },
    setItem: (key, value) => { values.set(key, value); },
    size: () => values.size,
  };
}
