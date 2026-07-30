import type { QualityMode, RunControlState, StageType } from '../contracts';
import type { WorkspacePhase } from './runReducer';

export type RunCommandIntent =
  | { type: 'continue'; fallbackNextStageId?: string; stageId: string }
  | { type: 'none' }
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'return_export' }
  | { type: 'start' };

export function resolveRunCommandIntent(params: {
  activeRunId: string;
  checkpointContinueReady: boolean;
  checkpointStageId: string;
  infoContinueReady: boolean;
  paused: boolean;
  qualityMode: QualityMode;
  runControlState: RunControlState;
  running: boolean;
  selectedStageType: StageType;
  workspacePhase: WorkspacePhase;
}): RunCommandIntent {
  const activeRun = Boolean(params.activeRunId);
  const runningWorkspace = params.workspacePhase === 'running';
  const fastRunBusy = params.qualityMode === 'fast' && (
    params.running
    || params.runControlState === 'starting'
    || params.runControlState === 'running'
    || params.runControlState === 'stop_requested'
  );
  if (fastRunBusy) return { type: 'none' };

  if (runningWorkspace && params.infoContinueReady && activeRun) {
    return { type: 'continue', stageId: 'info', fallbackNextStageId: 'summary' };
  }

  if (runningWorkspace && params.checkpointContinueReady && activeRun) {
    if (params.selectedStageType === 'export_artifact' || params.checkpointStageId === 'export') {
      return { type: 'return_export' };
    }
    return { type: 'continue', stageId: params.checkpointStageId };
  }

  if (runningWorkspace && params.paused && activeRun) {
    const deepCheckpointBlocked = params.qualityMode === 'deep'
      && Boolean(params.checkpointStageId)
      && !params.checkpointContinueReady;
    return deepCheckpointBlocked ? { type: 'none' } : { type: 'resume' };
  }

  if (runningWorkspace && params.running && activeRun) {
    return params.qualityMode === 'fast' ? { type: 'none' } : { type: 'pause' };
  }

  return { type: 'start' };
}
