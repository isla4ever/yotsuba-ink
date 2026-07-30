import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';

export function shouldFocusVariants(
  stage: WorkflowStage,
  events: RunEvent[],
  workflow: WorkflowDefinition,
) {
  if (stage.type === 'info_recommend' || !stage.variant_policy.enabled || workflow.quality_mode !== 'balanced') {
    return false;
  }
  if (!events.some((event) => event.type === 'variant_compare_requested' && event.node_id === stage.id)) {
    return false;
  }
  const variantCount = events.filter((event) => event.type === 'variant_generated' && event.node_id === stage.id).length;
  const selected = events.some((event) => event.type === 'best_variant_selected' && event.node_id === stage.id);
  return variantCount > 1 && !selected;
}

export function shouldFocusDraftCandidates(
  stage: WorkflowStage,
  events: RunEvent[],
  workflow: WorkflowDefinition,
) {
  const allowed = stage.type === 'info_recommend'
    ? workflow.quality_mode === 'balanced' || workflow.quality_mode === 'deep'
    : workflow.quality_mode === 'deep';
  if (!allowed) return false;
  const requestIndex = events.findIndex((event) => event.type === 'draft_regeneration_requested' && event.node_id === stage.id);
  const requested = requestIndex >= 0;
  const requestId = requested ? events[requestIndex].request_id : undefined;
  const laterEvents = requested ? events.slice(0, requestIndex) : [];
  const belongsToLatestRequest = (event: RunEvent) => !requestId || !event.request_id || event.request_id === requestId;
  const selectedAfterLatestRequest = laterEvents.some((event) => event.type === 'draft_candidate_selected' && event.node_id === stage.id && belongsToLatestRequest(event));
  const failedAfterLatestRequest = laterEvents.some((event) => event.type === 'draft_regeneration_failed' && event.node_id === stage.id && belongsToLatestRequest(event));
  const candidateCount = events.filter((event) => event.type === 'draft_candidate_generated' && event.node_id === stage.id && belongsToLatestRequest(event)).length;
  const confirmed = events.some((event) => event.type === 'stage_artifact_confirmed' && event.node_id === stage.id);
  return (requested || candidateCount > 0) && !selectedAfterLatestRequest && !failedAfterLatestRequest && !confirmed;
}

export function latestDraftRegenerationFailure(stageId: string, events: RunEvent[]) {
  const requestIndex = events.findIndex((event) => (
    event.type === 'draft_regeneration_requested' && event.node_id === stageId
  ));
  if (requestIndex < 0) return null;
  const requestId = events[requestIndex].request_id;
  return events.slice(0, requestIndex).find((event) => (
    event.type === 'draft_regeneration_failed'
    && event.node_id === stageId
    && (!requestId || !event.request_id || event.request_id === requestId)
  )) ?? null;
}
