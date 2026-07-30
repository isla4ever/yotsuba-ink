export type DetailDraftRow<T> = {
  id: string;
  value: T;
};

let nextLocalRowId = 0;

export function createDetailDraftRows<T>(scope: string, values: T[]): DetailDraftRow<T>[] {
  const occurrences = new Map<string, number>();
  return values.map((value) => {
    const signature = stableSignature(value);
    const occurrence = (occurrences.get(signature) ?? 0) + 1;
    occurrences.set(signature, occurrence);
    return {
      id: `${scope}-${hashSignature(signature)}-${occurrence}`,
      value: structuredClone(value),
    };
  });
}

export function appendDetailDraftRow<T>(rows: DetailDraftRow<T>[], scope: string, value: T) {
  nextLocalRowId += 1;
  return [...rows, { id: `${scope}-new-${nextLocalRowId}`, value: structuredClone(value) }];
}

export function updateDetailDraftRow<T>(rows: DetailDraftRow<T>[], id: string, value: T) {
  return rows.map((row) => row.id === id ? { ...row, value } : row);
}

export function removeDetailDraftRow<T>(rows: DetailDraftRow<T>[], id: string) {
  return rows.filter((row) => row.id !== id);
}

export function detailDraftValues<T>(rows: DetailDraftRow<T>[]) {
  return rows.map((row) => structuredClone(row.value));
}

function stableSignature(value: unknown) {
  return JSON.stringify(sortValue(value));
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, entry]) => [key, sortValue(entry)]));
}

function hashSignature(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}
