import type { RunEvent, WorkflowStage } from '../contracts';
import { coverArtifact, exportArtifact } from '../running/stageArtifacts';
import { formalCoverCandidateId } from '../running/coverPresentation';
import { indexedStageStatus, type RunEventIndex, type StageRunStatus } from './runEventIndex';

type StageIdentity = Pick<WorkflowStage, 'id' | 'type'>;

const artifactEventTypes = new Set([
  'artifact_approved',
  'asset_progress_updated',
  'node_completed',
  'run_export_ready',
  'stage_artifact_confirmed',
  'stage_checkpoint_ready',
]);

/**
 * Lifecycle completion is not delivery completion for Cover and Export.
 * These two stages must also carry a usable asset/package artifact.
 */
export function stageDeliveryStatus(index: RunEventIndex, stage: StageIdentity): StageRunStatus {
  const lifecycleStatus = indexedStageStatus(index, stage.id);
  if (lifecycleStatus !== 'done') return lifecycleStatus;
  if (stage.type === 'cover_image') return coverReady(index.byStage[stage.id] ?? []) ? 'done' : 'attention';
  if (stage.type === 'export_artifact') return exportReady(index.byStage[stage.id] ?? []) ? 'done' : 'attention';
  return lifecycleStatus;
}

export function completedDeliveryStageIds(index: RunEventIndex, stages: StageIdentity[]): string[] {
  return stages
    .filter((stage) => stageDeliveryStatus(index, stage) === 'done')
    .map((stage) => stage.id);
}

function coverReady(events: RunEvent[]) {
  const value = latestArtifactValue(events);
  return Boolean(value && formalCoverCandidateId(coverArtifact(value)));
}

function exportReady(events: RunEvent[]) {
  const readyEvent = events.find((event) => event.type === 'run_export_ready' && event.artifact != null);
  const value = artifactValue(readyEvent) || latestArtifactValue(events);
  return Boolean(value && exportArtifact(value).package_ready);
}

function latestArtifactValue(events: RunEvent[]) {
  const event = events.find((candidate) => artifactEventTypes.has(candidate.type) && (candidate.artifact != null || candidate.result != null));
  return artifactValue(event);
}

function artifactValue(event?: RunEvent) {
  const value = event?.artifact ?? event?.result;
  if (typeof value === 'string') return value.trim();
  return value && typeof value === 'object' ? JSON.stringify(value) : '';
}
