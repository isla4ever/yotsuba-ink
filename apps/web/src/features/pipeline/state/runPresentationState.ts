import type { QualityMode, RunControlState, StageType } from '../contracts';
import type { StageRunStatus } from './runEventIndex';

export type RunActionKey =
  | 'start'
  | 'running-locked'
  | 'resume'
  | 'awaiting-confirmation'
  | 'continue'
  | 'complete';

export type RunActionPresentation = {
  key: RunActionKey;
  label: string;
  title: string;
  disabled: boolean;
  visualState: 'planning-start' | 'running-locked' | 'danger' | 'awaiting-confirmation' | 'continue-ready';
};

export type ModeRoutePolicy = {
  stageRoutes: 'none' | 'all';
  /**
   * Run monitor console availability per quality mode:
   * fast lands there by default, balanced can toggle in/out,
   * deep never leaves the item-by-item workbench.
   */
  monitor: 'default' | 'available' | 'none';
};

type Params = {
  approvalPending: boolean;
  checkpointContinueReady: boolean;
  briefContinueReady: boolean;
  qualityMode: QualityMode;
  runControlState: RunControlState;
  running: boolean;
  /** Whether the selected stage has reached its checkpoint (F5 summary fact). */
  selectedStageCheckpointReady: boolean;
  selectedStageStatus: StageRunStatus;
  selectedStageType: StageType;
  transitioning: boolean;
  workspacePhase: 'planning' | 'running';
};

export function runActionPresentation(params: Params): RunActionPresentation {
  const runningState = params.running || params.runControlState === 'starting' || params.runControlState === 'running';
  if (params.workspacePhase === 'planning') return startAction(params.qualityMode);
  if (params.transitioning) return lockedAction('正在进入下一阶段');
  if (params.selectedStageStatus === 'attention' && params.selectedStageType === 'cover') {
    return awaitingAction('等待封面资产', '请先生成并选定可用的封面图片资产');
  }
  if (params.selectedStageStatus === 'attention' && params.selectedStageType === 'export') {
    return awaitingAction('等待导出就绪', '请先补齐章节、封面、质量与事实冲突校验');
  }
  if (params.briefContinueReady) return continueAction('继续进入故事脊柱', '显示阶段结算并进入故事脊柱');
  if (params.checkpointContinueReady && params.selectedStageType === 'export') {
    return { key: 'complete', label: '完成本次创作', title: '结束运行并保留导出工作台', disabled: false, visualState: 'continue-ready' };
  }
  if (params.checkpointContinueReady) return continueAction('继续下一阶段', '显示阶段结算并进入下一阶段');
  if (params.qualityMode !== 'fast' && params.approvalPending) {
    return awaitingAction('等待阶段定稿', '请先在当前阶段页面确认定稿');
  }
  if (params.runControlState === 'starting') return lockedAction('正在启动创作');
  if (params.runControlState === 'stop_requested') return lockedAction('运行状态同步中');
  if (params.runControlState === 'paused') {
    return { key: 'resume', label: '同步运行状态', title: '重新连接运行事件', disabled: false, visualState: 'continue-ready' };
  }
  if (runningState) {
    return lockedAction(params.qualityMode === 'fast' ? '极速模式运行中' : '创作运行中');
  }
  return startAction(params.qualityMode);
}

export function modeRoutePolicy(mode: QualityMode): ModeRoutePolicy {
  if (mode === 'fast') return { stageRoutes: 'none', monitor: 'default' };
  if (mode === 'balanced') return { stageRoutes: 'all', monitor: 'available' };
  return { stageRoutes: 'all', monitor: 'none' };
}

export function canNavigateToStage(policy: ModeRoutePolicy, stageId: string) {
  void stageId;
  return policy.stageRoutes === 'all';
}

function startAction(_mode: QualityMode): RunActionPresentation {
  const label = '开始创作';
  return { key: 'start', label, title: label, disabled: false, visualState: 'planning-start' };
}

function lockedAction(label: string): RunActionPresentation {
  return { key: 'running-locked', label, title: label, disabled: true, visualState: 'running-locked' };
}

function awaitingAction(label: string, title: string): RunActionPresentation {
  return { key: 'awaiting-confirmation', label, title, disabled: true, visualState: 'awaiting-confirmation' };
}

function continueAction(label: string, title: string): RunActionPresentation {
  return { key: 'continue', label, title, disabled: false, visualState: 'continue-ready' };
}
