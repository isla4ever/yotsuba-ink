import type { InspectorTarget, RunControlState, RunEvent } from '../contracts';
import { formatResult } from '../lib/workflow';
import {
  appendRunEvent,
  buildRunEventIndex,
  emptyRunEventIndex,
  RUN_EVENT_LIMIT,
  trimRunEventWindow,
  type RunEventIndex,
} from './runEventIndex';
import type { HydratedRunState } from './runState';
import { selectMemoryEvents } from './runSelectors';

export type WorkspacePhase = 'planning' | 'running';

/**
 * Latest artifact event per stage / per text chapter, kept outside the capped
 * event ring: a long run (40 chapters ≈ 1800 events) trims early artifacts out
 * of `events`, and run-wide surfaces like the monitor console must still
 * present the whole book structure. Committed artifacts always win over
 * candidates; entries never expire until the run is reset or replaced.
 */
export type StickyArtifacts = {
  stages: Record<string, RunEvent>;
  chapters: Record<string, RunEvent>;
};

export type RunState = {
  activeRunId: string;
  events: RunEvent[];
  /** Phase 12 F6: incremental per-type/per-stage index over `events`. */
  eventIndex: RunEventIndex;
  knowledgePrompt: string;
  knowledgePromptOpen: boolean;
  latestResult: string;
  memoryEvents: RunEvent[];
  paused: boolean;
  runControlState: RunControlState;
  running: boolean;
  selectedId: string;
  selectedInspectorTarget: InspectorTarget;
  stickyArtifacts: StickyArtifacts;
  workspacePhase: WorkspacePhase;
};

type RunControlChange = Partial<Pick<RunState, 'paused' | 'runControlState' | 'running'>>;

export type RunAction =
  | { type: 'control_changed'; control: RunControlChange }
  | { type: 'event_received'; event: RunEvent }
  | { type: 'knowledge_prompt_open_changed'; open: boolean }
  | { type: 'run_export_completed' }
  | { type: 'run_reset'; stageId: string }
  | { type: 'run_restored'; hydrated: HydratedRunState }
  | { type: 'run_started_locally'; runId: string; stageId: string }
  | { type: 'selected_id_changed'; selectedId: string }
  | { type: 'selected_inspector_changed'; target: InspectorTarget }
  | { type: 'stage_selected'; stageId: string }
  | { type: 'workspace_changed'; workspacePhase: WorkspacePhase };

export function createInitialRunState(params: {
  activeRunId: string;
  events: RunEvent[];
  paused: boolean;
  runControlState: RunControlState;
  selectedId: string;
  stageId: string;
  /** Persisted stage artifact events that outlived the capped event window. */
  stickyStageEvents?: RunEvent[];
  workspacePhase: WorkspacePhase;
}): RunState {
  const selectedId = params.activeRunId ? params.selectedId : params.stageId;
  return {
    activeRunId: params.activeRunId,
    events: params.events,
    eventIndex: buildRunEventIndex(params.events),
    knowledgePrompt: '',
    knowledgePromptOpen: false,
    latestResult: '等待运行',
    memoryEvents: selectMemoryEvents(params.events),
    paused: params.paused,
    runControlState: params.runControlState,
    running: false,
    selectedId,
    selectedInspectorTarget: stageTarget(selectedId),
    stickyArtifacts: stickyArtifactsFromEvents(params.events, params.stickyStageEvents ?? []),
    workspacePhase: params.workspacePhase,
  };
}

export function stickyArtifactsFromEvents(events: RunEvent[], seedEvents: RunEvent[] = []): StickyArtifacts {
  let sticky: StickyArtifacts = { chapters: {}, stages: {} };
  // Seed entries were persisted before older events got evicted, so they apply
  // first; `events` is newest-first, so replay it oldest-first to let newer win.
  for (const event of seedEvents) {
    sticky = stickyArtifactsForEvent(sticky, event);
  }
  for (let index = events.length - 1; index >= 0; index -= 1) {
    sticky = stickyArtifactsForEvent(sticky, events[index]);
  }
  return sticky;
}

function stickyArtifactsForEvent(current: StickyArtifacts, event: RunEvent): StickyArtifacts {
  if (event.type !== 'artifact.committed' && event.type !== 'artifact.candidate_ready') return current;
  if (event.payload == null || !event.stage_id) return current;
  if (event.chapter_id && event.stage_id === 'text') {
    return { ...current, chapters: { ...current.chapters, [event.chapter_id]: event } };
  }
  const existing = current.stages[event.stage_id];
  if (existing?.type === 'artifact.committed' && event.type === 'artifact.candidate_ready') return current;
  return { ...current, stages: { ...current.stages, [event.stage_id]: event } };
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'control_changed':
      return { ...state, ...action.control };
    case 'event_received':
      return stateForRunEvent(state, action.event);
    case 'knowledge_prompt_open_changed':
      return { ...state, knowledgePromptOpen: action.open };
    case 'run_export_completed':
      return {
        ...state,
        paused: false,
        runControlState: 'completed',
        running: false,
        selectedId: 'export',
        selectedInspectorTarget: stageTarget('export'),
        workspacePhase: 'running',
      };
    case 'run_reset':
      return {
        ...state,
        activeRunId: '',
        events: [],
        eventIndex: emptyRunEventIndex(),
        latestResult: '等待运行',
        memoryEvents: [],
        paused: false,
        runControlState: 'idle',
        running: false,
        selectedId: action.stageId,
        selectedInspectorTarget: stageTarget(action.stageId),
        stickyArtifacts: { chapters: {}, stages: {} },
        workspacePhase: 'planning',
      };
    case 'run_restored':
      return {
        ...state,
        activeRunId: action.hydrated.activeRunId,
        events: action.hydrated.events,
        eventIndex: buildRunEventIndex(action.hydrated.events),
        memoryEvents: selectMemoryEvents(action.hydrated.events),
        stickyArtifacts: stickyArtifactsFromEvents(
          action.hydrated.events,
          action.hydrated.stickyStageEvents ?? [],
        ),
        paused: action.hydrated.paused,
        runControlState: action.hydrated.runControlState,
        running: false,
        selectedId: action.hydrated.selectedId,
        selectedInspectorTarget: stageTarget(action.hydrated.selectedId),
        workspacePhase: 'running',
      };
    case 'run_started_locally':
      return {
        ...state,
        activeRunId: action.runId,
        events: [],
        eventIndex: emptyRunEventIndex(),
        latestResult: '创作中...',
        memoryEvents: [],
        paused: false,
        runControlState: 'starting',
        running: true,
        selectedId: action.stageId,
        selectedInspectorTarget: stageTarget(action.stageId),
        stickyArtifacts: { chapters: {}, stages: {} },
        workspacePhase: 'running',
      };
    case 'selected_id_changed':
      return { ...state, selectedId: action.selectedId };
    case 'selected_inspector_changed':
      return { ...state, selectedInspectorTarget: action.target };
    case 'stage_selected':
      return {
        ...state,
        selectedId: action.stageId,
        selectedInspectorTarget: stageTarget(action.stageId),
        workspacePhase: 'running',
      };
    case 'workspace_changed':
      return { ...state, workspacePhase: action.workspacePhase };
  }
}

export function stageIdForRunEventNavigation(event: RunEvent): string {
  if (!event.stage_id) return '';
  if (event.type === 'node.started' || event.type === 'decision.required') return event.stage_id;
  return '';
}

function stateForRunEvent(state: RunState, event: RunEvent): RunState {
  const stageId = stageIdForRunEventNavigation(event);
  const trimmed = state.events.length >= RUN_EVENT_LIMIT;
  // Trimming pins each stage's closing event past the window so events-derived
  // stage projections survive long runs (see trimRunEventWindow).
  const events = trimRunEventWindow([event, ...state.events]);
  let next: RunState = {
    ...state,
    activeRunId: event.run_id || state.activeRunId,
    events,
    // The append path is O(#keys); once the capped list starts dropping events
    // the index is rebuilt from the trimmed list so both stay equivalent.
    eventIndex: trimmed ? buildRunEventIndex(events) : appendRunEvent(state.eventIndex, event),
    memoryEvents: isMemoryEvent(event)
      ? [event, ...state.memoryEvents].slice(0, 40)
      : state.memoryEvents,
    stickyArtifacts: stickyArtifactsForEvent(state.stickyArtifacts, event),
  };
  if (stageId) {
    next = {
      ...next,
      selectedId: stageId,
      selectedInspectorTarget: stageTarget(stageId),
      workspacePhase: 'running',
    };
  }
  return applyEventEffect(next, event);
}

function applyEventEffect(state: RunState, event: RunEvent): RunState {
  switch (event.type) {
    case 'run.started':
      return { ...state, paused: false, runControlState: 'running', running: true };
    case 'decision.required':
      return { ...state, latestResult: '阶段产物等待你的决定。', paused: true, runControlState: 'paused', running: false };
    case 'decision.resolved':
      return { ...state, latestResult: '决定已确认，流水线继续推进。', paused: false, runControlState: 'running', running: true };
    case 'artifact.candidate_ready':
      return { ...state, latestResult: formatResult(event.payload ?? '') };
    case 'artifact.committed':
      return { ...state, latestResult: '阶段产物已正式写回。' };
    case 'checkpoint.saved':
      return { ...state, latestResult: '运行检查点已保存。' };
    case 'review.completed':
      return { ...state, latestResult: '审稿已完成。' };
    case 'review.unavailable':
      return { ...state, latestResult: '审稿角色不可用，等待 Graph 决策。' };
    case 'evidence.proposed':
      return { ...state, latestResult: '正文证据提案已生成。' };
    case 'writeback.queued':
      return { ...state, latestResult: '正式写回已进入事务队列。' };
    case 'writeback.committed':
      return { ...state, latestResult: '正式写回事务已提交。' };
    case 'writeback.failed':
      return { ...state, latestResult: payloadMessage(event) || '正式写回事务失败。' };
    case 'node.completed':
      return state;
    case 'run.failed':
      return { ...state, latestResult: payloadMessage(event) || payloadCode(event) || '运行失败', paused: false, runControlState: 'failed', running: false };
    case 'run.completed':
      return { ...state, latestResult: '流水线已完成。', paused: false, runControlState: 'completed', running: false };
    case 'node.failed':
      return { ...state, latestResult: payloadMessage(event) || payloadCode(event) || '本阶段执行失败', paused: false, runControlState: 'failed', running: false };
    default:
      return state;
  }
}

function payloadMessage(event: RunEvent) {
  const value = event.payload?.message;
  return typeof value === 'string' ? value : '';
}

function payloadCode(event: RunEvent) {
  const value = event.payload?.code;
  return typeof value === 'string' ? value : '';
}

function isMemoryEvent(event: RunEvent) {
  return event.type === 'evidence.proposed' || event.type.startsWith('writeback.');
}

function stageTarget(stageId: string): InspectorTarget {
  return { kind: 'stage', id: stageId };
}
