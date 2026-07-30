import { useState, type MutableRefObject } from 'react';
import type { RunControlState, RunEvent, WorkflowDefinition } from '../contracts';
import { isBackendRunSource, type RunSource } from '../lib/runSource';
import { approveRunArtifact } from '../services/runApi';
import type { HydratedRunState } from './runState';
import {
  parseApprovalArtifact,
  selectCheckpointStageId,
  selectLatestStageArtifact,
} from './runSelectors';
import {
  continuationStartedState,
  decisionStateForPausedStream,
  exportReadyState,
  infoApprovedState,
  initialStageDecisionState,
  restoreStageDecisionState,
  stageDecisionStateForEvent,
  stageConfirmedState,
} from './stageDecisionState';
import { useStageCandidates } from './useStageCandidates';
import {
  clearInfoApprovalDraft,
  loadInfoApprovalDraft,
  saveInfoApprovalDraft,
} from './infoApprovalDraftStorage';

type StageDecisionOptions = {
  activeRunId: string;
  emitEvent: (event: RunEvent) => void;
  eventsRef: MutableRefObject<RunEvent[]>;
  onWarning: (message: string) => void;
  runSource: RunSource;
  setRunControl: (control: {
    paused: boolean;
    runControlState: RunControlState;
    running: boolean;
  }) => void;
  workflow: WorkflowDefinition;
};

export function useStageDecision({
  activeRunId,
  emitEvent,
  eventsRef,
  onWarning,
  runSource,
  setRunControl,
  workflow,
}: StageDecisionOptions) {
  const [state, setState] = useState(initialStageDecisionState);
  const candidates = useStageCandidates({
    activeRunId,
    emitEvent,
    eventsRef,
    onWarning,
    workflow,
  });

  function setApprovalDraft(approvalDraft: string) {
    if (state.approvalPending && state.approvalSource) {
      saveInfoApprovalDraft(activeRunId, state.approvalSource, approvalDraft);
    }
    setState((current) => ({ ...current, approvalDraft }));
  }

  function restore(hydrated: HydratedRunState) {
    const restored = restoreStageDecisionState(hydrated);
    const localDraft = restored.approvalPending
      ? loadInfoApprovalDraft(hydrated.activeRunId, restored.approvalSource)
      : '';
    setState({ ...restored, approvalDraft: localDraft || restored.approvalDraft });
  }

  function reset() {
    clearInfoApprovalDraft(activeRunId);
    candidates.resetCandidates();
    setState(initialStageDecisionState);
  }

  function syncPausedStream(events: RunEvent[]) {
    setState((current) => decisionStateForPausedStream(current, events));
  }

  function applyEvent(event: RunEvent) {
    if (event.type === 'artifact_approved' && event.node_id === 'info') {
      clearInfoApprovalDraft(event.run_id || activeRunId);
    }
    setState((current) => {
      const next = stageDecisionStateForEvent(current, event);
      if (!isInfoSourceEvent(event) || !next.approvalPending || !next.approvalSource) return next;
      if (next.approvalSource === current.approvalSource && current.approvalDraft) {
        return { ...next, approvalDraft: current.approvalDraft };
      }
      const localDraft = loadInfoApprovalDraft(event.run_id || activeRunId, next.approvalSource);
      return localDraft ? { ...next, approvalDraft: localDraft } : next;
    });
  }

  function beginContinuation(stageId: string, selectedStageId: string) {
    const resolvedStageId = selectCheckpointStageId(
      stageId,
      eventsRef.current,
      workflow.nodes,
      selectedStageId,
    );
    if (resolvedStageId !== 'export') {
      setState((current) => continuationStartedState(current));
    }
    return resolvedStageId;
  }

  function markExportReady() {
    candidates.resetCandidates();
    setState((current) => exportReadyState(current));
  }

  function clearCheckpoint() {
    setState((current) => continuationStartedState(current));
  }

  async function approveBrief(artifact: string) {
    if (!activeRunId) return false;
    const parsedArtifact = parseApprovalArtifact(artifact);
    if (isBackendRunSource(runSource)) {
      try {
        await approveRunArtifact(activeRunId, 'info', 'info_recommend', parsedArtifact);
      } catch (error) {
        onWarning(`信息推荐定稿提交失败：${errorMessage(error)}`);
        return false;
      }
    }
    clearInfoApprovalDraft(activeRunId);
    setState((current) => infoApprovedState({
      ...current,
      approvalDraft: artifact,
      approvalSource: artifact,
    }));
    setRunControl({ paused: true, runControlState: 'paused', running: false });
    if (!isBackendRunSource(runSource)) {
      emitEvent({
        type: 'artifact_approved',
        run_id: activeRunId,
        node_id: 'info',
        node_type: 'info_recommend',
        output_key: 'info_recommend',
        artifact: parsedArtifact,
        created_at: new Date().toISOString(),
      });
    }
    return true;
  }

  async function regenerateBrief(direction = '强化悬疑钩子与人物关系') {
    if (!activeRunId || !state.approvalPending) return false;
    return candidates.regenerateStageDraft('info', direction);
  }

  async function confirmStageArtifact(stageId: string, editedArtifact?: string) {
    if (!activeRunId) return false;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage || stage.id === 'info') return false;
    const artifact = editedArtifact?.trim()
      ? parseApprovalArtifact(editedArtifact)
      : selectLatestStageArtifact(eventsRef.current, stage.id) ?? {};
    if (isBackendRunSource(runSource)) {
      try {
        await approveRunArtifact(
          activeRunId,
          stage.id,
          stage.output_key || stage.id,
          artifact,
        );
      } catch (error) {
        onWarning(`${stage.label} 定稿提交失败：${errorMessage(error)}`);
        return false;
      }
    } else {
      emitEvent({
        type: 'stage_artifact_confirmed',
        run_id: activeRunId,
        node_id: stage.id,
        node_type: stage.type,
        label: stage.label,
        output_key: stage.output_key,
        artifact,
        message: `${stage.label} 已人工定稿。`,
        created_at: new Date().toISOString(),
      });
    }
    setState((current) => stageConfirmedState(current, stage.id));
    setRunControl({ paused: true, runControlState: 'paused', running: false });
    return true;
  }

  return {
    ...candidates,
    applyEvent,
    approveBrief,
    beginContinuation,
    clearCheckpoint,
    confirmStageArtifact,
    markExportReady,
    regenerateBrief,
    reset,
    restore,
    setApprovalDraft,
    state,
    syncPausedStream,
  };
}

export type StageDecisionController = ReturnType<typeof useStageDecision>;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}

function isInfoSourceEvent(event: RunEvent) {
  return event.node_id === 'info' && [
    'approval_required',
    'brief_regenerated',
    'draft_candidate_selected',
  ].includes(event.type);
}
