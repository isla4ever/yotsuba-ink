import type { ProjectRecord } from '../contracts';

/**
 * Phase 11.2 singleton-mine fix: all per-workspace localStorage keys become
 * project-scoped. Empty scope means the legacy "unarchived" session and keeps
 * reading/writing the historical unscoped keys, so pre-Studio data is never
 * lost — it simply lives on as the unarchived workspace.
 */

export const activeProjectStorageKey = 'novel-workflow-active-project';
export const archivedRunLinksStorageKey = 'novel-workflow-archived-run-links';

let storageProjectScope = '';

export function setStorageProjectScope(projectId: string) {
  storageProjectScope = projectId ?? '';
}

export function currentStorageProjectScope() {
  return storageProjectScope;
}

/**
 * Legacy migration semantics: scoped keys are `{base}:{projectId}`; the bare
 * legacy key stays owned by the unarchived session (scope '').
 */
export function storageScopedKey(base: string, projectId = storageProjectScope) {
  return projectId ? `${base}:${projectId}` : base;
}

export function loadActiveProjectLocally(): ProjectRecord | null {
  try {
    const stored = window.localStorage.getItem(activeProjectStorageKey);
    const parsed = stored ? JSON.parse(stored) as Partial<ProjectRecord> : null;
    if (!parsed || typeof parsed !== 'object' || !parsed.id || !parsed.workflow_id) return null;
    return normalizeProjectRecord(parsed);
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

export function normalizeProjectRecord(value: Partial<ProjectRecord>): ProjectRecord {
  return {
    id: String(value.id || ''),
    title: String(value.title || '未命名作品'),
    summary: String(value.summary || ''),
    accent_hue: clampHue(Number(value.accent_hue)),
    workflow_id: String(value.workflow_id || ''),
    status: value.status === 'archived' ? 'archived' : 'active',
    created_at: String(value.created_at || ''),
    updated_at: String(value.updated_at || ''),
    latest_run_id: String(value.latest_run_id || ''),
  };
}

/**
 * Archived-run links: run_id -> project_id, recorded when the user archives a
 * legacy run (project_id == run_id) into a real project. The backend cannot
 * backfill old run records, so this association is a local UI affordance —
 * the historical run stays stored exactly as it was.
 */
export function loadArchivedRunLinks(): Record<string, string> {
  try {
    const stored = window.localStorage.getItem(archivedRunLinksStorageKey);
    const parsed = stored ? JSON.parse(stored) : null;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>)
        .filter(([runId, projectId]) => runId && typeof projectId === 'string' && projectId)
        .map(([runId, projectId]) => [runId, String(projectId)]),
    );
  } catch {
    return {};
  }
}

export function saveArchivedRunLink(runId: string, projectId: string) {
  if (!runId || !projectId) return;
  try {
    window.localStorage.setItem(
      archivedRunLinksStorageKey,
      JSON.stringify({ ...loadArchivedRunLinks(), [runId]: projectId }),
    );
  } catch {
    // Association is a convenience; archiving still succeeded server-side.
  }
}

/** Resolves the owning project for an opened run (mine 5): snapshot project_id, archived link, else unarchived (''). */
export function projectIdForRun(snapshotProjectId: string | undefined, runId: string, links = loadArchivedRunLinks()): string {
  const projectId = String(snapshotProjectId || '');
  if (projectId && projectId !== runId) return projectId;
  return links[runId] ?? '';
}

function clampHue(value: number) {
  if (Number.isNaN(value)) return 212;
  return Math.min(360, Math.max(0, Math.round(value)));
}
