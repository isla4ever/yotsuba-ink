import type { CanvasLayout, RunControlState, RunEvent, RunHistoryItem, WorkflowDefinition } from '../contracts';
import type { RunSource } from '../lib/runSource';
import { applyQualityMode } from '../lib/workflow';
import { storageScopedKey } from './projectScope';

/**
 * Base storage keys. All four are project-scoped via storageScopedKey():
 * the active project appends `:{projectId}`, while the empty scope keeps the
 * legacy unscoped key alive as the "unarchived" session (Phase 11.2 mine 1).
 */
export const canvasLayoutStorageKey = 'novel-workflow-canvas-layout';
export const qualityModeStorageKey = 'novel-workflow-quality-mode';
export const localRunHistoryStorageKey = 'novel-workflow-local-run-history';
export const runControlStorageKey = 'novel-workflow-run-control-state';

export type StoredRunControlState = {
  activeRunId: string;
  events?: RunEvent[];
  paused: boolean;
  runSource?: RunSource;
  runControlState: RunControlState;
  selectedId: string;
  workspacePhase: 'planning' | 'running';
};

export function workflowWithStoredPreferences(workflow: WorkflowDefinition): WorkflowDefinition {
  return workflowWithStoredQualityMode(workflowWithStoredCanvasLayout(workflow));
}

export function workflowWithActiveRunMode(
  workflow: WorkflowDefinition,
  storedRun: StoredRunControlState,
): WorkflowDefinition {
  const mode = storedRun.events?.find((event) => (
    event.quality_mode === 'fast' || event.quality_mode === 'balanced' || event.quality_mode === 'deep'
  ))?.quality_mode;
  return mode ? applyQualityMode(workflow, mode) : workflow;
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
    const shouldResetViewport = isLegacyViewport(canvas_layout.viewport);
    return {
      ...workflow,
      canvas_layout: {
        ...workflow.canvas_layout,
        ...canvas_layout,
        nodes: normalizeStoredCanvasNodes(workflow, canvas_layout.nodes),
        viewport: shouldResetViewport ? workflow.canvas_layout?.viewport : canvas_layout.viewport,
      },
    };
  } catch {
    return workflow;
  }
}

function normalizeStoredCanvasNodes(workflow: WorkflowDefinition, nodes: CanvasLayout['nodes']) {
  if (isLegacyStageLayout(nodes)) return { ...defaultCanvasNodes() };
  const next = { ...(workflow.canvas_layout?.nodes ?? {}), ...nodes };
  if (
    !nodes['wiki-layer']
    || isNear(nodes['wiki-layer'].x, 70)
    || isNear(nodes['wiki-layer'].x, 300)
    || isNear(nodes['wiki-layer'].x, 276)
    || isNear(nodes['wiki-layer'].x, 184)
    || isNear(nodes['wiki-layer'].x, 324)
    || isNear(nodes['wiki-layer'].y, 56)
    || isNear(nodes['wiki-layer'].y, -20)
    || isNear(nodes['wiki-layer'].x, 408)
  ) {
    next['wiki-layer'] = workflow.canvas_layout?.nodes?.['wiki-layer'] ?? { x: 324, y: -96 };
  }
  if (
    !nodes['quality-layer']
    || isNear(nodes['quality-layer'].x, 760)
    || isNear(nodes['quality-layer'].x, 694)
    || isNear(nodes['quality-layer'].x, 676)
    || isNear(nodes['quality-layer'].x, 484)
    || isNear(nodes['quality-layer'].x, 480)
    || isNear(nodes['quality-layer'].x, 616)
    || isNear(nodes['quality-layer'].y, 282)
    || isNear(nodes['quality-layer'].y, 374)
    || isNear(nodes['quality-layer'].x, 602)
  ) {
    next['quality-layer'] = workflow.canvas_layout?.nodes?.['quality-layer'] ?? { x: 708, y: 452 };
  }
  return next;
}

function isNear(value: number, target: number) {
  return Math.abs(value - target) <= 4;
}

function isLegacyStageLayout(nodes: CanvasLayout['nodes']) {
  const info = nodes.info;
  const summary = nodes.summary;
  const exportStage = nodes.export;
  return Boolean(
    info && summary && (
      isNear(info.x, 266)
      || isNear(summary.x, 266)
      || isNear(summary.y, 160)
      || isNear(exportStage?.y ?? 0, 860)
    ),
  );
}

function isLegacyViewport(viewport?: CanvasLayout['viewport']) {
  if (!viewport) return false;
  return (
    (isNear(viewport.x, -10) && isNear(viewport.y, 18))
    || (isNear(viewport.x, 34) && isNear(viewport.y, -8))
    || isNear(viewport.x, 24)
    || isNear(viewport.y, 8)
  );
}

function defaultCanvasNodes() {
  return {
    info: { x: -12, y: 178 },
    summary: { x: 214, y: 178 },
    outline: { x: 440, y: 178 },
    detail: { x: 666, y: 178 },
    text: { x: 892, y: 178 },
    cover: { x: 1118, y: 178 },
    export: { x: 1344, y: 178 },
    'wiki-layer': { x: 324, y: -96 },
    'quality-layer': { x: 708, y: 452 },
  };
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
      paused: state === 'paused' || Boolean(parsed.paused),
      runSource: 'backend',
      runControlState: state,
      selectedId: typeof parsed.selectedId === 'string' && parsed.selectedId.trim() ? parsed.selectedId : 'info',
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
    selectedId: 'info',
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

export function loadLocalRunHistory(): RunHistoryItem[] {
  try {
    const stored = window.localStorage.getItem(storageScopedKey(localRunHistoryStorageKey));
    const parsed = stored ? JSON.parse(stored) : null;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is RunHistoryItem => {
        if (!item || typeof item !== 'object') return false;
        const record = item as Record<string, unknown>;
        return Boolean(record.run_id && !String(record.id || '').startsWith('local-history-'));
      })
      .map((item) => ({ ...item, source: 'local' as const }));
  } catch {
    return [];
  }
}

export function saveLocalRunHistory(items: RunHistoryItem[]) {
  try {
    window.localStorage.setItem(storageScopedKey(localRunHistoryStorageKey), JSON.stringify(items.slice(0, 24)));
  } catch {
    // Local history is a UI preview affordance; failure should not block creation.
  }
}

export function historyItemFromEvents(events: RunEvent[], workflow: WorkflowDefinition): RunHistoryItem | null {
  if (!events.some((event) => event.type === 'run_started')) return null;
  const latestStage = events.find((event) => event.node_id)?.node_id ?? workflow.nodes[0]?.id ?? 'info';
  const latestStageEvent = events.find((event) => event.node_id);
  const usageByScope = new Map<string, RunEvent>();
  for (const event of events.filter((item) => item.type === 'stage_usage_finalized' || item.type === 'stage_usage_updated')) {
    const key = `${event.node_id ?? ''}:${event.chapter ?? ''}`;
    if (!usageByScope.has(key)) usageByScope.set(key, event);
  }
  const tokens = [...usageByScope.values()].reduce((sum, event) => sum + Number(event.usage?.estimated_input_tokens ?? 0) + Number(event.usage?.estimated_output_tokens ?? 0), 0);
  const cost = [...usageByScope.values()].reduce((sum, event) => sum + Number(event.usage?.estimated_cost_usd ?? 0), 0);
  const chapters = new Map<string, number>();
  for (const chapter of events.flatMap((event) => event.chapters ?? [])) chapters.set(chapter.chapter, Number(chapter.words ?? 0));
  const words = [...chapters.values()].reduce((sum, value) => sum + value, 0);
  const status = events.some((event) => event.type === 'run_completed')
    ? 'completed'
    : events.some((event) => event.type === 'run_recovery_required')
      ? 'recovery_required'
      : events.some((event) => event.type === 'run_failed' || event.type === 'run_error')
        ? 'failed'
        : events.some((event) => event.type === 'approval_required' || event.type === 'stage_checkpoint_ready')
          ? 'awaiting_confirmation'
          : 'running';
  const projectId = String(events.find((event) => event.state?.project_id)?.state?.project_id ?? '');
  return {
    run_id: events.find((event) => event.run_id)?.run_id ?? `local-${Date.now()}`,
    project_id: projectId,
    title: workflow.global_inputs.find((item) => item.key === 'title')?.default?.toString() || workflow.name,
    quality_mode: latestStageEvent?.quality_mode === 'fast' || latestStageEvent?.quality_mode === 'deep' ? latestStageEvent.quality_mode : 'balanced',
    status,
    current_stage: {
      id: latestStage,
      label: latestStageEvent?.label ?? workflow.nodes.find((node) => node.id === latestStage)?.label ?? '配置准备',
      type: latestStageEvent?.node_type ?? '',
    },
    completed_stage_ids: events.filter((event) => event.type === 'node_completed' && event.node_id).map((event) => event.node_id as string),
    created_at: events.find((event) => event.type === 'run_started')?.created_at ?? new Date().toISOString(),
    updated_at: new Date().toISOString(),
    completed_at: events.find((event) => event.type === 'run_completed')?.created_at ?? '',
    words,
    total_tokens: tokens,
    estimated_cost_usd: cost,
    summary: events.find((event) => event.type === 'stage_summary_ready')?.message ?? '本轮创作记录可用于回溯配置、阶段产物与运行成本。',
    can_resume: status !== 'completed' && status !== 'failed',
    recovery_required: status === 'recovery_required',
    latest_snapshot_id: '',
    export_ready: events.some((event) => event.type === 'run_export_ready' || event.node_id === 'export'),
    export_count: 0,
    latest_export: null,
    state_revision: 0,
    source: 'local',
  };
}
