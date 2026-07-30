import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  activeProjectStorageKey,
  archivedRunLinksStorageKey,
  loadActiveProjectLocally,
  loadArchivedRunLinks,
  projectIdForRun,
  saveActiveProjectLocally,
  saveArchivedRunLink,
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

  it('scopes keys per project and keeps the bare legacy key for the unarchived session', () => {
    setStorageProjectScope('proj-1');
    expect(storageScopedKey('novel-workflow-quality-mode')).toBe('novel-workflow-quality-mode:proj-1');
    setStorageProjectScope('');
    expect(storageScopedKey('novel-workflow-quality-mode')).toBe('novel-workflow-quality-mode');
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

  it('records archived-run links and resolves run ownership through them', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    saveArchivedRunLink('run-legacy', 'proj-1');
    expect(loadArchivedRunLinks()).toEqual({ 'run-legacy': 'proj-1' });
    expect(win.__store.has(archivedRunLinksStorageKey)).toBe(true);

    // Real project id from run.json wins.
    expect(projectIdForRun('proj-7', 'run-x', {})).toBe('proj-7');
    // Legacy run (project_id == run_id) falls back to the archive link.
    expect(projectIdForRun('run-legacy', 'run-legacy', { 'run-legacy': 'proj-1' })).toBe('proj-1');
    // Unknown legacy run stays unarchived ('').
    expect(projectIdForRun('', 'run-unknown', {})).toBe('');
  });
});
