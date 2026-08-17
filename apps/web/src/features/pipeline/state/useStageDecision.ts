import { useState, type MutableRefObject } from 'react';
import type { RunEvent, WorkflowDefinition } from '../contracts';
import { pendingStageDecision } from '../lib/runDecisionProjection';
import { resolveRunDecision } from '../services/runApi';
import type { HydratedRunState } from './runState';
import {
  parseApprovalArtifact,
  selectCheckpointStageId,
  selectLatestStageArtifact,
} from './runSelectors';
import {
  continuationStartedState,
  decisionStateForPausedStream,
  initialStageDecisionState,
  restoreStageDecisionState,
  stageDecisionStateForEvent,
} from './stageDecisionState';
import { useStageRegeneration } from './useStageRegeneration';

type StageDecisionOptions = {
  activeRunId: string;
  eventsRef: MutableRefObject<RunEvent[]>;
  onWarning: (message: string) => void;
  onDecisionSubmitted?: () => Promise<void>;
  workflow: WorkflowDefinition;
};

export function useStageDecision({
  activeRunId,
  eventsRef,
  onWarning,
  onDecisionSubmitted,
  workflow,
}: StageDecisionOptions) {
  const [state, setState] = useState(initialStageDecisionState);
  const regeneration = useStageRegeneration({
    activeRunId,
    eventsRef,
    onWarning,
    onDecisionSubmitted,
    workflow,
  });

  function restore(hydrated: HydratedRunState) {
    setState(restoreStageDecisionState(hydrated));
  }

  function reset() {
    regeneration.resetRegeneration();
    setState(initialStageDecisionState);
  }

  function syncPausedStream(events: RunEvent[]) {
    setState((current) => decisionStateForPausedStream(current, events));
  }

  function applyEvent(event: RunEvent) {
    setState((current) => stageDecisionStateForEvent(current, event));
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

  function clearCheckpoint() {
    setState((current) => continuationStartedState(current));
  }

  async function approveBrief(artifact: string) {
    if (!activeRunId) return false;
    const parsedArtifact = parseApprovalArtifact(artifact);
    try {
      await submitGraphDecision('brief', 'accept', parsedArtifact);
    } catch (error) {
      onWarning(`创作立项定稿提交失败：${errorMessage(error)}`);
      return false;
    }
    return true;
  }

  async function regenerateBrief(direction = '强化悬疑钩子与人物关系') {
    if (!activeRunId || !state.approvalPending) return false;
    return regeneration.regenerateStageDraft('brief', direction);
  }

  async function confirmStageArtifact(stageId: string, editedArtifact?: string) {
    if (!activeRunId) return false;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage || stage.id === 'brief') return false;
    const artifact = editedArtifact?.trim()
      ? parseApprovalArtifact(editedArtifact)
      : selectLatestStageArtifact(eventsRef.current, stage.id) ?? {};
    try {
      await submitGraphDecision(stage.id, 'accept', artifact);
    } catch (error) {
      onWarning(`${stage.label} 定稿提交失败：${errorMessage(error)}`);
      return false;
    }
    return true;
  }

  return {
    ...regeneration,
    applyEvent,
    approveBrief,
    beginContinuation,
    clearCheckpoint,
    confirmStageArtifact,
    regenerateBrief,
    reset,
    restore,
    state,
    syncPausedStream,
  };

  async function submitGraphDecision(
    stageId: string,
    action: 'accept' | 'regenerate' | 'cancel',
    artifact?: unknown,
  ) {
    const event = pendingStageDecision(eventsRef.current, stageId);
    const payload = event?.payload;
    const decisionId = typeof payload?.decision_id === 'string' ? payload.decision_id : '';
    const revision = Number(payload?.domain_revision);
    if (!decisionId || !Number.isInteger(revision) || revision < 0) {
      throw new Error('当前阶段没有可提交的 LangGraph interrupt');
    }
    await resolveRunDecision(
      activeRunId,
      decisionId,
      action,
      revision,
      artifact && typeof artifact === 'object' && !Array.isArray(artifact)
        ? artifact as Record<string, unknown>
        : undefined,
    );
    await onDecisionSubmitted?.();
  }
}

export type StageDecisionController = ReturnType<typeof useStageDecision>;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}
