import { afterEach, describe, expect, it, vi } from 'vitest';
import { setStorageProjectScope } from './projectScope';
import {
  loadLocalRunHistory,
  loadRunControlLocally,
  qualityModeStorageKey,
  runControlStorageKey,
  saveQualityModeLocally,
  saveRunControlLocally,
  workflowWithActiveRunMode,
  type StoredRunControlState,
} from './storage';
import type { RunEvent, RunHistoryItem } from '../contracts';
import { defaultWorkflow } from './defaultWorkflow';

function memoryWindow(seed: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(seed));
  return {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    },
    __store: store,
  };
}

function storedRunControl(runId: string): StoredRunControlState {
  return {
    activeRunId: runId,
    events: [{ type: 'run_started', run_id: runId } as RunEvent],
    paused: false,
    runSource: 'backend',
    runControlState: 'running',
    selectedId: 'summary',
    workspacePhase: 'running',
  };
}

describe('project-scoped workspace storage (mine 1)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setStorageProjectScope('');
  });

  it('writes run control state under the project-scoped key', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    setStorageProjectScope('proj-1');
    saveRunControlLocally(storedRunControl('run-1'));
    expect(win.__store.has(`${runControlStorageKey}:proj-1`)).toBe(true);
    expect(win.__store.has(runControlStorageKey)).toBe(false);
    expect(loadRunControlLocally().activeRunId).toBe('run-1');
  });

  it('keeps an active run recoverable while the user browses planning', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    const state = { ...storedRunControl('run-1'), workspacePhase: 'planning' as const };
    saveRunControlLocally(state);

    expect(win.__store.has(runControlStorageKey)).toBe(true);
    expect(loadRunControlLocally()).toMatchObject({
      activeRunId: 'run-1',
      selectedId: 'summary',
      workspacePhase: 'planning',
    });
  });

  it('uses the active run mode for the hydration shell before recovery finishes', () => {
    const state = storedRunControl('run-1');
    state.events = [{ type: 'run_started', run_id: 'run-1', quality_mode: 'deep' } as RunEvent];

    expect(workflowWithActiveRunMode(defaultWorkflow, state).quality_mode).toBe('deep');
  });

  it('keeps legacy unscoped data readable as the unarchived session and isolated from projects', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    // Legacy pre-Studio data written under the bare key.
    setStorageProjectScope('');
    saveRunControlLocally(storedRunControl('run-legacy'));
    saveQualityModeLocally('deep');
    expect(win.__store.has(runControlStorageKey)).toBe(true);
    expect(win.__store.get(qualityModeStorageKey)).toBe('deep');

    // A project session neither reads nor clobbers the legacy keys.
    setStorageProjectScope('proj-1');
    expect(loadRunControlLocally().activeRunId).toBe('');
    saveQualityModeLocally('fast');
    expect(win.__store.get(qualityModeStorageKey)).toBe('deep');
    expect(win.__store.get(`${qualityModeStorageKey}:proj-1`)).toBe('fast');

    // Returning to the unarchived scope restores the legacy session unchanged.
    setStorageProjectScope('');
    expect(loadRunControlLocally().activeRunId).toBe('run-legacy');
  });

  it('scopes the local run-history mirror per project', () => {
    const item = { run_id: 'run-1', project_id: 'proj-1' } as RunHistoryItem;
    const win = memoryWindow({
      'novel-workflow-local-run-history:proj-1': JSON.stringify([item]),
      'novel-workflow-local-run-history': JSON.stringify([{ run_id: 'run-legacy', project_id: '' }]),
    });
    vi.stubGlobal('window', win);
    setStorageProjectScope('proj-1');
    expect(loadLocalRunHistory().map((entry) => entry.run_id)).toEqual(['run-1']);
    setStorageProjectScope('');
    expect(loadLocalRunHistory().map((entry) => entry.run_id)).toEqual(['run-legacy']);
  });
});
