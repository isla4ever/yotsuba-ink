import type { CanvasLayout, RunControlState, RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
import type { RunSource } from '../lib/runSource';
import { applyQualityMode } from '../lib/workflow';
import { storageScopedKey } from './projectScope';
import { isRunInputs } from './runInputSnapshot';

/** Base storage keys. Reads and writes require an explicit active project scope. */
export const canvasLayoutStorageKey = 'novel-workflow-canvas-layout';
export const qualityModeStorageKey = 'novel-workflow-quality-mode';
export const runControlStorageKey = 'novel-workflow-run-control-state';

export type StoredRunControlState = {
  activeRunId: string;
  events?: RunEvent[];
  /** Original run inputs used to keep offline recovery configuration truthful. */
  inputs?: RunInputs;
  paused: boolean;
  runSource?: RunSource;
  runControlState: RunControlState;
  selectedId: string;
  /**
   * Latest committed/candidate artifact event per stage, kept alongside the
   * capped event window so long runs (40 chapters ≈ 1800 events vs the 500-event
   * cap) still recover the early-stage artifacts after a reload. Chapter bodies
   * are deliberately not persisted: they dominate payload size and remain
   * recoverable from run history / export.
   */
  stickyStageEvents?: RunEvent[];
  workspacePhase: 'planning' | 'running';
};

export function workflowWithStoredPreferences(workflow: WorkflowDefinition): WorkflowDefinition {
  return workflowWithStoredQualityMode(workflowWithStoredCanvasLayout(workflow));
}

export function workflowWithActiveRunMode(
  workflow: WorkflowDefinition,
  storedRun: StoredRunControlState,
): WorkflowDefinition {
  void storedRun;
  return workflow;
}

export function workflowWithStoredQualityMode(workflow: WorkflowDefinition): WorkflowDefinition {
  try {
    const stored = window.localStorage.getItem(storageScopedKey(qualityModeStorageKey));
    if (stored !== 'fast' && stored !== 'balanced' && stored !== 'deep') return workflow;
    return applyQualityMode(workflow, stored);
  } catch {
    return workflow;
  }
}

export function workflowWithStoredCanvasLayout(workflow: WorkflowDefinition): WorkflowDefinition {
  try {
    const stored = window.localStorage.getItem(storageScopedKey(canvasLayoutStorageKey));
    if (!stored) return workflow;
    const canvas_layout = JSON.parse(stored) as CanvasLayout;
    if (!canvas_layout || typeof canvas_layout !== 'object' || !canvas_layout.nodes) return workflow;
    if (!isCurrentCanvasLayout(workflow, canvas_layout)) return workflow;
    return {
      ...workflow,
      canvas_layout: {
        ...canvas_layout,
        nodes: { ...canvas_layout.nodes },
      },
    };
  } catch {
    return workflow;
  }
}

function isCurrentCanvasLayout(workflow: WorkflowDefinition, layout: CanvasLayout) {
  const requiredNodeIds = [
    ...workflow.nodes.map((stage) => stage.id),
    'wiki-layer',
    'quality-layer',
  ];
  return requiredNodeIds.every((id) => {
    const node = layout.nodes[id];
    return node && Number.isFinite(node.x) && Number.isFinite(node.y);
  });
}

export function saveCanvasLayoutLocally(layout: CanvasLayout) {
  try {
    window.localStorage.setItem(storageScopedKey(canvasLayoutStorageKey), JSON.stringify(layout));
  } catch {
    // Ignore local storage failures; backend autosave still receives the layout.
  }
}

export function saveQualityModeLocally(mode: WorkflowDefinition['quality_mode']) {
  try {
    window.localStorage.setItem(storageScopedKey(qualityModeStorageKey), mode);
  } catch {
    // Ignore local storage failures; workflow autosave still receives the mode.
  }
}

export function loadRunControlLocally(): StoredRunControlState {
  try {
    const stored = window.localStorage.getItem(storageScopedKey(runControlStorageKey));
    const parsed = stored ? JSON.parse(stored) as Partial<StoredRunControlState> : null;
    if (!parsed || (parsed.workspacePhase !== 'running' && parsed.workspacePhase !== 'planning')) return defaultRunControlState();
    if (typeof parsed.activeRunId !== 'string' || !parsed.activeRunId.trim()) return defaultRunControlState();
    const state = normalizeRunControlState(parsed.runControlState);
    const events = Array.isArray(parsed.events) ? parsed.events : [];
    if (!events.length) return defaultRunControlState();
    return {
      activeRunId: parsed.activeRunId,
      events,
      inputs: isRunInputs(parsed.inputs) ? parsed.inputs : undefined,
      paused: state === 'paused' || Boolean(parsed.paused),
      runSource: 'backend',
      runControlState: state,
      selectedId: typeof parsed.selectedId === 'string' && parsed.selectedId.trim() ? parsed.selectedId : 'brief',
      stickyStageEvents: Array.isArray(parsed.stickyStageEvents) ? parsed.stickyStageEvents : undefined,
      workspacePhase: parsed.workspacePhase,
    };
  } catch {
    return defaultRunControlState();
  }
}

export function saveRunControlLocally(state: StoredRunControlState) {
  try {
    if (!state.activeRunId) {
      window.localStorage.removeItem(storageScopedKey(runControlStorageKey));
      return;
    }
    window.localStorage.setItem(storageScopedKey(runControlStorageKey), JSON.stringify({
      ...state,
      events: state.events ? [...state.events].reverse().slice(-500) : undefined,
    }));
  } catch {
    // The URL still reflects the current surface when local storage is unavailable.
  }
}

export function clearRunControlLocally() {
  try {
    window.localStorage.removeItem(storageScopedKey(runControlStorageKey));
  } catch {
    // Ignore local storage failures; UI state will still reset in memory.
  }
}

function defaultRunControlState(): StoredRunControlState {
  return {
    activeRunId: '',
    events: [],
    paused: false,
    runSource: 'backend',
    runControlState: 'idle',
    selectedId: 'brief',
    workspacePhase: 'planning',
  };
}

function normalizeRunControlState(state?: RunControlState): RunControlState {
  if (state === 'starting' || state === 'running' || state === 'stop_requested' || state === 'paused' || state === 'completed' || state === 'failed') return state;
  return 'idle';
}

export function hasOnlineTextProvider(workflow: WorkflowDefinition) {
  return workflow.provider_profiles.some((provider) => {
    if (!provider.enabled) return false;
    return provider.kind === 'openai-compatible' && provider.base_url.trim() && (provider.api_key_env.trim() || provider.has_saved_secret);
  });
}
