import type { ProjectRecord, ProjectSummary, RunHistoryItem } from '../contracts';

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
  const payload = await response.json();
  return Array.isArray(payload) ? payload.map(normalizeProject) : [];
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
  return normalizeProject(await response.json());
}

export async function getProject(projectId: string, signal?: AbortSignal): Promise<ProjectRecord> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, { signal });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}`);
  return normalizeProject(await response.json());
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
  return normalizeProject(await response.json());
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}`);
}

export async function getProjectSummary(projectId: string, signal?: AbortSignal): Promise<ProjectSummary> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/summary`, { signal });
  if (!response.ok) throw await projectApiError(response, `/api/projects/${projectId}/summary`);
  const payload = await response.json() as Partial<ProjectSummary>;
  const stage = payload.current_stage && typeof payload.current_stage === 'object' ? payload.current_stage : {};
  return {
    project: normalizeProject(payload.project ?? {}),
    latest_run: (payload.latest_run && typeof payload.latest_run === 'object' ? payload.latest_run as RunHistoryItem : null),
    title: String(payload.title || ''),
    status: String(payload.status || ''),
    current_stage: stage,
    completed_stage_ids: Array.isArray(payload.completed_stage_ids) ? payload.completed_stage_ids.map(String) : [],
    words: Number(payload.words || 0),
    updated_at: String(payload.updated_at || ''),
  };
}

function normalizeProject(value: unknown): ProjectRecord {
  const record = value && typeof value === 'object' ? value as Partial<ProjectRecord> : {};
  return {
    id: String(record.id || ''),
    title: String(record.title || '未命名作品'),
    summary: String(record.summary || ''),
    accent_hue: Number.isFinite(Number(record.accent_hue)) ? Number(record.accent_hue) : 212,
    workflow_id: String(record.workflow_id || ''),
    status: record.status === 'archived' ? 'archived' : 'active',
    created_at: String(record.created_at || ''),
    updated_at: String(record.updated_at || ''),
    latest_run_id: String(record.latest_run_id || ''),
  };
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
