import type { RunEvent } from '../contracts';
import { latestApprovedArtifact, latestResult } from './stageRunUtils';

export function infoArtifactSource(events: RunEvent[], approvalDraft: string, approvalPending: boolean) {
  const confirmed = latestApprovedArtifact(events, 'info') || latestResult(events, 'info');
  if (approvalPending && approvalDraft.trim()) return approvalDraft;
  return confirmed || approvalDraft;
}
