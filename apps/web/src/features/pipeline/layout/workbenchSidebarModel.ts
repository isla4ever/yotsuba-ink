import type { StageRuntimeSummaryMap } from '../state/pipelineShellContext';
import type { StageRunStatus } from '../state/runEventIndex';
import { canNavigateToStage, type ModeRoutePolicy } from '../state/runPresentationState';
import type { QualityMode, WorkflowStage } from '../contracts';
import { creationModeTitle } from '../lib/terminology';

export type SidebarStageItem = {
  id: string;
  label: string;
  status: StageRunStatus;
  statusLabel: string;
  disabled: boolean;
  disabledReason: string;
};

export const sidebarExpandedStorageKey = 'novel-workflow-sidebar-expanded';

export type SidebarPreferenceStorage = Pick<Storage, 'getItem' | 'setItem'>;

const statusLabels: Record<StageRunStatus, string> = {
  idle: '未开始',
  running: '进行中',
  awaiting: '待决策',
  done: '已完成',
  attention: '待完善',
  failed: '失败',
};

export function defaultSidebarExpanded(wideViewport: boolean) {
  return wideViewport;
}

export function hasSidebarPreference(storage: SidebarPreferenceStorage | null = browserStorage()) {
  try {
    const stored = storage?.getItem(sidebarExpandedStorageKey);
    return stored === 'expanded' || stored === 'collapsed';
  } catch {
    return false;
  }
}

export function loadSidebarExpanded(fallback: boolean, storage: SidebarPreferenceStorage | null = browserStorage()) {
  try {
    const stored = storage?.getItem(sidebarExpandedStorageKey);
    if (stored === 'expanded') return true;
    if (stored === 'collapsed') return false;
    return fallback;
  } catch {
    return fallback;
  }
}

export function saveSidebarExpanded(expanded: boolean, storage: SidebarPreferenceStorage | null = browserStorage()) {
  try {
    storage?.setItem(sidebarExpandedStorageKey, expanded ? 'expanded' : 'collapsed');
  } catch {
    // The sidebar keeps working in-memory when local storage is unavailable.
  }
}

export function sidebarStageItems(input: {
  stages: Array<Pick<WorkflowStage, 'id' | 'label'>>;
  /** Phase 12 F5: low-frequency per-stage runtime summary from the shell slice. */
  stageRuntimes: StageRuntimeSummaryMap;
  policy: ModeRoutePolicy;
  qualityMode: QualityMode;
  runHasStarted: boolean;
}): SidebarStageItem[] {
  return input.stages.map((stage) => {
    const status = input.stageRuntimes[stage.id]?.status ?? 'idle';
    const disabledReason = stageDisabledReason(stage.id, input.policy, input.qualityMode, input.runHasStarted);
    return {
      id: stage.id,
      label: stage.label,
      status,
      statusLabel: statusLabels[status],
      disabled: Boolean(disabledReason),
      disabledReason,
    };
  });
}

function stageDisabledReason(stageId: string, policy: ModeRoutePolicy, qualityMode: QualityMode, runHasStarted: boolean) {
  if (!canNavigateToStage(policy, stageId)) {
    return qualityMode === 'fast' ? `${creationModeTitle('fast')}模式下阶段进度在驾驶舱内查看` : '当前模式下阶段进度在驾驶舱内查看';
  }
  if (!runHasStarted) return '启动创作后可进入阶段工作台';
  return '';
}

function browserStorage(): SidebarPreferenceStorage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}
