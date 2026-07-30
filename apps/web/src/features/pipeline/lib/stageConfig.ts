import type { InputField, RunEvent, WorkflowStage } from '../contracts';

export type WorldbuildingView = {
  source: string;
  seed: string;
  rules: string[];
  tone: string;
  impact: string[];
};

export const defaultWorldbuilding: WorldbuildingView = {
  source: '等待产物',
  seed: '',
  rules: [],
  tone: '',
  impact: [],
};

export function worldbuildingFromDraft(detail: string): WorldbuildingView {
  const lines = detail.split(/\n|；|;/).map((item) => item.trim()).filter(Boolean);
  return {
    ...defaultWorldbuilding,
    source: '推荐草稿',
    seed: detail.trim(),
    rules: lines.slice(0, 4),
  };
}

export function updateStageInputDefault(stage: WorkflowStage, key: string, value: unknown): WorkflowStage {
  return {
    ...stage,
    input_schema: stage.input_schema.map((field) => (field.key === key ? { ...field, default: value } : field)),
  };
}

/**
 * Phase 12 B2: the brief keeps a single length control. The user picks the
 * word-count range (the finer choice); the coarse `target_length` tier is
 * derived from it so both prompt inputs stay consistent without asking twice.
 */
export const targetLengthByWordsRange: Record<string, string> = {
  '1-3 万字': '短篇',
  '5-10 万字': '中篇',
  '20-40 万字': '长篇',
  '80-120 万字': '长篇',
  '120 万字以上': '系列长篇',
};

export function applyTargetWordsRange(stage: WorkflowStage, range: string): WorkflowStage {
  const next = updateStageInputDefault(stage, 'target_words_range', range);
  const derived = targetLengthByWordsRange[range];
  return derived ? updateStageInputDefault(next, 'target_length', derived) : next;
}

export function parseTagInput(value: string) {
  return value
    .split(/[,\n，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function addTagValue(value: unknown, next: string) {
  const current = Array.isArray(value) ? value.map(String) : parseTagInput(String(value ?? ''));
  const incoming = parseTagInput(next);
  return Array.from(new Set([...current, ...incoming]));
}

export function removeTagValue(value: unknown, tag: string) {
  const current = Array.isArray(value) ? value.map(String) : parseTagInput(String(value ?? ''));
  return current.filter((item) => item !== tag);
}

export function clampQualityScore(value: number, min = 0.6, max = 0.95) {
  if (Number.isNaN(value)) return min;
  return Math.min(max, Math.max(min, value));
}

export function formatTagInput(value: unknown) {
  if (Array.isArray(value)) return value.map(String).join('、');
  return String(value ?? '');
}

export function coerceFieldValue(field: InputField, raw: string | boolean) {
  if (field.type === 'boolean') return Boolean(raw);
  const value = String(raw);
  if (field.type === 'number') return Number(value);
  if (field.type === 'tags') return parseTagInput(value);
  return value;
}

export function extractWorldbuilding(events: RunEvent[]): WorldbuildingView {
  const latestInfo = events.find((event) => event.type === 'node_completed' && event.node_type === 'info_recommend');
  const result = latestInfo?.result;
  if (!result) return defaultWorldbuilding;

  if (typeof result === 'object' && result !== null) {
    const record = result as Record<string, unknown>;
    const seed = firstString(record.worldbuilding_detail, record.worldbuilding, record.world, record.world_seed);
    return {
      source: '小说推荐产物',
      seed,
      rules: arrayFrom(record.rules, record.constraints, record.hard_settings) || parseTagInput(seed),
      tone: firstString(record.tone, record.style, record.genre),
      impact: arrayFrom(record.impact, record.downstream_effects) || [],
    };
  }

  const text = String(result);
  return {
    ...defaultWorldbuilding,
    source: '小说推荐产物',
    seed: text.length > 180 ? `${text.slice(0, 180)}...` : text,
  };
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function arrayFrom(...values: unknown[]) {
  for (const value of values) {
    if (Array.isArray(value) && value.length) return value.map(String);
    if (typeof value === 'string' && value.trim()) return parseTagInput(value);
  }
  return null;
}
