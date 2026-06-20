import type { InputField, RunEvent, WorkflowStage } from '../contracts';

export type WorldbuildingView = {
  source: string;
  seed: string;
  rules: string[];
  tone: string;
  impact: string[];
};

const defaultWorldbuilding: WorldbuildingView = {
  source: '默认草案',
  seed: '旧港城市被多年前的记忆实验影响，人物对同一事件保留互相矛盾的片段。',
  rules: ['记忆不能凭空改写事实，只能改变人物对事实的理解', '旧案线索必须能回扣到港口、档案馆或实验室', '人物关系变化要优先服从已建立动机'],
  tone: '悬疑、冷调、群像推进，强调信息差和旧案回声。',
  impact: ['约束梗概主线不要脱离旧港旧案', '约束大纲持续推进人物关系与伏笔回收', '约束正文保持记忆线索的一致性'],
};

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
  const latestInfo = events.find((event) => event.type === 'node_completed' && event.node_type === 'info_recommend');
  const result = latestInfo?.result;
  if (!result) return defaultWorldbuilding;

  if (typeof result === 'object' && result !== null) {
    const record = result as Record<string, unknown>;
    const seed = firstString(record.world_seed, record.worldbuilding, record.world, record.summary);
    return {
      source: '小说推荐产物',
      seed: seed || defaultWorldbuilding.seed,
      rules: arrayFrom(record.rules, record.constraints, record.hard_settings) || defaultWorldbuilding.rules,
      tone: firstString(record.tone, record.style, record.genre) || defaultWorldbuilding.tone,
      impact: arrayFrom(record.impact, record.downstream_effects) || defaultWorldbuilding.impact,
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
