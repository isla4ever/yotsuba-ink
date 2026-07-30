const UNAVAILABLE_PREVIEW = '候选产物已生成，当前结构暂不支持内容预览。';

export function candidatePreviewText(value: unknown, fallback?: unknown) {
  const fallbackText = plainText(fallback);
  if (fallbackText) return fallbackText;
  return structuredPreview(value) || UNAVAILABLE_PREVIEW;
}

function structuredPreview(value: unknown): string {
  const text = plainText(value);
  if (text) return text;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '';
  const record = value as Record<string, unknown>;
  const nested = record.artifact;
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    const preview = structuredPreview(nested);
    if (preview) return preview;
  }

  const title = firstString(record.selected_title, record.title, record.chapter_title);
  const body = firstString(
    record.content,
    record.full_synopsis,
    record.synopsis,
    record.one_liner,
    record.brief,
    record.composition,
    record.summary,
    record.goal,
    record.volume_goal,
  );
  if (title || body) return [title, body].filter(Boolean).join('\n');

  const volumes = listPreview(record.volumes, ['title', 'volume_goal']);
  if (volumes) return volumes;
  return listPreview(record.chapters, ['title', 'chapter', 'goal', 'content']);
}

function listPreview(value: unknown, keys: string[]) {
  if (!Array.isArray(value)) return '';
  return value
    .slice(0, 3)
    .map((item) => {
      if (!item || typeof item !== 'object' || Array.isArray(item)) return plainText(item);
      const record = item as Record<string, unknown>;
      return firstString(...keys.map((key) => record[key]));
    })
    .filter(Boolean)
    .join('\n');
}

function firstString(...values: unknown[]) {
  return values.map((value) => plainText(value)).find(Boolean) ?? '';
}

function plainText(value: unknown) {
  if (typeof value !== 'string') return '';
  const text = value.trim();
  if (!text || text === '[object Object]' || looksLikeStructuredDump(text)) return '';
  return text;
}

function looksLikeStructuredDump(value: string) {
  if (!((value.startsWith('{') && value.endsWith('}')) || (value.startsWith('[') && value.endsWith(']')))) return false;
  try {
    const parsed = JSON.parse(value);
    return Boolean(parsed && typeof parsed === 'object');
  } catch {
    return true;
  }
}
