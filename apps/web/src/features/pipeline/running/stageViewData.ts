export function deltasBySection(deltas: Array<{ section: string; delta: string }>) {
  const map = new Map<string, string>();
  deltas.forEach((item) => {
    map.set(item.section, [map.get(item.section), item.delta].filter(Boolean).join('\n'));
  });
  return map;
}

export function activeIndexFor(names: string[], deltas: Map<string, string>) {
  for (let index = names.length - 1; index >= 0; index -= 1) {
    if (deltas.has(names[index])) return index;
  }
  return 0;
}

export function listText(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => valueText(item)).filter(Boolean);
  const text = String(value ?? '').trim();
  return text ? text.split(/\n+/).map((item) => item.trim()).filter(Boolean) : [];
}

export function valueText(value: unknown): string {
  if (value == null) return '';
  if (Array.isArray(value)) return value.map((item) => valueText(item)).filter(Boolean).join('；');
  if (typeof value !== 'object') return String(value).trim();
  const record = value as Record<string, unknown>;
  if ('character' in record || 'change' in record) {
    return [record.character, record.change].map((item) => valueText(item)).filter(Boolean).join('：');
  }
  if ('anchor' in record || 'reveal' in record) {
    return [record.anchor, record.reveal].map((item) => valueText(item)).filter(Boolean).join('：');
  }
  if ('name' in record || 'status' in record || 'chapter_range' in record || 'target_chapter' in record || 'note' in record) {
    const head = [record.chapter_range ?? record.target_chapter, record.status, record.name]
      .map((item) => valueText(item)).filter(Boolean).join(' ');
    return [head, valueText(record.note)].filter(Boolean).join('：');
  }
  return Object.entries(record)
    .filter(([key]) => !INTERNAL_PREVIEW_KEYS.has(key))
    .map(([key, item]) => {
      const text = valueText(item);
      if (!text) return '';
      const label = PREVIEW_LABELS[key];
      return label ? `${label}：${text}` : text;
    })
    .filter(Boolean)
    .join('；');
}

const INTERNAL_PREVIEW_KEYS = new Set(['id', 'schema_version', 'artifact_signature', 'commit_signature', 'candidate_signature']);

const PREVIEW_LABELS: Record<string, string> = {
  character: '人物',
  change: '变化',
  impact: '后续影响',
  motivation: '动机',
  pressure: '关系压力',
  relation: '关系',
  related_to: '关系对象',
  rule: '规则限制',
};

export function firstText(value: unknown) {
  return listText(value)[0] ?? '';
}

export function splitLines(value: unknown) {
  return String(value ?? '').split(/\n+/).map((item) => item.trim()).filter(Boolean);
}
