import type { ProjectRecord, ProjectSummary } from '../contracts';
import { parseRunHistoryItem } from './runHistoryApi';

/** IO-only adapter for `/api/projects` (Phase 11.2 Studio Shell). */

export class ProjectApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ProjectApiError';
  }
}

export async function listProjects(signal?: AbortSignal): Promise<ProjectRecord[]> {
  const response = await fetch('/api/projects', { signal });
  if (!response.ok) throw await projectApiError(response, '/api/projects');
  const payload: unknown = await response.json();
  if (!Array.isArray(payload)) throw invalidProjectContract('/api/projects');
  return payload.map((item) => parseProject(item, '/api/projects'));
}

export async function createProject(input: {
  title: string;
  summary?: string;
  template_workflow_id?: string;
}): Promise<ProjectRecord> {
  const response = await fetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: input.title,
      summary: input.summary ?? '',
      template_workflow_id: input.template_workflow_id || 'default-novel-workflow',
    }),
  });
  if (!response.ok) throw await projectApiError(response, '/api/projects');
  return parseProject(await response.json(), '/api/projects');
}

export async function getProject(projectId: string, signal?: AbortSignal): Promise<ProjectRecord> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, { signal });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}`);
  return parseProject(await response.json(), `/api/projects/${projectId}`);
}

export async function patchProject(
  projectId: string,
  changes: Partial<Pick<ProjectRecord, 'title' | 'summary' | 'status' | 'accent_hue'>>,
): Promise<ProjectRecord> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}`);
  return parseProject(await response.json(), `/api/projects/${projectId}`);
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}`);
}

export async function getProjectSummary(projectId: string, signal?: AbortSignal): Promise<ProjectSummary> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/summary`, { signal });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}/summary`);
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== 'object') throw invalidProjectContract(`/api/projects/${projectId}/summary`);
  const record = payload as Partial<ProjectSummary>;
  if (
    typeof record.title !== 'string'
    || typeof record.status !== 'string'
    || !record.current_stage || typeof record.current_stage !== 'object'
    || !Array.isArray(record.completed_stage_ids) || !record.completed_stage_ids.every((item) => typeof item === 'string')
    || typeof record.words !== 'number' || !Number.isFinite(record.words)
    || typeof record.updated_at !== 'string'
    || (record.latest_run !== null && (typeof record.latest_run !== 'object' || !record.latest_run))
  ) throw invalidProjectContract(`/api/projects/${projectId}/summary`);
  return {
    project: parseProject(record.project, `/api/projects/${projectId}/summary`),
    latest_run: record.latest_run === null ? null : parseRunHistoryItem(record.latest_run),
    title: record.title,
    status: record.status,
    current_stage: record.current_stage,
    completed_stage_ids: record.completed_stage_ids,
    words: record.words,
    updated_at: record.updated_at,
  };
}

function parseProject(value: unknown, url: string): ProjectRecord {
  if (!value || typeof value !== 'object') throw invalidProjectContract(url);
  const record = value as Partial<ProjectRecord>;
  if (
    typeof record.id !== 'string' || !record.id
    || typeof record.title !== 'string' || !record.title
    || typeof record.summary !== 'string'
    || typeof record.accent_hue !== 'number' || record.accent_hue < 0 || record.accent_hue > 360
    || typeof record.workflow_id !== 'string' || !record.workflow_id
    || (record.status !== 'active' && record.status !== 'archived')
    || typeof record.created_at !== 'string'
    || typeof record.updated_at !== 'string'
    || typeof record.latest_run_id !== 'string'
  ) throw invalidProjectContract(url);
  return record as ProjectRecord;
}

function invalidProjectContract(url: string) {
  return new ProjectApiError(`Invalid Project API contract: ${url}`, 502);
}

async function projectApiError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    detail = '';
  }
  return new ProjectApiError(detail || `Request failed: ${url} ${response.status}`, response.status);
}
