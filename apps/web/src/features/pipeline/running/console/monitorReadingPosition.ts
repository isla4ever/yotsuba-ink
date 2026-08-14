import type { MonitorSelection } from './MonitorSidebar';

const storageKey = 'novel-workflow-monitor-reading-position';

type StoredPositions = Record<string, MonitorSelection>;

function readAll(): StoredPositions {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? (parsed as StoredPositions) : {};
  } catch {
    return {};
  }
}

/** Reopening a book resumes where the author left off instead of snapping to live progress. */
export function loadReadingPosition(runId: string): MonitorSelection | null {
  if (!runId) return null;
  const entry = readAll()[runId];
  if (!entry) return null;
  if (entry.kind === 'chapter' && typeof entry.chapterRef === 'string') return entry;
  if (entry.kind === 'stage' && typeof entry.stageId === 'string') return entry;
  return null;
}

export function saveReadingPosition(runId: string, selection: MonitorSelection | null) {
  if (!runId || typeof window === 'undefined') return;
  try {
    const all = readAll();
    if (selection) all[runId] = selection;
    else delete all[runId];
    window.localStorage.setItem(storageKey, JSON.stringify(all));
  } catch {
    // Reading position is a convenience; storage failures must not break the console.
  }
}
