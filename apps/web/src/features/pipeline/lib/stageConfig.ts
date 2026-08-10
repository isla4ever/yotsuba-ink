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
  const latestInfo = events.find((event) => event.type === 'artifact.committed' && event.stage_id === 'info');
  const result = latestInfo?.payload;
  if (!result) return defaultWorldbuilding;

  const promise = recordFrom(result.story_promise);
  return {
    source: '创作立项 Artifact',
    seed: firstString(result.premise),
    rules: arrayFrom(result.world_rules) || [],
    tone: firstString(promise?.tone),
    impact: [firstString(result.thematic_question), firstString(result.ending_promise)].filter(Boolean),
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

function recordFrom(value: unknown) {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}
