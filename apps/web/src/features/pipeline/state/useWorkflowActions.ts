import type { Dispatch, MutableRefObject, SetStateAction } from 'react';
import type { CanvasLayout, InspectorTarget, RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { saveCanvasLayoutLocally, saveQualityModeLocally } from './storage';
import { canSwitchMode, hasRecoverableRun } from './runSelectors';
import type { RunState } from './runReducer';
import {
  withAddedModelOption,
  withDeletedKnowledgeDocument,
  withQualityMode,
  withUpdatedCanvasLayout,
  withUpdatedStage,
} from './workflowMutations';
import type { StageDecisionState } from './stageDecisionState';

type Props = {
  clearRunState: () => void;
  decision: StageDecisionState;
  eventsRef: MutableRefObject<RunEvent[]>;
  runState: RunState;
  setSelectedId: (selectedId: string) => void;
  setSelectedInspectorTarget: (target: InspectorTarget) => void;
  setWorkflow: Dispatch<SetStateAction<WorkflowDefinition>>;
};

export function useWorkflowActions({
  clearRunState,
  decision,
  eventsRef,
  runState,
  setSelectedId,
  setSelectedInspectorTarget,
  setWorkflow,
}: Props) {
  function handleStageChange(stage: WorkflowStage) {
    setWorkflow((current) => withUpdatedStage(current, stage));
  }

  function handleLayoutChange(layout: CanvasLayout) {
    saveCanvasLayoutLocally(layout);
    setWorkflow((current) => withUpdatedCanvasLayout(current, layout));
  }

  function handleAddModelOption(providerId: string, model: string) {
    setWorkflow((current) => withAddedModelOption(current, providerId, model));
  }

  function handleKnowledgeDocumentDeleted(docId: string) {
    setWorkflow((current) => withDeletedKnowledgeDocument(current, docId));
  }

  function handleQualityModeChange(mode: WorkflowDefinition['quality_mode']) {
    const canChange = canSwitchMode({
      activeRunId: runState.activeRunId,
      approvalPending: decision.approvalPending,
      checkpointContinueReady: decision.checkpointContinueReady,
      events: eventsRef.current,
      infoContinueReady: decision.infoContinueReady,
      paused: runState.paused,
      runControlState: runState.runControlState,
      running: runState.running,
    });
    if (!canChange) return;
    saveQualityModeLocally(mode);
    const noRecoverableRun = !hasRecoverableRun(
      runState.activeRunId,
      eventsRef.current,
      runState.runControlState,
    );
    if (noRecoverableRun || ['completed', 'failed'].includes(runState.runControlState)) {
      clearRunState();
    }
    setWorkflow((current) => withQualityMode(current, mode));
  }

  function handleCanvasSelect(target: InspectorTarget) {
    setSelectedInspectorTarget(target);
    setSelectedId(target.id);
  }

  return {
    handleAddModelOption,
    handleCanvasSelect,
    handleKnowledgeDocumentDeleted,
    handleLayoutChange,
    handleQualityModeChange,
    handleStageChange,
  };
}
