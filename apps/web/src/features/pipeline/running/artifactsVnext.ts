export type ArtifactParseResult<T> = { artifact: T | null; errors: string[] };

export type LengthEnvelope = {
  word_target_soft: number | null;
  chapter_target_soft: number | null;
};

export type StoryBriefArtifact = {
  title: string;
  premise: string;
  promise: string;
  world_rules: string[];
  theme: string;
  ending_promise: string;
  voice: string;
  length_envelope: LengthEnvelope;
};

export type StorySpineArtifact = {
  turns: Array<{ id: string; cause: string; change: string }>;
  ending: string;
  open_questions: string[];
  progress_types: Array<'information' | 'relationship' | 'external' | 'internal'>;
};

export type VolumeArchitectureArtifact = {
  volumes: Array<{
    id: string;
    promise: string;
    conflict: string;
    climax: string;
    closure: string;
    turn_refs: string[];
    cast_ids: string[];
    thread_ids: string[];
    length_hint: 'short' | 'medium' | 'long';
  }>;
};

export type DetailArtifactVnext = {
  chapters: Array<{
    ref: string;
    volume_ref: string;
    purpose: string;
    pov: string;
    cast_ids: string[];
    scenes: Array<{ place: string; objective: string; conflict: string; turn: string; result: string }>;
    handoff: string;
  }>;
};

export type ChapterArtifactVnext = { chapter_id: string; version_id: string; title: string; content: string; author_status: 'candidate' | 'accepted' | 'edited' | 'branched' };
export type CoverBriefVnext = { concept: string; image_prompt: string; palette: string[]; negative_constraints: string[] };
export type CoverArtifactVnext = { brief: CoverBriefVnext; selected_asset_id: string };
export type ExportArtifactVnext = { format: 'md' | 'json' | 'zip'; chapter_version_ids: string[]; cover_asset_id: string; metadata: { title: string; author: string; version_note: string } };

type Schema = { type: 'string'; values?: readonly string[]; allowEmpty?: boolean } | { type: 'number'; integer?: boolean; min?: number; nullable?: boolean } | { type: 'array'; items: Schema; min?: number } | { type: 'object'; fields: Record<string, Schema> };
const string = (options: Omit<Extract<Schema, { type: 'string' }>, 'type'> = {}): Schema => ({ type: 'string', ...options });
const number = (options: Omit<Extract<Schema, { type: 'number' }>, 'type'> = {}): Schema => ({ type: 'number', ...options });
const array = (items: Schema, min = 0): Schema => ({ type: 'array', items, min });
const object = (fields: Record<string, Schema>): Schema => ({ type: 'object', fields });

const BRIEF_SCHEMA = object({ title: string(), premise: string(), promise: string(), world_rules: array(string(), 1), theme: string(), ending_promise: string(), voice: string(), length_envelope: object({ word_target_soft: number({ min: 1, integer: true, nullable: true }), chapter_target_soft: number({ min: 1, integer: true, nullable: true }) }) });
const SPINE_SCHEMA = object({ turns: array(object({ id: string(), cause: string(), change: string() }), 1), ending: string(), open_questions: array(string()), progress_types: array(string({ values: ['information', 'relationship', 'external', 'internal'] }), 1) });
const VOLUMES_SCHEMA = object({ volumes: array(object({ id: string(), promise: string(), conflict: string(), climax: string(), closure: string(), turn_refs: array(string(), 1), cast_ids: array(string(), 1), thread_ids: array(string()), length_hint: string({ values: ['short', 'medium', 'long'] }) }), 1) });
const DETAIL_SCHEMA = object({ chapters: array(object({ ref: string(), volume_ref: string(), purpose: string(), pov: string(), cast_ids: array(string(), 1), scenes: array(object({ place: string(), objective: string(), conflict: string(), turn: string(), result: string() }), 1), handoff: string() }), 1) });
const CHAPTER_SCHEMA = object({ chapter_id: string(), version_id: string(), title: string(), content: string(), author_status: string({ values: ['candidate', 'accepted', 'edited', 'branched'] }) });
const COVER_SCHEMA = object({ brief: object({ concept: string(), image_prompt: string(), palette: array(string(), 1), negative_constraints: array(string()) }), selected_asset_id: string({ allowEmpty: true }) });
const EXPORT_SCHEMA = object({ format: string({ values: ['md', 'json', 'zip'] }), chapter_version_ids: array(string(), 1), cover_asset_id: string({ allowEmpty: true }), metadata: object({ title: string(), author: string({ allowEmpty: true }), version_note: string({ allowEmpty: true }) }) });

export const parseStoryBriefArtifact = (source: string) => parseArtifact<StoryBriefArtifact>(source, BRIEF_SCHEMA);
export const parseSpineArtifact = (source: string) => parseArtifact<StorySpineArtifact>(source, SPINE_SCHEMA, validateOrderedIdentity('turns', 'turn', 'id'));
export const parseVolumesArtifact = (source: string) => parseArtifact<VolumeArchitectureArtifact>(source, VOLUMES_SCHEMA, validateOrderedIdentity('volumes', 'volume', 'id'));
export const parseDetailArtifact = (source: string) => parseArtifact<DetailArtifactVnext>(source, DETAIL_SCHEMA, (value, errors) => {
  validateOrderedIdentity('chapters', 'chapter', 'ref')(value, errors);
  if (!isRecord(value) || !Array.isArray(value.chapters)) return;
  value.chapters.forEach((item) => {
    if (!isRecord(item) || !Array.isArray(item.cast_ids) || typeof item.pov !== 'string') return;
    if (new Set(item.cast_ids).size !== item.cast_ids.length) errors.push(`${String(item.ref)} 的出场人物不能重复`);
    if (!item.cast_ids.includes(item.pov)) errors.push(`${String(item.ref)} 的出场人物必须包含 POV`);
  });
});
export const parseChapterArtifact = (source: string) => parseArtifact<ChapterArtifactVnext>(source, CHAPTER_SCHEMA);
export const parseCoverArtifact = (source: string) => parseArtifact<CoverArtifactVnext>(source, COVER_SCHEMA);
export const parseExportArtifact = (source: string) => parseArtifact<ExportArtifactVnext>(source, EXPORT_SCHEMA);

export function artifactReadiness<T>(result: ArtifactParseResult<T>) { const missingLabels = result.artifact ? [] : [result.errors[0] ?? '有效阶段产物']; return { completed: missingLabels.length ? 0 : 1, missingLabels, ready: !missingLabels.length, total: 1 }; }
export function coverArtifactReadiness(result: ArtifactParseResult<CoverArtifactVnext>) { const missingLabels = result.artifact ? (result.artifact.selected_asset_id ? [] : ['正式封面候选']) : [result.errors[0] ?? '有效封面产物']; return { completed: missingLabels.length ? 0 : 1, missingLabels, ready: !missingLabels.length, total: 1 }; }

function parseArtifact<T>(source: string, schema: Schema, semantic?: (value: unknown, errors: string[]) => void): ArtifactParseResult<T> {
  let value: unknown;
  try { value = JSON.parse(source); } catch { return { artifact: null, errors: ['阶段产物不是有效 JSON'] }; }
  const errors: string[] = [];
  validateSchema(value, schema, 'artifact', errors);
  semantic?.(value, errors);
  return errors.length ? { artifact: null, errors } : { artifact: value as T, errors: [] };
}

function validateSchema(value: unknown, schema: Schema, path: string, errors: string[]) {
  if (schema.type === 'string') { if (typeof value !== 'string' || (!schema.allowEmpty && !value.trim())) errors.push(`${path} 必须是非空字符串`); else if (schema.values && !schema.values.includes(value)) errors.push(`${path} 不在允许值内`); return; }
  if (schema.type === 'number') { if (value === null && schema.nullable) return; if (typeof value !== 'number' || !Number.isFinite(value)) errors.push(`${path} 必须是数字`); else if (schema.integer && !Number.isInteger(value)) errors.push(`${path} 必须是整数`); else if (schema.min !== undefined && value < schema.min) errors.push(`${path} 不能小于 ${schema.min}`); return; }
  if (schema.type === 'array') { if (!Array.isArray(value)) { errors.push(`${path} 必须是数组`); return; } if (schema.min && value.length < schema.min) errors.push(`${path} 至少包含 ${schema.min} 项`); value.forEach((item, index) => validateSchema(item, schema.items, `${path}[${index}]`, errors)); return; }
  if (!isRecord(value)) { errors.push(`${path} 必须是对象`); return; }
  const expected = Object.keys(schema.fields); const unknown = Object.keys(value).filter((key) => !expected.includes(key)); const missing = expected.filter((key) => !(key in value));
  if (unknown.length) errors.push(`${path} 包含未支持字段：${unknown.join('、')}`); if (missing.length) errors.push(`${path} 缺少字段：${missing.join('、')}`); expected.forEach((key) => { if (key in value) validateSchema(value[key], schema.fields[key], `${path}.${key}`, errors); });
}

function validateOrderedIdentity(field: string, prefix: string, identityKey: string) { return (value: unknown, errors: string[]) => { if (!isRecord(value) || !Array.isArray(value[field])) return; const ids = value[field].map((item) => isRecord(item) ? item[identityKey] : null); ids.forEach((id, index) => { if (id !== `${prefix}-${index + 1}`) errors.push(`${field} 的 ID 必须连续`); }); }; }
function isRecord(value: unknown): value is Record<string, any> { return Boolean(value) && typeof value === 'object' && !Array.isArray(value); }
