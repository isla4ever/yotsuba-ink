import type {
  ChapterRevisionBasePayload,
  ChapterRevisionCandidate,
  ChapterRevisionOperation,
  ChapterReviewResponse,
  ChapterSelection,
  ChapterWritebackProposal,
  ExportFormat,
  ExportMetadata,
  RunEvent,
  RunInputs,
} from '../contracts';
import { verifyExportBlob } from './exportIntegrity';
import type { StoredRunSnapshot } from '../state/runState';

export class RunApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'RunApiError';
  }
}

export async function getRun(runId: string, signal?: AbortSignal): Promise<StoredRunSnapshot> {
  const response = await fetch(`/api/runs/${runId}`, { signal });
  if (!response.ok) throw new RunApiError(`Unable to load run ${runId}`, response.status);
  return response.json();
}

export function isRunNotFoundError(error: unknown) {
  return error instanceof RunApiError && error.status === 404;
}

export async function resumeRun(runId: string) {
  await postWithoutBody(`/api/runs/${runId}/resume`);
}

export async function advanceRun(runId: string) {
  await postWithoutBody(`/api/runs/${runId}/advance`);
}

export async function replayStage(runId: string) {
  await postWithoutBody(`/api/runs/${runId}/replay-stage`);
}

export async function pauseRunRequest(runId: string) {
  await postWithoutBody(`/api/runs/${runId}/pause`);
}

export async function approveRunBrief(runId: string, artifact: unknown) {
  await approveRunArtifact(runId, 'info', 'info_recommend', artifact);
}

export async function approveRunArtifact(runId: string, nodeId: string, outputKey: string, artifact: unknown) {
  await postJson(`/api/runs/${runId}/approve-artifact`, {
    node_id: nodeId,
    output_key: outputKey,
    artifact,
  });
}

export async function regenerateRunBrief(
  runId: string,
  workflowId: string,
  inputs: RunInputs,
): Promise<{ artifact?: unknown }> {
  const response = await postJson(`/api/runs/${runId}/regenerate-brief`, {
    workflow_id: workflowId,
    inputs,
  });
  return response.json();
}

export async function regenerateRunDraft(
  runId: string,
  workflowId: string,
  nodeId: string,
  direction: string,
  candidateCount = 3,
  requestId = '',
): Promise<{ events?: RunEvent[] }> {
  const response = await postJson(`/api/runs/${runId}/regenerate-draft`, {
    workflow_id: workflowId,
    node_id: nodeId,
    direction,
    candidate_count: candidateCount,
    request_id: requestId,
  });
  return response.json();
}

export async function selectRunDraftCandidate(
  runId: string,
  workflowId: string,
  nodeId: string,
  section: string,
): Promise<{ event?: RunEvent }> {
  const response = await postJson(`/api/runs/${runId}/select-draft-candidate`, {
    workflow_id: workflowId,
    node_id: nodeId,
    section,
  });
  return response.json();
}

export async function retryCoverAsset(
  runId: string,
  candidateId: string,
  requestId: string,
): Promise<{ artifact: unknown; events?: RunEvent[]; reused?: boolean }> {
  const response = await postJson(`/api/runs/${runId}/cover-assets/retry`, {
    candidate_id: candidateId,
    request_id: requestId,
  });
  return response.json();
}

export async function generateChapterSelectionRevision(
  runId: string,
  payload: ChapterRevisionBasePayload & Omit<ChapterSelection, 'text'> & {
    operation: ChapterRevisionOperation;
    direction: string;
    selected_text: string;
  },
): Promise<{ candidate: ChapterRevisionCandidate }> {
  const response = await postJson(`/api/runs/${runId}/chapter-selection-revisions`, payload);
  return response.json();
}

export async function applyChapterSelectionRevision(
  runId: string,
  payload: { workflow_id: string; node_id: string; request_id: string; candidate_signature: string },
): Promise<{ artifact: unknown; chapter: Record<string, unknown> }> {
  const response = await postJson(`/api/runs/${runId}/chapter-selection-revisions/apply`, payload);
  return response.json();
}

export async function restoreChapterVersion(
  runId: string,
  payload: ChapterRevisionBasePayload & { version_id: string },
): Promise<{ artifact: unknown; chapter: Record<string, unknown> }> {
  const response = await postJson(`/api/runs/${runId}/chapter-versions/restore`, payload);
  return response.json();
}

export async function syncChapterSummary(
  runId: string,
  chapterId: string,
  payload: ChapterRevisionBasePayload & { summary: string },
): Promise<ChapterReviewResponse> {
  const response = await postJson(`/api/runs/${runId}/chapters/${chapterId}/sync-summary`, payload);
  return response.json();
}

export async function decideChapterWritebackProposal(
  runId: string,
  chapterId: string,
  payload: {
    workflow_id: string;
    node_id: string;
    chapter_id: string;
    proposal_id: string;
    proposal_signature: string;
    decision: 'accepted' | 'rejected';
    base_version: number;
    base_signature: string;
    request_id: string;
    conflict_resolutions?: NonNullable<ChapterWritebackProposal['conflict_resolutions']>;
  },
): Promise<ChapterReviewResponse> {
  const response = await postJson(`/api/runs/${runId}/chapters/${chapterId}/writeback-proposal`, payload);
  return response.json();
}

export async function createRunStream(workflowId: string, inputs: RunInputs, signal?: AbortSignal, runId?: string) {
  const response = await postJson('/api/runs/stream', {
    workflow_id: workflowId,
    run_id: runId,
    project_id: inputs.project_id || undefined,
    inputs,
  }, signal);
  return response;
}

export async function streamExistingRun(runId: string, signal?: AbortSignal) {
  return fetch(`/api/runs/${runId}/events`, { method: 'POST', signal });
}

export async function downloadRunExportPackage(
  runId: string,
  format: ExportFormat,
  chapterIds: string[],
  requestId = '',
  metadata?: ExportMetadata,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string; export_id: string; version: number; snapshot_id: string; artifact_signature: string; selection_digest: string; sha256: string }> {
  const body: { format: ExportFormat; chapter_ids: string[]; metadata?: ExportMetadata; request_id?: string } = { format, chapter_ids: chapterIds };
  if (requestId) body.request_id = requestId;
  if (metadata) body.metadata = metadata;
  const response = await postJson(`/api/runs/${runId}/export-package`, body, signal);
  const disposition = response.headers.get('content-disposition') ?? '';
  const sha256 = response.headers.get('x-export-sha256') ?? '';
  const contentLength = response.headers.get('content-length');
  const blob = await response.blob();
  await verifyExportBlob(blob, {
    expectedSizeBytes: contentLength == null ? undefined : Number(contentLength),
    responseSha256: sha256,
  });
  return {
    blob,
    filename: filenameFromDisposition(disposition, `novel-export.${format}`),
    export_id: response.headers.get('x-export-id') ?? '',
    version: Number(response.headers.get('x-export-version') || 0),
    snapshot_id: response.headers.get('x-source-snapshot-id') ?? '',
    artifact_signature: response.headers.get('x-artifact-signature') ?? '',
    selection_digest: response.headers.get('x-selection-digest') ?? '',
    sha256,
  };
}

export async function downloadRunExportPreview(
  runId: string,
  format: ExportFormat,
  chapterIds: string[],
  metadata?: ExportMetadata,
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string; sha256: string }> {
  const response = await postJson(`/api/runs/${runId}/export-preview`, {
    format,
    chapter_ids: chapterIds,
    metadata,
  }, signal);
  const disposition = response.headers.get('content-disposition') ?? '';
  const sha256 = response.headers.get('x-preview-sha256') ?? '';
  const blob = await response.blob();
  await verifyExportBlob(blob, { responseSha256: sha256 });
  return {
    blob,
    filename: filenameFromDisposition(disposition, `novel-preview.${format}`),
    sha256,
  };
}

async function postWithoutBody(url: string) {
  const response = await fetch(url, { method: 'POST' });
  if (!response.ok) throw await responseError(response, url);
  return response;
}

async function postJson(url: string, body: unknown, signal?: AbortSignal) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await responseError(response, url);
  return response;
}

async function responseError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    detail = '';
  }
  return new RunApiError(detail || `Request failed: ${url} ${response.status}`, response.status);
}

function filenameFromDisposition(value: string, fallback: string) {
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return fallback;
    }
  }
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback;
}

export function briefRegeneratedEvent(runId: string, artifact: unknown): RunEvent {
  return {
    type: 'brief_regenerated',
    run_id: runId,
    node_id: 'info',
    node_type: 'info_recommend',
    artifact,
  };
}
