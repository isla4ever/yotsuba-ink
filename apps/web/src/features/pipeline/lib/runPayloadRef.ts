import type { RunEvent } from '../contracts';

export type RunPayloadAuthority = 'artifact-record' | 'chapter-version';

export function runPayloadAuthority(event: RunEvent): RunPayloadAuthority | null {
  const isArtifactEvent = event.type === 'artifact.candidate_ready' || event.type === 'artifact.committed';
  if (!event.payload_ref || event.payload || !isArtifactEvent) return null;
  if (event.stage_id === 'text' && event.chapter_id) return 'chapter-version';
  return event.stage_id ? 'artifact-record' : null;
}
