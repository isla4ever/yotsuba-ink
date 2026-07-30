export const infoApprovalDraftStoragePrefix = 'novel-workflow-info-approval-draft';

export type InfoApprovalDraftStorage = Pick<Storage, 'getItem' | 'removeItem' | 'setItem'>;

type StoredInfoApprovalDraft = {
  draft: string;
  run_id: string;
  source_artifact: string;
  source_signature: string;
  version: 1;
};

export function infoApprovalSourceSignature(source: string) {
  const canonical = canonicalArtifact(source);
  let first = 2166136261;
  let second = 2246822507;
  for (let index = 0; index < canonical.length; index += 1) {
    const code = canonical.charCodeAt(index);
    first = Math.imul(first ^ code, 16777619);
    second = Math.imul(second ^ code, 3266489909);
  }
  return `${(first >>> 0).toString(36)}-${(second >>> 0).toString(36)}`;
}

export function loadInfoApprovalDraft(
  runId: string,
  source: string,
  storage: InfoApprovalDraftStorage | null = browserStorage(),
) {
  if (!runId || !source || !storage) return '';
  const key = storageKey(runId);
  try {
    const raw = storage.getItem(key);
    if (!raw) return '';
    const stored = JSON.parse(raw) as Partial<StoredInfoApprovalDraft>;
    const sourceArtifact = canonicalArtifact(source);
    if (
      stored.version !== 1
      || stored.run_id !== runId
      || stored.source_signature !== infoApprovalSourceSignature(source)
      || stored.source_artifact !== sourceArtifact
      || typeof stored.draft !== 'string'
    ) {
      storage.removeItem(key);
      return '';
    }
    return stored.draft;
  } catch {
    storage.removeItem(key);
    return '';
  }
}

export function saveInfoApprovalDraft(
  runId: string,
  source: string,
  draft: string,
  storage: InfoApprovalDraftStorage | null = browserStorage(),
) {
  if (!runId || !source || !storage) return;
  const key = storageKey(runId);
  try {
    if (canonicalArtifact(source) === canonicalArtifact(draft)) {
      storage.removeItem(key);
      return;
    }
    storage.setItem(key, JSON.stringify({
      draft,
      run_id: runId,
      source_artifact: canonicalArtifact(source),
      source_signature: infoApprovalSourceSignature(source),
      version: 1,
    } satisfies StoredInfoApprovalDraft));
  } catch {
    // The server approval artifact remains the fallback when local storage is unavailable.
  }
}

export function clearInfoApprovalDraft(
  runId: string,
  storage: InfoApprovalDraftStorage | null = browserStorage(),
) {
  if (!runId || !storage) return;
  try {
    storage.removeItem(storageKey(runId));
  } catch {
    // Clearing a best-effort local draft must not block run reset or approval.
  }
}

function canonicalArtifact(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return '';
  try {
    return JSON.stringify(sortValue(JSON.parse(trimmed)));
  } catch {
    return trimmed;
  }
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, entry]) => [key, sortValue(entry)]));
}

function storageKey(runId: string) {
  return `${infoApprovalDraftStoragePrefix}:${encodeURIComponent(runId)}`;
}

function browserStorage() {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}
