export type CharacterKind = 'protagonist' | 'major' | 'functional' | 'npc' | 'historical_record';
export type CharacterSubject = { id: string; name: string; kind: CharacterKind; function: string; drive: string; change: string; debut: string; limits: string[]; demand_refs: string[] };
export type CharacterRelation = { a: string; b: string; type: string; pressure: string };
export type CharacterBibleArtifact = { subjects: CharacterSubject[]; relations: CharacterRelation[] };
export type CharacterBibleParseResult = { artifact: CharacterBibleArtifact | null; errors: string[] };

const ID_PATTERN = /^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/;
const WINDOW_PATTERN = /^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$/;
const KINDS = new Set<CharacterKind>(['protagonist', 'major', 'functional', 'npc', 'historical_record']);

export function parseCharacterBibleArtifact(source: string): CharacterBibleParseResult {
  let value: unknown;
  try { value = JSON.parse(source); } catch { return { artifact: null, errors: ['人物圣经不是有效 JSON'] }; }
  if (!isRecord(value)) return { artifact: null, errors: ['人物圣经必须是对象'] };
  const errors: string[] = [];
  exactKeys(value, ['subjects', 'relations'], '人物圣经', errors);
  const subjects = parseSubjects(value.subjects, errors);
  const relations = parseRelations(value.relations, errors);
  const ids = new Set(subjects.map((item) => item.id));
  if (!subjects.some((item) => item.kind === 'protagonist')) errors.push('人物圣经至少需要一名主角');
  if (ids.size !== subjects.length) errors.push('人物 ID 必须唯一');
  relations.forEach((item, index) => { if (item.a === item.b || !ids.has(item.a) || !ids.has(item.b)) errors.push(`关系 ${index + 1} 引用了未登记主体`); });
  return errors.length ? { artifact: null, errors } : { artifact: { subjects, relations }, errors: [] };
}

export function characterBibleReadiness(artifact: CharacterBibleArtifact | null) {
  const missingLabels = !artifact ? ['有效的人物圣经'] : artifact.subjects.some((item) => item.kind === 'protagonist') ? [] : ['至少一名主角'];
  return { completed: missingLabels.length ? 0 : 1, missingLabels, ready: !missingLabels.length, total: 1 };
}

export function nextSubjectId(artifact: CharacterBibleArtifact) { const used = new Set(artifact.subjects.map((item) => item.id)); let index = 1; while (used.has(`subject-${index}`)) index += 1; return `subject-${index}`; }

function parseSubjects(value: unknown, errors: string[]): CharacterSubject[] {
  if (!Array.isArray(value)) { errors.push('subjects 必须是数组'); return []; }
  return value.flatMap((item, index) => {
    if (!isRecord(item)) { errors.push(`主体 ${index + 1} 不是对象`); return []; }
    exactKeys(item, ['id', 'name', 'kind', 'function', 'drive', 'change', 'debut', 'limits', 'demand_refs'], `主体 ${index + 1}`, errors);
    const subject: CharacterSubject = { id: String(item.id ?? ''), name: String(item.name ?? ''), kind: item.kind as CharacterKind, function: String(item.function ?? ''), drive: String(item.drive ?? ''), change: String(item.change ?? ''), debut: String(item.debut ?? ''), limits: stringList(item.limits, `主体 ${index + 1} 限制`, errors), demand_refs: stringList(item.demand_refs, `主体 ${index + 1} 职责引用`, errors) };
    if (!ID_PATTERN.test(subject.id)) errors.push(`主体 ${index + 1} 的 ID 无效`); if (!subject.name.trim() || !subject.function.trim() || !subject.drive.trim() || !subject.change.trim()) errors.push(`主体 ${index + 1} 的核心字段不能为空`); if (!KINDS.has(subject.kind)) errors.push(`主体 ${index + 1} 的类型无效`); if (!validWindow(subject.debut)) errors.push(`主体 ${index + 1} 的首次窗口无效`);
    return [subject];
  });
}

function parseRelations(value: unknown, errors: string[]): CharacterRelation[] {
  if (!Array.isArray(value)) { errors.push('relations 必须是数组'); return []; }
  return value.flatMap((item, index) => { if (!isRecord(item)) { errors.push(`关系 ${index + 1} 不是对象`); return []; } exactKeys(item, ['a', 'b', 'type', 'pressure'], `关系 ${index + 1}`, errors); const relation = { a: String(item.a ?? ''), b: String(item.b ?? ''), type: String(item.type ?? ''), pressure: String(item.pressure ?? '') }; if (!relation.type.trim() || !relation.pressure.trim()) errors.push(`关系 ${index + 1} 的语义不能为空`); return [relation]; });
}

function stringList(value: unknown, label: string, errors: string[]) { if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || !item.trim())) { errors.push(`${label} 必须是非空字符串数组`); return []; } return value.map(String); }
function validWindow(value: string) { const match = WINDOW_PATTERN.exec(value); if (!match) return false; const [start, end = start] = value.slice('chapter:'.length).split('-').map(Number); return start <= end; }
function exactKeys(record: Record<string, unknown>, keys: readonly string[], label: string, errors: string[]) { const unknown = Object.keys(record).filter((key) => !keys.includes(key)); const missing = keys.filter((key) => !(key in record)); if (unknown.length) errors.push(`${label} 包含未支持字段：${unknown.join('、')}`); if (missing.length) errors.push(`${label} 缺少字段：${missing.join('、')}`); }
function isRecord(value: unknown): value is Record<string, any> { return Boolean(value) && typeof value === 'object' && !Array.isArray(value); }
