import type {
  ChapterContextManifestRecord,
  GraphRunEnvelope,
  RunInputs,
  WorkflowDefinition,
} from '../contracts';

export class RunApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'RunApiError';
  }
}

export async function getRun(runId: string, signal?: AbortSignal): Promise<GraphRunEnvelope> {
  const response = await fetch(`/api/runs/${runId}`, { signal });
  if (!response.ok) throw new RunApiError(`Unable to load run ${runId}`, response.status);
  return response.json();
}

export async function createRunBranch(
  sourceRunId: string,
  checkpointId: string,
  targetRunId = `run-${crypto.randomUUID()}`,
  signal?: AbortSignal,
) {
  const response = await postJson(`/api/runs/${sourceRunId}/branches`, {
    target_run_id: targetRunId,
    checkpoint_id: checkpointId,
  }, signal);
  return response.json() as Promise<{
    run_id: string;
    thread_id: string;
    status: string;
    source_run_id: string;
    source_checkpoint_id: string;
  }>;
}

export function isRunNotFoundError(error: unknown) {
  return error instanceof RunApiError && error.status === 404;
}

export async function resolveRunDecision(
  runId: string,
  decisionId: string,
  action: 'accept' | 'regenerate' | 'cancel',
  domainRevision: number,
  artifact?: Record<string, unknown>,
  direction?: string,
) {
  await postJson(`/api/runs/${runId}/decisions/${encodeURIComponent(decisionId)}`, {
    action,
    domain_revision: domainRevision,
    ...(artifact ? { artifact } : {}),
    ...(direction?.trim() ? { direction: direction.trim() } : {}),
  });
}

export async function getArtifactRecord(runId: string, artifactId: string, signal?: AbortSignal) {
  const response = await fetch(`/api/runs/${runId}/artifact-records/${encodeURIComponent(artifactId)}`, { signal });
  if (!response.ok) throw await responseError(response, 'artifact record');
  return response.json() as Promise<{ payload: Record<string, unknown> }>;
}

export async function getContextManifest(
  runId: string,
  manifestId: string,
  signal?: AbortSignal,
) {
  const response = await fetch(
    `/api/runs/${runId}/context-manifests/${encodeURIComponent(manifestId)}`,
    { signal },
  );
  if (!response.ok) throw await responseError(response, 'context manifest');
  return response.json() as Promise<ChapterContextManifestRecord>;
}

export async function getChapterVersion(runId: string, chapterId: string, versionId: string, signal?: AbortSignal) {
  const response = await fetch(`/api/runs/${runId}/chapters/${encodeURIComponent(chapterId)}/versions/${encodeURIComponent(versionId)}`, { signal });
  if (!response.ok) throw await responseError(response, 'chapter version');
  return response.json() as Promise<{ artifact: Record<string, unknown> }>;
}

export async function createRunStream(workflow: WorkflowDefinition, inputs: RunInputs, signal?: AbortSignal, runId?: string) {
  if (!inputs.project_id) throw new RunApiError('A Run requires an active project', 422);
  const { export_preferences: exportPreferences, ...projectInputs } = inputs;
  if (!['md', 'json', 'zip'].includes(exportPreferences.format)) {
    throw new RunApiError('Export format must be md, json, or zip', 422);
  }
  const id = runId || `run-${crypto.randomUUID()}`;
  await postJson('/api/runs', {
    run_id: id,
    project_id: inputs.project_id,
    workflow_id: workflow.id,
    inputs: projectInputs,
    export_preferences: exportPreferences,
  }, signal);
  await postWithoutBody(`/api/runs/${id}/start`, signal);
  return fetch(`/api/runs/${id}/events?after=0`, { method: 'GET', signal });
}

export async function streamExistingRun(runId: string, signal?: AbortSignal, after = 0) {
  return fetch(`/api/runs/${runId}/events?after=${after}`, { method: 'GET', signal });
}

async function postWithoutBody(url: string, signal?: AbortSignal) {
  const response = await fetch(url, { method: 'POST', signal });
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
