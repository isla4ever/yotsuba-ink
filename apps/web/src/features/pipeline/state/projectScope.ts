import type { ProjectRecord } from '../contracts';

/** Project-scoped local persistence for the active Yotsuba Ink workspace. */

export const activeProjectStorageKey = 'novel-workflow-active-project';

let storageProjectScope = '';

export function setStorageProjectScope(projectId: string) {
  storageProjectScope = projectId ?? '';
}

export function currentStorageProjectScope() {
  return storageProjectScope;
}

export function storageScopedKey(base: string, projectId = storageProjectScope) {
  if (!projectId) throw new Error('Project-scoped storage requires an active project');
  return `${base}:${projectId}`;
}

export function loadActiveProjectLocally(): ProjectRecord | null {
  try {
    const stored = window.localStorage.getItem(activeProjectStorageKey);
    const parsed = stored ? JSON.parse(stored) as Partial<ProjectRecord> : null;
    return isProjectRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveActiveProjectLocally(project: ProjectRecord | null) {
  try {
    if (!project) window.localStorage.removeItem(activeProjectStorageKey);
    else window.localStorage.setItem(activeProjectStorageKey, JSON.stringify(project));
  } catch {
    // The in-memory active project keeps working when persistence is unavailable.
  }
}

function isProjectRecord(value: Partial<ProjectRecord> | null): value is ProjectRecord {
  return Boolean(
    value
    && typeof value.id === 'string' && value.id.length > 0
    && typeof value.title === 'string' && value.title.length > 0
    && typeof value.summary === 'string'
    && typeof value.accent_hue === 'number' && value.accent_hue >= 0 && value.accent_hue <= 360
    && typeof value.workflow_id === 'string' && value.workflow_id.length > 0
    && (value.status === 'active' || value.status === 'archived')
    && typeof value.created_at === 'string'
    && typeof value.updated_at === 'string'
    && typeof value.latest_run_id === 'string'
  );
}
