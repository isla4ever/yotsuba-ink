import type { RunEvent, StageType, WorkflowStage } from '../contracts';
import { isFailureDecision, pendingStageDecision } from '../lib/runDecisionProjection';
import { eventStageId } from './stageRunUtils';

export type ArtifactSource = 'live' | 'fixture';

export type StageArtifactDraft = { source: string; value: string };

export type StageArtifactState =
  | { status: 'ready'; result: string; source: ArtifactSource }
  | { status: 'streaming'; sections: string[] }
  | { status: 'empty' }
  | { status: 'invalid'; message: string }
  | { status: 'error'; message: string };

const artifactEventTypes = new Set([
  'artifact.candidate_ready',
  'artifact.committed',
]);

export function stageArtifactState(stage: WorkflowStage, events: RunEvent[]): StageArtifactState {
  const stageEvents = events.filter((event) => eventStageId(event) === stage.id || event.type === 'run.failed');
  const failure = activeRunFailure(stageEvents);
  if (failure) {
    const message = payloadText(failure, 'message') || payloadText(failure, 'code') || '阶段执行失败，请返回工作台检查运行配置。';
    return { status: 'error', message };
  }

  const pendingDecision = pendingStageDecision(stageEvents, stage.id);
  const failureDecision = isFailureDecision(pendingDecision) ? pendingDecision : undefined;
  const artifactIndex = stageEvents.findIndex((event) => artifactEventTypes.has(event.type));
  if (artifactIndex >= 0) {
    const artifactEvent = stageEvents[artifactIndex];
    const newerEvents = stageEvents.slice(0, artifactIndex);
    if (failureDecision && failureDecision.sequence > artifactEvent.sequence) {
      return assessArtifact(stage.type, artifactEvent.payload, artifactSource(artifactEvent));
    }
    if (newCandidateCycleStarted(stage.type, artifactEvent, newerEvents)) {
      return { status: 'streaming', sections: streamSections(stageEvents) };
    }
    return assessArtifact(stage.type, artifactEvent.payload, artifactSource(artifactEvent));
  }

  const recoverableFailure = failureDecision
    ? stageEvents.find((event) => event.type === 'node.failed' && event.sequence < failureDecision.sequence)
    : undefined;
  if (recoverableFailure && failureDecision) {
    const message = payloadText(recoverableFailure, 'message') || payloadText(recoverableFailure, 'code') || '本次生成未通过阶段合同。';
    return { status: 'error', message };
  }

  if (stageEvents.some((event) => event.type === 'node.started')) {
    return { status: 'streaming', sections: streamSections(stageEvents) };
  }
  return { status: 'empty' };
}

function activeRunFailure(events: RunEvent[]) {
  const failure = events
    .filter((event) => event.type === 'run.failed')
    .reduce<RunEvent | undefined>((latest, event) => (
      !latest || event.sequence > latest.sequence ? event : latest
    ), undefined);
  if (!failure) return undefined;
  const superseded = events.some((event) => (
    event.sequence > failure.sequence
    && (
      event.type === 'branch.created'
      || event.type === 'run.started'
      || event.type === 'run.completed'
      || event.type === 'node.started'
      || event.type === 'decision.required'
      || event.type === 'decision.resolved'
      || artifactEventTypes.has(event.type)
    )
  ));
  return superseded ? undefined : failure;
}

function newCandidateCycleStarted(type: StageType, artifactEvent: RunEvent, newerEvents: RunEvent[]) {
  const generationNode = type === 'text' ? 'generate_prose' : 'generate_candidate';
  if (newerEvents.some((event) => event.type === 'node.started' && nodeName(event) === generationNode)) {
    return true;
  }
  if (type !== 'text' || !artifactEvent.chapter_id) return false;
  return newerEvents.some((event) => (
    event.type === 'node.started'
    && Boolean(event.chapter_id)
    && event.chapter_id !== artifactEvent.chapter_id
  ));
}

function nodeName(event: RunEvent) {
  const parts = event.node_id.split('.');
  return parts[parts.length - 1] ?? '';
}

export function currentStageArtifact(source: string, draft?: StageArtifactDraft) {
  return draft?.source === source ? draft.value : source;
}

function assessArtifact(type: StageType, value: unknown, source: ArtifactSource): StageArtifactState {
  const result = stringifyArtifact(value);
  if (!result) return { status: 'empty' };
  const record = typeof value === 'string' ? parseExactRecord(value) : objectRecord(value);
  if (!record || !hasStageShape(type, record)) {
    return { status: 'invalid', message: '模型返回内容未满足当前阶段的结构要求。' };
  }
  return { status: 'ready', result, source };
}

function hasStageShape(type: StageType, record: Record<string, unknown>) {
  if (type === 'brief') return hasText(record.title) && hasText(record.premise) && hasItems(record.world_rules);
  if (type === 'spine') {
    return hasItems(record.turns)
      && hasText(record.ending)
      && Array.isArray(record.open_questions)
      && hasItems(record.progress_types);
  }
  if (type === 'volumes') return hasItems(record.volumes);
  if (type === 'detail') return hasItems(record.chapters);
  if (type === 'text') return hasText(record.chapter_id) && hasText(record.content);
  if (type === 'cover') {
    const brief = objectRecord(record.brief);
    return Boolean(
      brief
      && hasText(brief.concept)
      && hasText(brief.image_prompt)
      && hasItems(brief.palette)
      && Array.isArray(brief.negative_constraints)
      && typeof record.selected_asset_id === 'string',
    );
  }
  if (type === 'export') return hasItems(record.chapter_version_ids);
  return true;
}

function streamSections(events: RunEvent[]) {
  return Array.from(new Set(events
    .filter((event) => event.type === 'node.started')
    .map((event) => {
      return nodeName(event).replace(/_/g, ' ');
    })
    .filter(Boolean))).slice(0, 4);
}

function artifactSource(event: RunEvent): ArtifactSource {
  return event.payload?.source === 'fixture' ? 'fixture' : 'live';
}

function parseExactRecord(value: string) {
  try {
    return objectRecord(JSON.parse(value));
  } catch {
    return null;
  }
}

function stringifyArtifact(value: unknown) {
  if (typeof value === 'string') return value.trim();
  if (!value || typeof value !== 'object') return '';
  return JSON.stringify(value);
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function hasText(value: unknown) {
  return typeof value === 'string' && Boolean(value.trim());
}

function hasItems(value: unknown) {
  return Array.isArray(value) && value.length > 0;
}

function payloadText(event: RunEvent, key: string) {
  const value = event.payload?.[key];
  return typeof value === 'string' ? value : '';
}
