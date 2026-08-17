import type {
  ChapterContextManifestRecord,
  GraphRunEnvelope,
  ProviderStageId,
  RunArtifactRecord,
  RunInputs,
  StageArtifactDraftRecord,
  WorkflowDefinition,
} from '../contracts';

export class RunApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = 'RunApiError';
  }
}

export async function getRun(runId: string, signal?: AbortSignal): Promise<GraphRunEnvelope> {
  const response = await fetch(`/api/runs/${runId}`, { signal });
  if (!response.ok) throw await responseError(response, `run ${runId}`);
  return response.json();
}

export type RunPresentationSnapshot = {
  committedArtifacts: RunArtifactRecord[];
  acceptedChapters: ChapterVersionRecord[];
  envelope: GraphRunEnvelope;
};

export type ChapterVersionRecord = {
  run_id: string;
  chapter_id: string;
  version_id: string;
  artifact: {
    chapter_id: string;
    version_id: string;
    title: string;
    content: string;
    author_status: string;
    [key: string]: unknown;
  };
  signature: string;
  created_at: string;
};

export async function getRunPresentationSnapshot(
  runId: string,
  signal?: AbortSignal,
): Promise<RunPresentationSnapshot> {
  const envelope = await getRun(runId, signal);
  const committedArtifacts = await Promise.all(
    Object.entries(envelope.read_model.artifact_refs).map(async ([stageId, artifactId]) => {
      const record = await getArtifactRecord(runId, artifactId, signal);
      if (
        record.run_id !== runId
        || record.artifact_id !== artifactId
        || record.stage_id !== stageId
        || record.status !== 'committed'
      ) {
        throw new RunApiError(`Run ${runId} has an invalid committed artifact snapshot`, 409);
      }
      return record;
    }),
  );
  const acceptedChapters = isTerminalRun(envelope.read_model.status)
    ? (await getRunChapters(runId, signal)).chapters.filter((record) => record.artifact.author_status === 'accepted')
    : [];
  return { acceptedChapters, committedArtifacts, envelope };
}

export async function getRunChapters(
  runId: string,
  signal?: AbortSignal,
): Promise<{ run_id: string; chapters: ChapterVersionRecord[] }> {
  const response = await fetch(`/api/runs/${runId}/chapters`, { signal });
  if (!response.ok) throw await responseError(response, 'run chapters');
  const payload = await response.json() as { run_id?: unknown; chapters?: unknown };
  if (payload.run_id !== runId || !Array.isArray(payload.chapters)) {
    throw new RunApiError(`Run ${runId} has an invalid chapter snapshot`, 409);
  }
  if (payload.chapters.some((record) => !isChapterVersionRecord(record))) {
    throw new RunApiError(`Run ${runId} has an invalid chapter version record`, 409);
  }
  return {
    run_id: runId,
    chapters: payload.chapters as ChapterVersionRecord[],
  };
}

function isTerminalRun(status: GraphRunEnvelope['read_model']['status']) {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

function isChapterVersionRecord(value: unknown): value is ChapterVersionRecord {
  if (!value || typeof value !== 'object') return false;
  const record = value as Partial<ChapterVersionRecord>;
  const artifact = record.artifact;
  return Boolean(
    typeof record.run_id === 'string'
    && typeof record.chapter_id === 'string'
    && typeof record.version_id === 'string'
    && typeof record.signature === 'string'
    && typeof record.created_at === 'string'
    && artifact
    && typeof artifact === 'object'
    && typeof artifact.chapter_id === 'string'
    && typeof artifact.version_id === 'string'
    && typeof artifact.title === 'string'
    && typeof artifact.content === 'string'
    && typeof artifact.author_status === 'string',
  );
}

export async function createRunBranch(
  sourceRunId: string,
  checkpointId: string,
  targetRunId = `run-${crypto.randomUUID()}`,
  bindingOverrideStages: ProviderStageId[] = [],
  signal?: AbortSignal,
) {
  const response = await postJson(`/api/runs/${sourceRunId}/branches`, {
    target_run_id: targetRunId,
    checkpoint_id: checkpointId,
    ...(bindingOverrideStages.length ? { binding_override_stages: bindingOverrideStages } : {}),
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
  return error instanceof RunApiError
    && (error.status === 404 || error.code === 'run_contract_retired');
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

export async function getStageArtifactDraft(
  runId: string,
  decisionId: string,
  signal?: AbortSignal,
): Promise<StageArtifactDraftRecord | null> {
  const response = await fetch(
    `/api/runs/${runId}/stage-drafts/${encodeURIComponent(decisionId)}`,
    { signal },
  );
  if (!response.ok) throw await responseError(response, 'stage Artifact draft');
  return response.json();
}

export async function saveStageArtifactDraft(
  runId: string,
  decisionId: string,
  domainRevision: number,
  sourceArtifactId: string,
  artifact: Record<string, unknown>,
): Promise<StageArtifactDraftRecord> {
  const response = await putJson(
    `/api/runs/${runId}/stage-drafts/${encodeURIComponent(decisionId)}`,
    {
      domain_revision: domainRevision,
      source_artifact_id: sourceArtifactId,
      artifact,
    },
  );
  return response.json();
}

export async function getArtifactRecord(
  runId: string,
  artifactId: string,
  signal?: AbortSignal,
): Promise<RunArtifactRecord> {
  const response = await fetch(`/api/runs/${runId}/artifact-records/${encodeURIComponent(artifactId)}`, { signal });
  if (!response.ok) throw await responseError(response, 'artifact record');
  return response.json();
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

async function putJson(url: string, body: unknown, signal?: AbortSignal) {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await responseError(response, url);
  return response;
}

async function responseError(response: Response, url: string) {
  let detail = '';
  let code: string | undefined;
  try {
    const payload = await response.json() as {
      detail?: unknown;
    };
    if (typeof payload.detail === 'string') {
      detail = payload.detail;
    } else if (payload.detail && typeof payload.detail === 'object') {
      const structured = payload.detail as { code?: unknown; message?: unknown };
      code = typeof structured.code === 'string' ? structured.code : undefined;
      detail = typeof structured.message === 'string' ? structured.message : '';
    }
  } catch {
    detail = '';
  }
  return new RunApiError(
    detail || `Request failed: ${url} ${response.status}`,
    response.status,
    code,
  );
}
