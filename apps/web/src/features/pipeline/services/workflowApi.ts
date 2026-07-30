import type { WorkflowDefinition } from '../contracts';

const LOCAL_WORKFLOW_KEY = 'novel-workflow-demo-workflow-definition';

export class WorkflowApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'WorkflowApiError';
  }
}

export async function getDefaultWorkflowDefinition(): Promise<WorkflowDefinition> {
  const response = await fetch('/api/workflows/default');
  if (!response.ok) throw new Error(`Workflow load failed: ${response.status}`);
  return response.json();
}

/** Phase 11.2: per-project workflow load (mine 2 — no longer only /default). */
export async function getWorkflowDefinitionById(workflowId: string): Promise<WorkflowDefinition> {
  const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}`);
  if (!response.ok) throw await workflowApiError(response, `/api/workflows/${workflowId}`);
  return response.json();
}

export async function listWorkflowDefinitions(signal?: AbortSignal): Promise<WorkflowDefinition[]> {
  const response = await fetch('/api/workflows', { signal });
  if (!response.ok) throw await workflowApiError(response, '/api/workflows');
  const payload = await response.json();
  return Array.isArray(payload) ? payload as WorkflowDefinition[] : [];
}

export async function duplicateWorkflowDefinition(
  workflowId: string,
  options: { new_id?: string; name?: string; is_template?: boolean } = {},
): Promise<WorkflowDefinition> {
  const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}/duplicate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  if (!response.ok) throw await workflowApiError(response, `/api/workflows/${workflowId}/duplicate`);
  return response.json();
}

export async function deleteWorkflowDefinition(workflowId: string): Promise<void> {
  const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}`, { method: 'DELETE' });
  if (!response.ok) throw await workflowApiError(response, `/api/workflows/${workflowId}`);
}

/** POST upsert: saves whichever workflow id is in the payload (per-project workflows included). */
export async function saveWorkflowDefinition(workflow: WorkflowDefinition) {
  saveWorkflowLocally(workflow);
  const response = await fetch('/api/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(workflow),
  });
  if (!response.ok) throw new Error(`Workflow save failed: ${response.status}`);
}

async function workflowApiError(response: Response, url: string) {
  let detail = '';
  try {
    const payload = await response.json() as { detail?: unknown };
    detail = typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    detail = '';
  }
  return new WorkflowApiError(detail || `Request failed: ${url} ${response.status}`, response.status);
}

function saveWorkflowLocally(workflow: WorkflowDefinition) {
  try {
    window.localStorage.setItem(LOCAL_WORKFLOW_KEY, JSON.stringify(workflow));
  } catch {
    // Frontend demo mode must not block the planning surface when persistence is unavailable.
  }
}
