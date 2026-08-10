import type {
  GraphRunEnvelope,
  RunInputs,
  WorkflowDefinition,
} from '../contracts';
import { buildBookScalePlan } from '../lib/bookScalePlan';

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

export async function getChapterVersion(runId: string, chapterId: string, versionId: string, signal?: AbortSignal) {
  const response = await fetch(`/api/runs/${runId}/chapters/${encodeURIComponent(chapterId)}/versions/${encodeURIComponent(versionId)}`, { signal });
  if (!response.ok) throw await responseError(response, 'chapter version');
  return response.json() as Promise<{ artifact: Record<string, unknown> }>;
}

export async function createRunStream(workflow: WorkflowDefinition, inputs: RunInputs, signal?: AbortSignal, runId?: string) {
  if (!inputs.project_id) throw new RunApiError('A Run requires an active project', 422);
  const target = 'book_scale_plan' in inputs
    ? inputs.book_scale_plan
    : buildBookScalePlan(inputs.book_scale_target.target_mode, inputs.book_scale_target.target_value);
  const providerBindings = Object.fromEntries(workflow.nodes
    .filter((stage) => stage.id !== 'export')
    .map((stage) => [stage.id, {
      provider_profile_id: stage.provider_profile_id,
      model: stage.model_settings.model,
      temperature: stage.model_settings.temperature,
      max_tokens: stage.model_settings.max_tokens,
      top_p: stage.model_settings.top_p,
      timeout_seconds: stage.model_settings.timeout_seconds,
      prompt_template: workflow.prompt_templates.find((item) => item.id === stage.prompt_template_id)?.content ?? '',
    }]));
  const coverStage = workflow.nodes.find((stage) => stage.id === 'cover');
  const imageProvider = workflow.provider_profiles.find((provider) => (
    provider.kind === 'openai-compatible-image'
    && provider.id === coverStage?.image_provider_profile_id
  ));
  if (!coverStage?.image_provider_profile_id || !imageProvider?.default_model) {
    throw new RunApiError('Cover requires an explicit image Provider and model', 422);
  }
  const coverConfig = Object.fromEntries(coverStage.input_schema.map((field) => [field.key, field.default]));
  const candidateCount = Number(coverConfig.candidate_count);
  const imageSize = String(coverConfig.image_size ?? '');
  const imageQuality = String(coverConfig.image_quality ?? '');
  if (!Number.isInteger(candidateCount) || candidateCount < 1 || candidateCount > 4) {
    throw new RunApiError('Cover candidate count must be between 1 and 4', 422);
  }
  if (!/^[1-9][0-9]{2,3}x[1-9][0-9]{2,3}$/.test(imageSize)) {
    throw new RunApiError('Cover image size is invalid', 422);
  }
  if (!['low', 'medium', 'high'].includes(imageQuality)) {
    throw new RunApiError('Cover image quality is invalid', 422);
  }
  const { export_preferences: exportPreferences, ...projectInputs } = inputs;
  if (!['md', 'json', 'zip'].includes(exportPreferences.format)) {
    throw new RunApiError('Export format must be md, json, or zip', 422);
  }
  const id = runId || `run-${crypto.randomUUID()}`;
  await postJson('/api/runs', {
    run_id: id,
    project_id: inputs.project_id,
    workflow_revision: workflow.version,
    quality_mode: inputs.quality_mode,
    inputs: projectInputs,
    book_scale_plan: target,
    provider_bindings: providerBindings,
    cover_asset_binding: {
      provider_profile_id: coverStage.image_provider_profile_id,
      model: imageProvider.default_model,
      candidate_count: candidateCount,
      size: imageSize,
      quality: imageQuality,
      timeout_seconds: 180,
      failure_policy: 'fail_run',
    },
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
