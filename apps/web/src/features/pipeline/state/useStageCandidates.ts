import { useRef, type MutableRefObject } from 'react';
import type { RunEvent, WorkflowDefinition } from '../contracts';
import { regenerateRunDraft, selectRunDraftCandidate } from '../services/runApi';

type StageCandidateOptions = {
  activeRunId: string;
  emitEvent: (event: RunEvent) => void;
  eventsRef: MutableRefObject<RunEvent[]>;
  onWarning: (message: string) => void;
  workflow: WorkflowDefinition;
};

export function useStageCandidates({
  activeRunId,
  emitEvent,
  eventsRef,
  onWarning,
  workflow,
}: StageCandidateOptions) {
  const draftRequestRef = useRef(0);

  function resetCandidates() {
    draftRequestRef.current += 1;
  }

  async function regenerateStageDraft(stageId: string, direction: string) {
    if (!activeRunId) return false;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage) return false;
    const requestId = ++draftRequestRef.current;
    const clientRequestId = `${stage.id}-${Date.now()}-${requestId}`;
    emitEvent({
      type: 'draft_regeneration_requested',
      run_id: activeRunId,
      node_id: stage.id,
      node_type: stage.type,
      label: stage.label,
      section: direction,
      message: `按「${direction}」生成候选稿。`,
      candidate_count: 3,
      request_id: clientRequestId,
      created_at: new Date().toISOString(),
    });
    try {
      const response = await regenerateRunDraft(
        activeRunId,
        workflow.id,
        stage.id,
        direction,
        3,
        clientRequestId,
      );
      if (draftRequestRef.current !== requestId) return false;
      const responseEvents = response.events ?? [];
      responseEvents
        ?.filter((event) => event.type !== 'draft_regeneration_requested')
        .forEach(emitEvent);
      if (!responseEvents.some((event) => event.type === 'draft_candidate_generated' && event.request_id === clientRequestId)) {
        onWarning(`${stage.label} 换一稿失败：没有生成可用候选`);
        return false;
      }
      return true;
    } catch (error) {
      emitEvent({
        type: 'draft_regeneration_failed',
        run_id: activeRunId,
        node_id: stage.id,
        node_type: stage.type,
        label: stage.label,
        error: errorMessage(error),
        request_id: clientRequestId,
        created_at: new Date().toISOString(),
      });
      onWarning(`${stage.label} 换一稿失败：${errorMessage(error)}`);
      return false;
    }
  }

  async function selectDraftCandidate(stageId: string, candidateKey: string) {
    if (!activeRunId) return false;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage) return false;
    try {
      const response = await selectRunDraftCandidate(
        activeRunId,
        workflow.id,
        stage.id,
        candidateKey,
      );
      if (response.event) emitEvent(response.event);
      return Boolean(response.event);
    } catch (error) {
      onWarning(`${stage.label} 选稿写回失败：${errorMessage(error)}`);
      return false;
    }
  }

  async function requestVariantCompare(stageId: string) {
    if (!activeRunId || workflow.quality_mode !== 'balanced') return;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage || !stage.variant_policy.enabled) return;
    emitEvent({
      type: 'variant_compare_requested',
      run_id: activeRunId,
      node_id: stage.id,
      node_type: stage.type,
      label: stage.label,
      message: '用户主动进入版本对比。',
      created_at: new Date().toISOString(),
    });
    try {
      const response = await regenerateRunDraft(
        activeRunId,
        workflow.id,
        stage.id,
        '生成用于平衡模式对比的差异化候选',
        3,
      );
      response.events?.forEach((event) => {
        if (event.type !== 'draft_candidate_generated') return;
        const variantId = event.section || `候选 ${event.score ?? ''}`;
        emitEvent({
          ...event,
          type: 'variant_generated',
          artifact_source: 'live',
          variant: {
            artifact: event.artifact,
            node_id: stage.id,
            score: Number(event.score ?? 0),
            variant_id: variantId,
          },
        });
      });
    } catch (error) {
      onWarning(`${stage.label} 版本对比生成失败：${errorMessage(error)}`);
    }
  }

  async function selectBalancedVariant(
    stageId: string,
    variantId: string,
    modelPicked = false,
  ) {
    if (!activeRunId) return;
    const stage = workflow.nodes.find((item) => item.id === stageId);
    if (!stage) return;
    if (modelPicked) {
      onWarning('模型自动评审接口尚未接入，本次没有伪造评审结果；请手动选择真实候选。');
      return;
    }
    try {
      const response = await selectRunDraftCandidate(
        activeRunId,
        workflow.id,
        stage.id,
        variantId,
      );
      if (response.event) emitEvent(response.event);
      const source = eventsRef.current.find((event) => (
        event.type === 'variant_generated'
        && event.node_id === stage.id
        && event.variant
        && 'variant_id' in event.variant
        && event.variant.variant_id === variantId
      ));
      emitEvent({
        type: 'best_variant_selected',
        run_id: activeRunId,
        node_id: stage.id,
        node_type: stage.type,
        label: stage.label,
        selected: {
          node_id: stage.id,
          variant_id: variantId,
          score: Number(source?.score ?? 0),
          reason: '用户手动选择真实候选作为当前阶段基线。',
        },
        created_at: new Date().toISOString(),
      });
    } catch (error) {
      onWarning(`${stage.label} 候选择优失败：${errorMessage(error)}`);
    }
  }

  return {
    regenerateStageDraft,
    requestVariantCompare,
    resetCandidates,
    selectBalancedVariant,
    selectDraftCandidate,
  };
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}
