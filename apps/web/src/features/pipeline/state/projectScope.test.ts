import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  activeProjectStorageKey,
  loadActiveProjectLocally,
  saveActiveProjectLocally,
  setStorageProjectScope,
  storageScopedKey,
} from './projectScope';
import type { ProjectRecord } from '../contracts';

function memoryWindow() {
  const store = new Map<string, string>();
  return {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    },
    __store: store,
  };
}

const project: ProjectRecord = {
  id: 'proj-1',
  title: '雾城异闻',
  summary: '',
  accent_hue: 262,
  workflow_id: 'wf-proj-1',
  status: 'active',
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-02T00:00:00Z',
  latest_run_id: 'run-9',
};

describe('project storage scope (mine 1)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setStorageProjectScope('');
  });

  it('requires a project id for every scoped storage key', () => {
    setStorageProjectScope('proj-1');
    expect(storageScopedKey('novel-workflow-quality-mode')).toBe('novel-workflow-quality-mode:proj-1');
    setStorageProjectScope('');
    expect(() => storageScopedKey('novel-workflow-quality-mode')).toThrow('active project');
    // Explicit override wins over the module scope (used by tests and callers with a project at hand).
    expect(storageScopedKey('k', 'proj-2')).toBe('k:proj-2');
  });

  it('persists and restores the active project record', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    saveActiveProjectLocally(project);
    expect(win.__store.has(activeProjectStorageKey)).toBe(true);
    expect(loadActiveProjectLocally()).toEqual(project);
    saveActiveProjectLocally(null);
    expect(loadActiveProjectLocally()).toBeNull();
  });
});
