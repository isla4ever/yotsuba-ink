export type ArtifactParseResult<T> = { artifact: T | null; errors: string[] };

export type StoryBriefArtifact = {
  title: string;
  premise: string;
  story_promise: { genre: string; audience: string; tone: string };
  world_rules: string[];
  thematic_question: string;
  ending_promise: string;
  voice: { viewpoint: string; tense: string; texture: string; avoid: string[] };
  cast_requirements: Array<{ function: string; importance: 'protagonist' | 'major' | 'functional' | 'npc' }>;
};

export type SummaryArtifactVnext = {
  beats: Array<{ id: string; phase: string; event: string; consequence: string }>;
  climax: string;
  resolution: string;
  character_outcomes: Array<{ character_id: string; outcome: string }>;
};

export type OutlineArtifactVnext = {
  volumes: Array<{
    id: string;
    chapter_window: string;
    objective: string;
    turns: Array<{ id: string; event: string; consequence: string }>;
    ending_state: string;
    character_windows: Array<{ character_id: string; entry_state: string; exit_state: string; turn_id: string }>;
    thread_windows: Array<{ thread_id: string; kind: 'plot' | 'relationship' | 'mystery' | 'foreshadow'; action: string; chapter_window: string }>;
  }>;
};

export type DetailArtifactVnext = {
  chapters: Array<{
    id: string;
    number: number;
    purpose: string;
    pov_character_id: string;
    scenes: Array<{ id: string; location: string; goal: string; obstacle: string; turn: string; outcome: string }>;
    obligations: Array<{ kind: 'character' | 'thread' | 'world_rule' | 'promise'; ref_id: string; action: string }>;
    handoff: { unresolved_actions: string[]; emotional_carryover: string[]; next_pressure: string };
  }>;
};

export type ChapterArtifactVnext = {
  chapter_id: string;
  version_id: string;
  title: string;
  content: string;
  author_status: 'candidate' | 'accepted' | 'edited' | 'branched';
};

export type CoverBriefVnext = {
  concept: string;
  image_prompt: string;
  palette: string[];
  negative_constraints: string[];
};

export type CoverArtifactVnext = { brief: CoverBriefVnext; selected_asset_id: string };

export type ExportArtifactVnext = {
  format: 'md' | 'json' | 'zip';
  chapter_version_ids: string[];
  cover_asset_id: string;
  metadata: { title: string; author: string; version_note: string };
};

type Schema =
  | { type: 'string'; values?: readonly string[]; allowEmpty?: boolean }
  | { type: 'number'; integer?: boolean; min?: number }
  | { type: 'array'; items: Schema; min?: number }
  | { type: 'object'; fields: Record<string, Schema> };

const string = (options: Omit<Extract<Schema, { type: 'string' }>, 'type'> = {}): Schema => ({ type: 'string', ...options });
const number = (options: Omit<Extract<Schema, { type: 'number' }>, 'type'> = {}): Schema => ({ type: 'number', ...options });
const array = (items: Schema, min = 0): Schema => ({ type: 'array', items, min });
const object = (fields: Record<string, Schema>): Schema => ({ type: 'object', fields });

const STORY_BRIEF_SCHEMA = object({
  title: string(),
  premise: string(),
  story_promise: object({ genre: string(), audience: string(), tone: string() }),
  world_rules: array(string(), 1),
  thematic_question: string(),
  ending_promise: string(),
  voice: object({ viewpoint: string(), tense: string(), texture: string(), avoid: array(string()) }),
  cast_requirements: array(object({
    function: string(),
    importance: string({ values: ['protagonist', 'major', 'functional', 'npc'] }),
  })),
});

const SUMMARY_SCHEMA = object({
  beats: array(object({ id: string(), phase: string(), event: string(), consequence: string() }), 1),
  climax: string(),
  resolution: string(),
  character_outcomes: array(object({ character_id: string(), outcome: string() })),
});

const OUTLINE_SCHEMA = object({
  volumes: array(object({
    id: string(),
    chapter_window: string(),
    objective: string(),
    turns: array(object({ id: string(), event: string(), consequence: string() }), 1),
    ending_state: string(),
    character_windows: array(object({ character_id: string(), entry_state: string(), exit_state: string(), turn_id: string() })),
    thread_windows: array(object({
      thread_id: string(),
      kind: string({ values: ['plot', 'relationship', 'mystery', 'foreshadow'] }),
      action: string(),
      chapter_window: string(),
    })),
  }), 1),
});

const DETAIL_SCHEMA = object({
  chapters: array(object({
    id: string(),
    number: number({ integer: true, min: 1 }),
    purpose: string(),
    pov_character_id: string(),
    scenes: array(object({ id: string(), location: string(), goal: string(), obstacle: string(), turn: string(), outcome: string() }), 1),
    obligations: array(object({
      kind: string({ values: ['character', 'thread', 'world_rule', 'promise'] }),
      ref_id: string(),
      action: string(),
    })),
    handoff: object({ unresolved_actions: array(string()), emotional_carryover: array(string()), next_pressure: string({ allowEmpty: true }) }),
  }), 1),
});

const CHAPTER_SCHEMA = object({
  chapter_id: string(),
  version_id: string(),
  title: string(),
  content: string(),
  author_status: string({ values: ['candidate', 'accepted', 'edited', 'branched'] }),
});

const COVER_SCHEMA = object({
  brief: object({
    concept: string(),
    image_prompt: string(),
    palette: array(string(), 1),
    negative_constraints: array(string()),
  }),
  selected_asset_id: string({ allowEmpty: true }),
});
const EXPORT_SCHEMA = object({
  format: string({ values: ['md', 'json', 'zip'] }),
  chapter_version_ids: array(string(), 1),
  cover_asset_id: string({ allowEmpty: true }),
  metadata: object({ title: string(), author: string({ allowEmpty: true }), version_note: string({ allowEmpty: true }) }),
});

export const parseStoryBriefArtifact = (source: string) => parseArtifact<StoryBriefArtifact>(source, STORY_BRIEF_SCHEMA, validateUniqueIds);
export const parseSummaryArtifact = (source: string) => parseArtifact<SummaryArtifactVnext>(source, SUMMARY_SCHEMA, validateSummary);
export const parseOutlineArtifact = (source: string) => parseArtifact<OutlineArtifactVnext>(source, OUTLINE_SCHEMA, validateOutline);
export const parseDetailArtifact = (source: string) => parseArtifact<DetailArtifactVnext>(source, DETAIL_SCHEMA, validateDetail);
export const parseChapterArtifact = (source: string) => parseArtifact<ChapterArtifactVnext>(source, CHAPTER_SCHEMA);
export const parseCoverArtifact = (source: string) => parseArtifact<CoverArtifactVnext>(source, COVER_SCHEMA);
export const parseExportArtifact = (source: string) => parseArtifact<ExportArtifactVnext>(source, EXPORT_SCHEMA);

export function artifactReadiness<T>(result: ArtifactParseResult<T>) {
  return {
    completed: result.artifact ? 1 : 0,
    missingLabels: result.artifact ? [] : [result.errors[0] ?? '有效阶段产物'],
    ready: Boolean(result.artifact),
    total: 1,
  };
}

export function coverArtifactReadiness(result: ArtifactParseResult<CoverArtifactVnext>) {
  const missingLabels = result.artifact
    ? (result.artifact.selected_asset_id ? [] : ['正式封面候选'])
    : [result.errors[0] ?? '有效封面产物'];
  return {
    completed: missingLabels.length ? 0 : 1,
    missingLabels,
    ready: missingLabels.length === 0,
    total: 1,
  };
}

function parseArtifact<T>(source: string, schema: Schema, semantic?: (value: unknown, errors: string[]) => void): ArtifactParseResult<T> {
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch {
    return { artifact: null, errors: ['阶段产物不是有效 JSON'] };
  }
  const errors: string[] = [];
  validateSchema(value, schema, 'artifact', errors);
  semantic?.(value, errors);
  return errors.length ? { artifact: null, errors } : { artifact: value as T, errors: [] };
}

function validateSchema(value: unknown, schema: Schema, path: string, errors: string[]) {
  if (schema.type === 'string') {
    if (typeof value !== 'string' || (!schema.allowEmpty && !value.trim())) errors.push(`${path} 必须是非空字符串`);
    else if (schema.values && !schema.values.includes(value)) errors.push(`${path} 不在允许值内`);
    return;
  }
  if (schema.type === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value)) errors.push(`${path} 必须是数字`);
    else if (schema.integer && !Number.isInteger(value)) errors.push(`${path} 必须是整数`);
    else if (schema.min !== undefined && value < schema.min) errors.push(`${path} 不能小于 ${schema.min}`);
    return;
  }
  if (schema.type === 'array') {
    if (!Array.isArray(value)) {
      errors.push(`${path} 必须是数组`);
      return;
    }
    if (schema.min && value.length < schema.min) errors.push(`${path} 至少包含 ${schema.min} 项`);
    value.forEach((item, index) => validateSchema(item, schema.items, `${path}[${index}]`, errors));
    return;
  }
  if (!isRecord(value)) {
    errors.push(`${path} 必须是对象`);
    return;
  }
  const actual = Object.keys(value);
  const expected = Object.keys(schema.fields);
  const unknown = actual.filter((key) => !expected.includes(key));
  const missing = expected.filter((key) => !(key in value));
  if (unknown.length) errors.push(`${path} 包含未支持字段：${unknown.join('、')}`);
  if (missing.length) errors.push(`${path} 缺少字段：${missing.join('、')}`);
  expected.forEach((key) => {
    if (key in value) validateSchema(value[key], schema.fields[key], `${path}.${key}`, errors);
  });
}

function validateUniqueIds(value: unknown, errors: string[]) {
  if (!isRecord(value)) return;
  validateIds((value.cast_requirements as Array<Record<string, unknown>> | undefined) ?? [], errors, 'cast_requirements', false);
}

function validateSummary(value: unknown, errors: string[]) {
  if (!isRecord(value) || !Array.isArray(value.beats)) return;
  validateIds(value.beats, errors, 'beats');
  if (Array.isArray(value.character_outcomes)) {
    validateUniqueStrings(value.character_outcomes, 'character_id', errors, 'character_outcomes');
  }
}

function validateOutline(value: unknown, errors: string[]) {
  if (!isRecord(value) || !Array.isArray(value.volumes)) return;
  validateIds(value.volumes, errors, 'volumes');
  let expectedChapter = 1;
  value.volumes.forEach((volume, index) => {
    if (!isRecord(volume) || !Array.isArray(volume.turns)) return;
    const volumeWindow = parseChapterWindow(volume.chapter_window, `volumes[${index}].chapter_window`, errors);
    if (volumeWindow && volumeWindow[0] !== expectedChapter) errors.push('volumes 的章节窗口必须从第 1 章开始连续覆盖');
    if (volumeWindow) expectedChapter = volumeWindow[1] + 1;
    validateIds(volume.turns, errors, `volumes[${index}].turns`);
    const turnIds = new Set(volume.turns.flatMap((turn) => isRecord(turn) && typeof turn.id === 'string' ? [turn.id] : []));
    if (Array.isArray(volume.character_windows)) {
      volume.character_windows.forEach((window, windowIndex) => {
        if (isRecord(window) && typeof window.turn_id === 'string' && !turnIds.has(window.turn_id)) {
          errors.push(`volumes[${index}].character_windows[${windowIndex}] 引用了未知 turn_id`);
        }
      });
    }
    if (Array.isArray(volume.character_windows)) validateUniqueStrings(volume.character_windows, 'character_id', errors, `volumes[${index}].character_windows`);
    if (Array.isArray(volume.thread_windows) && volumeWindow) {
      volume.thread_windows.forEach((window, windowIndex) => {
        if (!isRecord(window)) return;
        const threadWindow = parseChapterWindow(window.chapter_window, `volumes[${index}].thread_windows[${windowIndex}].chapter_window`, errors);
        if (threadWindow && (threadWindow[0] < volumeWindow[0] || threadWindow[1] > volumeWindow[1])) {
          errors.push(`volumes[${index}].thread_windows[${windowIndex}] 超出所属卷窗口`);
        }
      });
    }
  });
}

function validateDetail(value: unknown, errors: string[]) {
  if (!isRecord(value) || !Array.isArray(value.chapters)) return;
  validateIds(value.chapters, errors, 'chapters');
  const numbers = value.chapters.flatMap((chapter) => isRecord(chapter) && typeof chapter.number === 'number' ? [chapter.number] : []);
  if (numbers.some((number, index) => number !== index + 1)) errors.push('chapters 必须从 1 开始连续编号');
  value.chapters.forEach((chapter, index) => {
    if (!isRecord(chapter)) return;
    if (chapter.id !== `chapter-${index + 1}`) errors.push(`chapters[${index}].id 必须等于 chapter-${index + 1}`);
    if (Array.isArray(chapter.scenes)) validateIds(chapter.scenes, errors, `chapters[${index}].scenes`);
  });
}

function validateIds(items: unknown[], errors: string[], path: string, required = true) {
  const ids = items.flatMap((item) => isRecord(item) && typeof item.id === 'string' ? [item.id] : []);
  if (required && ids.length !== items.length) errors.push(`${path} 每一项都必须包含 id`);
  if (new Set(ids).size !== ids.length) errors.push(`${path} 的 id 必须唯一`);
}

function validateUniqueStrings(items: unknown[], key: string, errors: string[], path: string) {
  const values = items.flatMap((item) => isRecord(item) && typeof item[key] === 'string' ? [item[key] as string] : []);
  if (new Set(values).size !== values.length) errors.push(`${path} 的 ${key} 必须唯一`);
}

function parseChapterWindow(value: unknown, path: string, errors: string[]): [number, number] | null {
  if (typeof value !== 'string') return null;
  const match = /^chapter:([1-9][0-9]*)(?:-([1-9][0-9]*))?$/.exec(value);
  if (!match) {
    errors.push(`${path} 必须使用 chapter:N 或 chapter:N-M`);
    return null;
  }
  const start = Number(match[1]);
  const end = Number(match[2] ?? match[1]);
  if (end < start) {
    errors.push(`${path} 的结束章节不能早于开始章节`);
    return null;
  }
  return [start, end];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
