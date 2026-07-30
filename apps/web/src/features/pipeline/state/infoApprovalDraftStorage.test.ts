import { describe, expect, it } from 'vitest';
import {
  clearInfoApprovalDraft,
  infoApprovalSourceSignature,
  loadInfoApprovalDraft,
  saveInfoApprovalDraft,
  type InfoApprovalDraftStorage,
} from './infoApprovalDraftStorage';

describe('Info approval draft storage', () => {
  it('restores a draft only for the same run and canonical source artifact', () => {
    const storage = memoryStorage();
    const source = '{"title":"原稿","characters":[{"name":"林一"}]}';
    const reorderedSource = '{"characters":[{"name":"林一"}],"title":"原稿"}';
    const draft = '{"title":"人工修改","characters":[{"name":"林一"}]}';

    saveInfoApprovalDraft('run-1', source, draft, storage);

    expect(loadInfoApprovalDraft('run-1', reorderedSource, storage)).toBe(draft);
    expect(loadInfoApprovalDraft('run-2', reorderedSource, storage)).toBe('');
  });

  it('rejects an old draft after the server source changes', () => {
    const storage = memoryStorage();
    saveInfoApprovalDraft('run-1', '{"title":"第一稿"}', '{"title":"人工稿"}', storage);

    expect(loadInfoApprovalDraft('run-1', '{"title":"候选第二稿"}', storage)).toBe('');
    expect(storage.size()).toBe(0);
  });

  it('removes clean and explicitly cleared drafts', () => {
    const storage = memoryStorage();
    const source = '{"title":"原稿"}';
    saveInfoApprovalDraft('run-1', source, '{"title":"人工稿"}', storage);
    expect(storage.size()).toBe(1);

    saveInfoApprovalDraft('run-1', source, '{ "title": "原稿" }', storage);
    expect(storage.size()).toBe(0);

    saveInfoApprovalDraft('run-1', source, '{"title":"第二次修改"}', storage);
    clearInfoApprovalDraft('run-1', storage);
    expect(storage.size()).toBe(0);
  });

  it('uses a stable source signature across object key order', () => {
    expect(infoApprovalSourceSignature('{"a":1,"b":2}'))
      .toBe(infoApprovalSourceSignature('{"b":2,"a":1}'));
  });
});

function memoryStorage(): InfoApprovalDraftStorage & { size: () => number } {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => { values.delete(key); },
    setItem: (key, value) => { values.set(key, value); },
    size: () => values.size,
  };
}
