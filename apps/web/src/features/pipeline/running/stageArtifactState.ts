import type { RunEvent, StageType, WorkflowStage } from '../contracts';
import { parseArtifactRecord } from './stageArtifacts';

export type ArtifactSource = 'live' | 'fixture';

export type StageArtifactDraft = { source: string; value: string };

export type StageArtifactState =
  | { status: 'ready'; result: string; source: ArtifactSource }
  | { status: 'streaming'; sections: string[] }
  | { status: 'empty' }
  | { status: 'invalid'; message: string }
  | { status: 'error'; message: string };

const artifactEventTypes = new Set([
  'artifact_approved',
  'artifact_validated',
  'brief_regenerated',
  'draft_candidate_selected',
  'chapter_selection_revision_applied',
  'chapter_version_restored',
  'chapter_summary_synced',
  'chapter_writeback_proposal_generated',
  'chapter_writeback_proposal_accepted',
  'chapter_writeback_proposal_rejected',
  'asset_progress_updated',
  'node_completed',
  'stage_artifact_confirmed',
]);

export function stageArtifactState(stage: WorkflowStage, events: RunEvent[], draft = ''): StageArtifactState {
  const stageEvents = events.filter((event) => event.node_id === stage.id || event.type === 'run_error');
  for (const event of stageEvents) {
    if (event.type === 'node_failed' || event.type === 'run_error') {
      const message = event.error || event.message || '阶段执行失败，请返回工作台检查运行配置。';
      return {
        status: 'error',
        message: event.recovery_state?.needs_recovery
          ? `${message} 已保存最后稳定检查点，请点击“继续创作”恢复。`
          : message,
      };
    }
    if (event.type === 'artifact_validation_failed') {
      return { status: 'invalid', message: validationMessage(event) };
    }
    if (artifactEventTypes.has(event.type)) {
      const value = event.artifact ?? event.result;
      return assessArtifact(stage.type, value, artifactSource(event));
    }
    if (event.type === 'node_started') {
      return { status: 'streaming', sections: streamSections(stageEvents) };
    }
  }

  if (stage.type === 'info_recommend' && draft.trim()) {
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
  const record = typeof value === 'string' ? parseArtifactRecord(value) : objectRecord(value);
  if (!record || !hasStageShape(type, record)) {
    return { status: 'invalid', message: '模型返回内容未满足当前阶段的结构要求。' };
  }
  return { status: 'ready', result, source };
}

function hasStageShape(type: StageType, record: Record<string, unknown>) {
  if (type === 'info_recommend') {
    return hasText(record.selected_title) && hasText(record.synopsis) && hasText(record.worldbuilding_detail) && hasItems(record.characters);
  }
  if (type === 'summary') {
    return hasText(record.full_synopsis) && hasItems(record.act_structure) && hasItems(record.key_turns);
  }
  if (type === 'outline') return hasItems(record.volumes);
  if (type === 'detail_outline') return hasItems(record.chapters);
  if (type === 'chapter_text') return hasItems(record.chapters);
  if (type === 'cover_image') return hasText(record.brief) && hasText(record.prompt) && hasItems(record.candidates);
  if (type === 'export_artifact') return hasItems(record.manifest);
  return true;
}

function streamSections(events: RunEvent[]) {
  return Array.from(new Set(events
    .filter((event) => event.type === 'artifact_stream_delta' || event.type === 'chapter_delta' || event.type === 'chapter_started')
    .map((event) => String(event.section || event.chapter || event.label || '').trim())
    .filter(Boolean))).slice(0, 4);
}

function validationMessage(event: RunEvent) {
  if (event.errors?.length) return event.errors.slice(0, 3).join('；');
  return event.error || event.message || '阶段产物结构检查未通过。';
}

function artifactSource(event: RunEvent): ArtifactSource {
  return event.artifact_source === 'fixture' || event.execution_mode === 'demo' ? 'fixture' : 'live';
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
