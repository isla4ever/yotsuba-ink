import type { RunEvent, WorkflowStage } from '../contracts';
import { parseCoverArtifact, parseExportArtifact } from '../running/artifactsVnext';
import { indexedStageStatus, type RunEventIndex, type StageRunStatus } from './runEventIndex';

type StageIdentity = Pick<WorkflowStage, 'id' | 'type'>;

const artifactEventTypes = new Set([
  'artifact.candidate_ready',
  'artifact.committed',
]);

/**
 * Lifecycle completion is not delivery completion for Cover and Export.
 * These two stages must also carry a usable asset/package artifact.
 */
export function stageDeliveryStatus(index: RunEventIndex, stage: StageIdentity): StageRunStatus {
  const lifecycleStatus = indexedStageStatus(index, stage.id);
  if (lifecycleStatus !== 'done') return lifecycleStatus;
  if (stage.type === 'cover') return coverReady(index.byStage[stage.id] ?? []) ? 'done' : 'attention';
  if (stage.type === 'export') return exportReady(index.byStage[stage.id] ?? []) ? 'done' : 'attention';
  return lifecycleStatus;
}

export function completedDeliveryStageIds(index: RunEventIndex, stages: StageIdentity[]): string[] {
  return stages
    .filter((stage) => stageDeliveryStatus(index, stage) === 'done')
    .map((stage) => stage.id);
}

function coverReady(events: RunEvent[]) {
  const value = latestArtifactValue(events);
  if (events.some((event) => event.type === 'cover.asset_skipped' && event.payload?.metadata_only === true)) return true;
  return Boolean(value && parseCoverArtifact(value).artifact?.selected_asset_id);
}

function exportReady(events: RunEvent[]) {
  const value = latestArtifactValue(events);
  return Boolean(value && parseExportArtifact(value).artifact?.chapter_version_ids.length);
}

function latestArtifactValue(events: RunEvent[]) {
  const event = events.find((candidate) => artifactEventTypes.has(candidate.type) && candidate.payload != null);
  return artifactValue(event);
}

function artifactValue(event?: RunEvent) {
  const value = event?.payload;
  return value && typeof value === 'object' ? JSON.stringify(value) : '';
}
