import type { RunEvent } from '../contracts';

export function pendingStageDecision(
  events: RunEvent[],
  stageId: string,
  chapterId?: string,
): RunEvent | undefined {
  const latestSignal = latestEvent(events, (event) => (
    (event.type === 'decision.required' || event.type === 'decision.resolved')
    && (event.stage_id || event.node_id.split('.')[0]) === stageId
    && (chapterId === undefined || event.chapter_id === chapterId)
  ));
  return latestSignal?.type === 'decision.required' ? latestSignal : undefined;
}

export function isFailureDecision(event?: RunEvent): event is RunEvent {
  return Boolean(event?.node_id.endsWith('.failure_decision'));
}

export function failureMessageForDecision(events: RunEvent[], decision: RunEvent) {
  const failure = recordValue(decision.payload?.failure);
  const projectedMessage = textValue(failure?.message) || textValue(failure?.code);
  if (projectedMessage) return projectedMessage;

  const nodeFailure = latestEvent(events, (event) => (
    event.type === 'node.failed'
    && (event.stage_id || event.node_id.split('.')[0]) === (decision.stage_id || decision.node_id.split('.')[0])
    && (!decision.chapter_id || event.chapter_id === decision.chapter_id)
    && event.sequence < decision.sequence
  ));
  return textValue(nodeFailure?.payload?.message) || textValue(nodeFailure?.payload?.code);
}

function latestEvent(events: RunEvent[], predicate: (event: RunEvent) => boolean) {
  let latest: RunEvent | undefined;
  for (const event of events) {
    if (predicate(event) && (!latest || event.sequence > latest.sequence)) latest = event;
  }
  return latest;
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value : '';
}
