export function parseArtifactRecord(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function text(value: unknown, fallback: string) {
  const next = String(value ?? '').trim();
  return next || fallback;
}

export function list(value: unknown, fallback: string[]) {
  if (Array.isArray(value)) {
    const items = value.map((item) => String(item ?? '').trim()).filter(Boolean);
    if (items.length) return items;
  }
  return fallback;
}

export function objectList<T extends object>(value: unknown, fallback: T[]): T[] {
  if (Array.isArray(value)) {
    const items = value.filter((item): item is T => Boolean(item) && typeof item === 'object' && !Array.isArray(item));
    if (items.length) return items;
  }
  return fallback;
}

export function objectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function numberValue(value: unknown, fallback: number) {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}
