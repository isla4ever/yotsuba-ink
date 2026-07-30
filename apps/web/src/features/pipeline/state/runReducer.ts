import type { InspectorTarget, RunControlState, RunEvent } from '../contracts';
import { formatResult } from '../lib/workflow';
import {
  appendRunEvent,
  buildRunEventIndex,
  emptyRunEventIndex,
  RUN_EVENT_LIMIT,
  type RunEventIndex,
} from './runEventIndex';
import type { HydratedRunState } from './runState';
import { selectMemoryEvents } from './runSelectors';

export type WorkspacePhase = 'planning' | 'running';

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
  workspacePhase: WorkspacePhase;
};

type RunControlChange = Partial<Pick<RunState, 'paused' | 'runControlState' | 'running'>>;

export type RunAction =
  | { type: 'control_changed'; control: RunControlChange }
  | { type: 'event_received'; event: RunEvent }
  | { type: 'knowledge_prompt_open_changed'; open: boolean }
  | { type: 'run_export_stayed' }
  | { type: 'run_reset'; stageId: string }
  | { type: 'run_restored'; hydrated: HydratedRunState }
  | { type: 'run_returned_to_planning'; stageId: string }
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
    workspacePhase: params.workspacePhase,
  };
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'control_changed':
      return { ...state, ...action.control };
    case 'event_received':
      return stateForRunEvent(state, action.event);
    case 'knowledge_prompt_open_changed':
      return { ...state, knowledgePromptOpen: action.open };
    case 'run_export_stayed':
      return {
        ...state,
        paused: true,
        runControlState: 'paused',
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
        workspacePhase: 'planning',
      };
    case 'run_restored':
      return {
        ...state,
        activeRunId: action.hydrated.activeRunId,
        events: action.hydrated.events,
        eventIndex: buildRunEventIndex(action.hydrated.events),
        memoryEvents: selectMemoryEvents(action.hydrated.events),
        paused: action.hydrated.paused,
        runControlState: action.hydrated.runControlState,
        running: false,
        selectedId: action.hydrated.selectedId,
        selectedInspectorTarget: stageTarget(action.hydrated.selectedId),
        workspacePhase: 'running',
      };
    case 'run_returned_to_planning':
      return {
        ...state,
        paused: false,
        runControlState: 'completed',
        running: false,
        selectedId: action.stageId,
        selectedInspectorTarget: stageTarget(action.stageId),
        workspacePhase: 'planning',
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
  if (!event.node_id) return '';
  if (event.type === 'node_started' && event.phase !== 'finalizing') return event.node_id;
  if (event.type === 'approval_required' || event.type === 'phase_changed') return event.node_id;
  return '';
}

function stateForRunEvent(state: RunState, event: RunEvent): RunState {
  const stageId = stageIdForRunEventNavigation(event);
  const trimmed = state.events.length >= RUN_EVENT_LIMIT;
  const events = [event, ...state.events].slice(0, RUN_EVENT_LIMIT);
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
    case 'run_started':
      return { ...state, paused: false, runControlState: 'running', running: true };
    case 'run_blocked': {
      const reason = event.reason ?? '当前知识库为空，请先上传资料。';
      return {
        ...state,
        knowledgePrompt: reason,
        knowledgePromptOpen: true,
        latestResult: event.reason ?? '需要先补充知识库资料才能继续。',
      };
    }
    case 'approval_required':
      return { ...state, latestResult: '创作立项已生成，等待你确认定稿。' };
    case 'artifact_approved':
    case 'stage_artifact_confirmed':
      return { ...state, latestResult: `${event.label ?? '阶段产物'}已定稿，流水线继续推进。` };
    case 'brief_regenerated':
      return { ...state, latestResult: '已换一稿创作立项草稿，等待你确认。' };
    case 'draft_candidate_selected':
      return { ...state, latestResult: formatResult(event.artifact ?? event.preview ?? event.message ?? '') };
    case 'run_paused':
      return { ...state, latestResult: '已在安全点暂停，可调整模式后继续。', paused: true, runControlState: 'paused', running: false };
    case 'run_resumed':
      return { ...state, latestResult: '已恢复创作。', paused: false, runControlState: 'running', running: true };
    case 'run_checkpoint_recovery_requested':
      return { ...state, latestResult: '已解锁最后稳定检查点，准备恢复创作。', paused: false, runControlState: 'running', running: true };
    case 'run_recovery_required':
      return { ...state, latestResult: event.message ?? '运行已暂停，请从最后稳定检查点恢复。', paused: true, runControlState: 'paused', running: false };
    case 'stage_checkpoint_ready':
      return { ...state, latestResult: `${event.label ?? event.node_id} 已完成，准备进入下一阶段。` };
    case 'artifact_validation_failed':
      return { ...state, latestResult: `阶段产物结构检查未通过：${event.message ?? event.error ?? '请检查模型输出结构'}` };
    case 'stage_replay_requested':
      return { ...state, latestResult: '当前阶段展示内容已刷新。' };
    case 'quality_check_completed':
      return { ...state, latestResult: qualityResult(event) };
    case 'revision_directive_created':
      return { ...state, latestResult: `已生成局部修订指令：${event.directive?.issue ?? '质量问题待修复'}` };
    case 'manual_intervention_required':
      return { ...state, latestResult: event.reason ?? '发现需要你处理的质量问题，运行已暂停。', paused: true, runControlState: 'paused', running: false };
    // Phase 12 D5: budget warnings no longer write the dead `latestResult`
    // string — the header budget status bar consumes these events directly.
    case 'stage_budget_exceeded':
    case 'run_budget_exceeded':
      return { ...state, paused: true, runControlState: 'paused', running: false };
    case 'chapter_progress_updated':
      return { ...state, latestResult: chapterProgressResult(event) };
    case 'node_completed':
      return { ...state, latestResult: formatResult(event.result) };
    case 'run_error':
    case 'run_failed':
      if (event.recovery_state?.needs_recovery) {
        return { ...state, latestResult: event.message ?? event.error ?? '运行已暂停，请从最后稳定检查点恢复。', paused: true, runControlState: 'paused', running: false };
      }
      return { ...state, latestResult: event.error ?? '运行失败', paused: false, runControlState: 'failed', running: false };
    case 'run_completed':
      return { ...state, latestResult: '流水线已完成。', paused: false, runControlState: 'completed', running: false };
    case 'run_export_ready':
      return { ...state, latestResult: '导出产物已准备好，等待人工下载或返回工作台。', paused: false, runControlState: 'running', running: false };
    case 'node_failed':
      if (event.recovery_state?.needs_recovery) {
        return { ...state, latestResult: event.message ?? event.error ?? '本阶段执行失败，等待从稳定检查点恢复。', paused: true, runControlState: 'paused', running: false };
      }
      return { ...state, latestResult: event.error ?? '本阶段执行失败', runControlState: 'failed' };
    default:
      return state;
  }
}

function isMemoryEvent(event: RunEvent) {
  return event.type === 'memory_context_loaded' || event.type === 'memory_writeback_completed';
}

function stageTarget(stageId: string): InspectorTarget {
  return { kind: 'stage', id: stageId };
}

function qualityResult(event: RunEvent) {
  return event.quality_report
    ? `质量检查完成：Q ${event.quality_report.score.toFixed(2)}，发现 ${event.quality_report.findings.length} 个问题。`
    : formatResult(event.quality ?? event);
}

function chapterProgressResult(event: RunEvent) {
  const completed = event.chapters?.filter((item) => item.status === 'completed').length ?? 0;
  return `正文进度已更新：${completed}/${event.chapters?.length ?? 0} 章`;
}
