import { useRef, type Dispatch, type MutableRefObject } from 'react';
import type { ProjectRecord, RunControlState, RunEvent, RunInputs, WorkflowDefinition } from '../contracts';
import { getPreferredRunSource, isBackendRunSource, type RunSource } from '../lib/runSource';
import { getProviderReadiness } from '../services/providerApi';
import { buildRunInputs } from './runInputs';
import { resolveRunCommandIntent } from './runCommandIntent';
import type { RunAction, RunState } from './runReducer';
import { selectNextStageId } from './runSelectors';
import type { HydratedRunState } from './runState';
import { clearRunControlLocally } from './storage';
import type { StageDecisionController } from './useStageDecision';
import type { RunHistoryController } from './useRunHistory';
import { isRunAbortError } from './useRunSession';
import type { RunStreamController } from './useRunStreamController';
import type { RunTransitions } from './useRunTransitions';

type CommandRunState = Pick<RunState,
  | 'activeRunId'
  | 'paused'
  | 'runControlState'
  | 'running'
  | 'selectedId'
  | 'workspacePhase'
>;

type RunCommandOptions = {
  dispatchRun: Dispatch<RunAction>;
  eventsRef: MutableRefObject<RunEvent[]>;
  history: RunHistoryController;
  onSettingsRequired: () => void;
  onWarning: (message: string) => void;
  /** Active project context: run inputs carry its id/title (Phase 11.2 mine 4). */
  project: Pick<ProjectRecord, 'id' | 'title'> | null;
  runInputs: RunInputs;
  setRunSource: (source: RunSource) => void;
  stageDecision: StageDecisionController;
  state: CommandRunState;
  stream: RunStreamController;
  transitions: RunTransitions;
  workflow: WorkflowDefinition;
};

export function useRunCommands(options: RunCommandOptions) {
  const {
    dispatchRun,
    eventsRef,
    history,
    onSettingsRequired,
    onWarning,
    project,
    runInputs,
    setRunSource,
    stageDecision,
    state,
    stream,
    transitions,
    workflow,
  } = options;
  const commandEpochRef = useRef(0);
  const startInFlightRef = useRef(false);

  function setRunControl(
    paused: boolean,
    runControlState: RunControlState,
    running: boolean,
  ) {
    dispatchRun({
      type: 'control_changed',
      control: { paused, runControlState, running },
    });
  }

  function clearRunState() {
    commandEpochRef.current += 1;
    clearRunControlLocally();
    eventsRef.current = [];
    dispatchRun({ type: 'run_reset', stageId: 'info' });
    stageDecision.reset();
    transitions.reset();
  }

  function resetRunControl() {
    stream.invalidate();
    clearRunState();
  }

  function settleRunControl(terminal: RunControlState) {
    if (terminal === 'paused') {
      setRunControl(true, 'paused', false);
      stageDecision.syncPausedStream(eventsRef.current);
      return;
    }
    const exportCompleted = eventsRef.current.some(
      (event) => event.type === 'artifact.committed' && event.stage_id === 'export',
    );
    if (terminal === 'completed' && workflow.quality_mode === 'deep' && exportCompleted) {
      markExportCompletedAndStay();
      return;
    }
    setRunControl(false, terminal === 'failed' ? 'failed' : 'completed', false);
  }

  async function consumeExistingRun(inputs: RunInputs, runId: string) {
    const terminal = await stream.consume({
      inputs,
      kind: 'existing',
      runId,
      workflow,
    });
    if (terminal) settleRunControl(terminal);
  }

  async function restoreRecoveredRun(hydrated: HydratedRunState, reconnect: boolean) {
    eventsRef.current = hydrated.events;
    dispatchRun({ type: 'run_restored', hydrated });
    stageDecision.restore(hydrated);
    transitions.setAutomationCockpitReady(hydrated.automationCockpitReady);
    if (!reconnect) return;
    setRunControl(false, 'running', true);
    const source: RunSource = 'backend';
    setRunSource('backend');
    try {
      await consumeExistingRun(
        hydrated.inputs ?? buildRunInputs(workflow, source, project),
        hydrated.activeRunId,
      );
    } catch (error) {
      if (isRunAbortError(error)) return;
      setRunControl(false, 'failed', false);
      onWarning(`真实链路恢复失败：${errorMessage(error)}`);
    }
  }

  async function runWorkflow() {
    const selectedStage = workflow.nodes.find((stage) => stage.id === state.selectedId)
      ?? workflow.nodes[0];
    const intent = resolveRunCommandIntent({
      ...state,
      checkpointContinueReady: stageDecision.state.checkpointContinueReady,
      checkpointStageId: stageDecision.state.checkpointStageId,
      infoContinueReady: stageDecision.state.infoContinueReady,
      qualityMode: workflow.quality_mode,
      selectedStageType: selectedStage.type,
    });
    if (intent.type === 'none') return;
    if (intent.type === 'return_export') {
      returnExportToPlanning();
      return;
    }
    if (intent.type === 'continue') {
      await continueAfterCheckpoint(intent.stageId);
      return;
    }
    if (intent.type === 'observe') {
      await observeActiveRun();
      return;
    }
    if (startInFlightRef.current) return;
    startInFlightRef.current = true;
    try {
      await startNewRun();
    } finally {
      startInFlightRef.current = false;
    }
  }

  async function observeActiveRun() {
    setRunControl(false, 'running', true);
    try {
      await consumeExistingRun(runInputs, state.activeRunId);
    } catch (error) {
      if (isRunAbortError(error)) return;
      setRunControl(false, 'failed', false);
      onWarning(`同步运行状态失败：${errorMessage(error)}`);
    }
  }

  async function startNewRun() {
    const commandEpoch = commandEpochRef.current;
    const source = getPreferredRunSource();
    setRunSource(source);
    if (isBackendRunSource(source)) {
      try {
        const readiness = await getProviderReadiness(workflow.id);
        if (!readiness.ok) {
          onWarning(readiness.message);
          onSettingsRequired();
          return;
        }
      } catch (error) {
        onWarning(`AI 服务状态检查失败：${errorMessage(error)}`);
        onSettingsRequired();
        return;
      }
    }
    if (commandEpochRef.current !== commandEpoch) return;
    onWarning('');
    const runId = `backend-run-${Date.now()}`;
    eventsRef.current = [];
    dispatchRun({ type: 'run_started_locally', runId, stageId: 'info' });
    transitions.reset();
    if (workflow.quality_mode !== 'fast') {
      transitions.navigateToStage('info');
    }
    stageDecision.reset();
    try {
      const terminal = await stream.consume({
        inputs: buildRunInputs(workflow, source, project),
        kind: 'new',
        runId,
        workflow,
      });
      if (!terminal) return;
      settleRunControl(terminal);
      history.record(eventsRef.current, workflow);
    } catch (error) {
      if (isRunAbortError(error)) return;
      clearRunState();
      onWarning(`真实链路启动失败：${errorMessage(error)}`);
    }
  }

  async function continueAfterCheckpoint(stageId: string) {
    const commandEpoch = commandEpochRef.current;
    const resolvedStageId = stageDecision.beginContinuation(stageId, state.selectedId);
    if (resolvedStageId === 'export') {
      returnExportToPlanning();
      return;
    }
    const nextStageId = selectNextStageId(workflow.nodes, resolvedStageId);
    transitions.startSettlement({
      kind: workflow.quality_mode === 'balanced' && resolvedStageId === 'info'
        ? 'balanced_cockpit'
        : 'route',
      nextStageId,
      stageId: resolvedStageId,
    });
    await new Promise((resolve) => window.setTimeout(resolve, 4200));
    if (commandEpochRef.current !== commandEpoch) return;
    setRunControl(false, 'running', true);
    if (stream.isInFlight()) return;
    try {
      await consumeExistingRun(runInputs, state.activeRunId);
    } catch (error) {
      if (isRunAbortError(error)) return;
      setRunControl(false, 'failed', false);
      onWarning(`真实链路继续失败：${errorMessage(error)}`);
    }
  }

  function markExportCompletedAndStay() {
    transitions.clearSettlement();
    stageDecision.markExportReady();
    stream.invalidate();
    if (state.activeRunId) history.record(eventsRef.current, workflow);
    dispatchRun({ type: 'run_export_stayed' });
  }

  function returnExportToPlanning() {
    markExportCompletedAndStay();
    stageDecision.clearCheckpoint();
    dispatchRun({ type: 'run_returned_to_planning', stageId: 'info' });
    transitions.setAutomationCockpitReady(workflow.quality_mode !== 'deep');
  }

  return {
    clearRunState,
    resetRunControl,
    restoreRecoveredRun,
    returnExportToPlanning,
    runWorkflow,
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}
