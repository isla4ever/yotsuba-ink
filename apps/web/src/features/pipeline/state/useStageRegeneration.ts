import { useRef, type MutableRefObject } from 'react';
import type { RunEvent, WorkflowDefinition } from '../contracts';
import { resolveRunDecision } from '../services/runApi';

type StageRegenerationOptions = {
  activeRunId: string;
  eventsRef: MutableRefObject<RunEvent[]>;
  onWarning: (message: string) => void;
  onDecisionSubmitted?: () => Promise<void>;
  workflow: WorkflowDefinition;
};

export function useStageRegeneration({
  activeRunId,
  eventsRef,
  onWarning,
  onDecisionSubmitted,
  workflow,
}: StageRegenerationOptions) {
  const requestEpochRef = useRef(0);

  function resetRegeneration() {
    requestEpochRef.current += 1;
  }

  async function regenerateStageDraft(stageId: string, direction: string, _chapterId = '') {
    if (!activeRunId) return false;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage) return false;
    const requestEpoch = ++requestEpochRef.current;
    try {
      const pending = pendingDecision(eventsRef.current, stage.id);
      await resolveRunDecision(
        activeRunId,
        pending.decisionId,
        'regenerate',
        pending.domainRevision,
        undefined,
        direction,
      );
      await onDecisionSubmitted?.();
      return requestEpochRef.current === requestEpoch;
    } catch (error) {
      onWarning(`${stage.label} 换一稿失败：${errorMessage(error)}`);
      return false;
    }
  }

  return { regenerateStageDraft, resetRegeneration };
}

function pendingDecision(events: RunEvent[], stageId: string) {
  const event = events.find((item) => (
    item.type === 'decision.required'
    && (item.stage_id || item.node_id?.split('.')[0]) === stageId
  ));
  const decisionId = typeof event?.payload?.decision_id === 'string'
    ? event.payload.decision_id
    : '';
  const domainRevision = Number(event?.payload?.domain_revision);
  if (!decisionId || !Number.isInteger(domainRevision) || domainRevision < 0) {
    throw new Error('当前阶段没有可恢复的 LangGraph 决策');
  }
  return { decisionId, domainRevision };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}
