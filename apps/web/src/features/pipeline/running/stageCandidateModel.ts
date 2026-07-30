import type { RunEvent } from '../contracts';
import { candidatePreviewText } from './stageCandidatePreview';

export type StageDraftCandidate = {
  artifact?: unknown;
  id: string;
  label: string;
  preview: string;
  ready: boolean;
  status: 'failed' | 'generating' | 'ready';
  title: string;
};

export function currentDraftCandidates(events: RunEvent[], stageId: string): StageDraftCandidate[] {
  const requested = events.find((event) => event.type === 'draft_regeneration_requested' && event.node_id === stageId);
  const requestTime = eventTime(requested);
  const requestId = requested?.request_id;
  const generated = generatedCandidates(events, stageId).filter((candidate) => {
    if (requestId && candidate.requestId) return candidate.requestId === requestId;
    return candidate.createdAt >= requestTime;
  });
  if (!requested) return generated.slice(-3).map(publicCandidate);

  const byLabel = new Map(generated.map((candidate) => [candidate.label, candidate]));
  const failures = failedCandidates(events, stageId, requested);
  const expectedCount = candidateCount(requested, generated.length, failures.size);
  return Array.from({ length: expectedCount }, (_, index) => {
    const label = `候选 ${index + 1}`;
    const existing = byLabel.get(label);
    if (existing) return publicCandidate(existing);
    const failure = failures.get(label);
    if (failure) {
      return {
        id: String(failure.candidate_id || `failed-${index + 1}`),
        label,
        preview: failure.errors?.join('；') || failure.message || failure.error || '候选未通过结构检查。',
        ready: false,
        status: 'failed' as const,
        title: String(requested.label ?? ''),
      };
    }
    return {
      id: `pending-${index + 1}`,
      label,
      preview: index === 0 ? String(requested.message ?? '候选生成中...') : '候选生成中...',
      ready: false,
      status: 'generating' as const,
      title: String(requested.label ?? ''),
    };
  });
}

export function draftCandidateHistory(events: RunEvent[], stageId: string): StageDraftCandidate[] {
  const requested = events.find((event) => event.type === 'draft_regeneration_requested' && event.node_id === stageId);
  const requestTime = eventTime(requested);
  const requestId = requested?.request_id;
  return generatedCandidates(events, stageId)
    .filter((candidate) => {
      if (requestId && candidate.requestId) return candidate.requestId !== requestId;
      return candidate.createdAt < requestTime;
    })
    .reverse()
    .slice(0, 12)
    .map(publicCandidate);
}

function generatedCandidates(events: RunEvent[], stageId: string) {
  const chronological = [...events].reverse();
  const streams = new Map<string, string>();
  chronological
    .filter((event) => event.type === 'draft_candidate_stream_delta' && event.node_id === stageId && event.delta)
    .forEach((event) => {
      const key = candidateKey(event);
      streams.set(key, `${streams.get(key) ?? ''}${event.delta}`);
    });
  return chronological
    .filter((event) => event.type === 'draft_candidate_generated' && event.node_id === stageId)
    .map((event, index) => {
      const id = candidateKey(event) || `candidate-${index + 1}`;
      return {
        artifact: event.artifact,
        createdAt: eventTime(event),
        id,
        label: String(event.section || `候选 ${index + 1}`),
        preview: candidatePreviewText(event.artifact, streams.get(id) || event.preview || event.message),
        ready: true,
        requestId: event.request_id,
        status: 'ready' as const,
        title: artifactTitle(event.artifact) || String(event.label ?? ''),
      };
    });
}

function publicCandidate(candidate: ReturnType<typeof generatedCandidates>[number]): StageDraftCandidate {
  return {
    artifact: candidate.artifact,
    id: candidate.id,
    label: candidate.label,
    preview: candidate.preview,
    ready: candidate.ready,
    status: candidate.status,
    title: candidate.title,
  };
}

function failedCandidates(events: RunEvent[], stageId: string, requested: RunEvent) {
  const requestTime = eventTime(requested);
  const requestId = requested.request_id;
  return new Map(
    events
      .filter((event) => event.type === 'artifact_validation_failed' && event.node_id === stageId)
      .filter((event) => {
        if (requestId && event.request_id) return event.request_id === requestId;
        return eventTime(event) >= requestTime;
      })
      .map((event) => [String(event.section || ''), event]),
  );
}

function candidateCount(requested: RunEvent, generatedCount: number, failedCount: number) {
  const declared = Number(requested.candidate_count);
  if (Number.isFinite(declared) && declared > 0) return Math.max(1, Math.min(3, Math.floor(declared)));
  return Math.min(3, generatedCount + failedCount);
}

function candidateKey(event: RunEvent) {
  return String(event.candidate_id || event.section || '');
}

function artifactTitle(artifact: unknown) {
  if (!artifact || typeof artifact !== 'object' || Array.isArray(artifact)) return '';
  const record = artifact as Record<string, unknown>;
  return String(record.selected_title || record.title || record.one_liner || '').trim();
}

function eventTime(event?: RunEvent) {
  if (!event?.created_at) return 0;
  const time = Date.parse(event.created_at);
  return Number.isFinite(time) ? time : 0;
}
