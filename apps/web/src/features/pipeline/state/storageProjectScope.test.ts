import { afterEach, describe, expect, it, vi } from 'vitest';
import { setStorageProjectScope } from './projectScope';
import {
  loadRunControlLocally,
  qualityModeStorageKey,
  runControlStorageKey,
  saveQualityModeLocally,
  saveRunControlLocally,
  workflowWithActiveRunMode,
  type StoredRunControlState,
} from './storage';
import type { RunEvent } from '../contracts';
import { defaultWorkflow } from './defaultWorkflow';
import { buildBookScalePlan } from '../lib/bookScalePlan';

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

  it('round-trips the original run inputs for offline recovery', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    setStorageProjectScope('proj-inputs');
    const state = {
      ...storedRunControl('run-inputs'),
      inputs: {
        project_id: 'proj-inputs',
        title: '恢复角色',
        theme: '旧港',
        quality_mode: 'balanced' as const,
        book_scale_plan: buildBookScalePlan('total_chapters', 3),
        run_intent: {
          project_brief: { narrative_profile: '意象织造者' },
          knowledge_strategy: {},
        },
        export_preferences: { format: 'zip' as const, author: '', version_note: '' },
      },
    };
    saveRunControlLocally(state);
    expect(loadRunControlLocally().inputs?.run_intent?.project_brief.narrative_profile).toBe('意象织造者');
  });

  it('keeps an active run recoverable while the user browses planning', () => {
    const win = memoryWindow();
    vi.stubGlobal('window', win);
    setStorageProjectScope('proj-1');
    const state = { ...storedRunControl('run-1'), workspacePhase: 'planning' as const };
    saveRunControlLocally(state);

    expect(win.__store.has(`${runControlStorageKey}:proj-1`)).toBe(true);
    expect(loadRunControlLocally()).toMatchObject({
      activeRunId: 'run-1',
      selectedId: 'summary',
      workspacePhase: 'planning',
    });
  });

  it('does not infer workflow mode from stored event payloads', () => {
    const state = storedRunControl('run-1');
    expect(workflowWithActiveRunMode(defaultWorkflow, state).quality_mode).toBe(defaultWorkflow.quality_mode);
  });

  it('never reads or writes an unscoped production session', () => {
    const win = memoryWindow({
      [runControlStorageKey]: JSON.stringify(storedRunControl('run-old-unscoped')),
      [qualityModeStorageKey]: 'deep',
    });
    vi.stubGlobal('window', win);
    setStorageProjectScope('');
    expect(loadRunControlLocally().activeRunId).toBe('');
    saveRunControlLocally(storedRunControl('run-new-unscoped'));
    saveQualityModeLocally('fast');
    expect(win.__store.get(runControlStorageKey)).toContain('run-old-unscoped');
    expect(win.__store.get(qualityModeStorageKey)).toBe('deep');

    setStorageProjectScope('proj-1');
    expect(loadRunControlLocally().activeRunId).toBe('');
    saveQualityModeLocally('fast');
    expect(win.__store.get(`${qualityModeStorageKey}:proj-1`)).toBe('fast');
  });
});
