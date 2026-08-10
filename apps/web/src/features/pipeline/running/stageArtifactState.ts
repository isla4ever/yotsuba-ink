import type { RunEvent, StageType, WorkflowStage } from '../contracts';
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

export function stageArtifactState(stage: WorkflowStage, events: RunEvent[], draft = ''): StageArtifactState {
  const stageEvents = events.filter((event) => eventStageId(event) === stage.id || event.type === 'run.failed');
  for (const event of stageEvents) {
    if (event.type === 'run.failed') {
      const message = payloadText(event, 'message') || payloadText(event, 'code') || '阶段执行失败，请返回工作台检查运行配置。';
      return { status: 'error', message };
    }
    if (artifactEventTypes.has(event.type)) {
      const value = event.payload;
      return assessArtifact(stage.type, value, artifactSource(event));
    }
    if (event.type === 'node.started') {
      return { status: 'streaming', sections: streamSections(stageEvents) };
    }
  }

  if (stage.type === 'info' && draft.trim()) {
    return assessArtifact(stage.type, draft, 'live');
  }
  return { status: 'empty' };
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
  if (type === 'info') return hasText(record.title) && hasText(record.premise) && hasItems(record.world_rules);
  if (type === 'summary') return hasItems(record.beats) && hasText(record.climax) && hasText(record.resolution);
  if (type === 'outline') return hasItems(record.volumes);
  if (type === 'detail') return hasItems(record.chapters);
  if (type === 'text') return hasText(record.chapter_id) && hasText(record.content);
  if (type === 'cover') return hasText(record.brief);
  if (type === 'export') return hasItems(record.chapter_version_ids);
  return true;
}

function streamSections(events: RunEvent[]) {
  return Array.from(new Set(events
    .filter((event) => event.type === 'node.started')
    .map((event) => {
      const parts = event.node_id.split('.');
      return parts[parts.length - 1]?.replace(/_/g, ' ') ?? '';
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
