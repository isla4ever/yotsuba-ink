export type CharacterTier = 'protagonist' | 'major' | 'functional';

export type CharacterArc = {
  start: string;
  turning_point: string;
  end: string;
};

export type CharacterRecord = {
  id: string;
  name: string;
  tier: CharacterTier;
  narrative_function: string;
  external_goal: string;
  inner_need: string;
  arc: CharacterArc;
  first_appearance_window: string;
  hard_boundaries: string[];
};

export type CharacterRelationship = {
  source_id: string;
  target_id: string;
  nature: string;
  initial_state: string;
  pressure: string;
};

export type NpcSlot = {
  id: string;
  function: string;
  first_appearance_window: string;
  limits: string[];
};

export type CharacterBibleArtifact = {
  characters: CharacterRecord[];
  relationships: CharacterRelationship[];
  npc_slots: NpcSlot[];
};

export type CharacterBibleParseResult = {
  artifact: CharacterBibleArtifact | null;
  errors: string[];
};

const ROOT_KEYS = ['characters', 'relationships', 'npc_slots'] as const;
const CHARACTER_KEYS = [
  'id',
  'name',
  'tier',
  'narrative_function',
  'external_goal',
  'inner_need',
  'arc',
  'first_appearance_window',
  'hard_boundaries',
] as const;
const ARC_KEYS = ['start', 'turning_point', 'end'] as const;
const RELATIONSHIP_KEYS = ['source_id', 'target_id', 'nature', 'initial_state', 'pressure'] as const;
const NPC_KEYS = ['id', 'function', 'first_appearance_window', 'limits'] as const;
const TIERS = new Set<CharacterTier>(['protagonist', 'major', 'functional']);
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;
const APPEARANCE_WINDOW_PATTERN = /^chapter:([1-9][0-9]*)(?:-([1-9][0-9]*))?$/;

export function parseCharacterBibleArtifact(source: string): CharacterBibleParseResult {
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch {
    return { artifact: null, errors: ['人物圣经不是有效的结构化产物'] };
  }
  if (!isRecord(value)) return { artifact: null, errors: ['人物圣经必须是对象'] };

  const errors: string[] = [];
  exactKeys(value, ROOT_KEYS, '人物圣经', errors);
  const characters = parseCharacters(value.characters, errors);
  const relationships = parseRelationships(value.relationships, errors);
  const npcSlots = parseNpcSlots(value.npc_slots, errors);
  validateRegistry(characters, relationships, npcSlots, errors);
  if (errors.length) return { artifact: null, errors };
  return { artifact: { characters, relationships, npc_slots: npcSlots }, errors: [] };
}

export function characterBibleReadiness(artifact: CharacterBibleArtifact | null) {
  const missingLabels: string[] = [];
  if (!artifact) missingLabels.push('有效的人物圣经');
  if (artifact && !artifact.characters.length) missingLabels.push('至少一名正式角色');
  return {
    completed: 2 - missingLabels.length,
    missingLabels,
    ready: missingLabels.length === 0,
    total: 2,
  };
}

export function nextCharacterId(artifact: CharacterBibleArtifact) {
  return nextId('character', new Set([
    ...artifact.characters.map((item) => item.id),
    ...artifact.npc_slots.map((item) => item.id),
  ]));
}

export function nextNpcSlotId(artifact: CharacterBibleArtifact) {
  return nextId('npc-slot', new Set([
    ...artifact.characters.map((item) => item.id),
    ...artifact.npc_slots.map((item) => item.id),
  ]));
}

function parseCharacters(value: unknown, errors: string[]): CharacterRecord[] {
  if (!Array.isArray(value)) {
    errors.push('characters 必须是数组');
    return [];
  }
  if (!value.length) errors.push('characters 至少包含一名角色');
  return value.flatMap((item, index) => {
    if (!isRecord(item)) {
      errors.push(`角色 ${index + 1} 不是对象`);
      return [];
    }
    exactKeys(item, CHARACTER_KEYS, `角色 ${index + 1}`, errors);
    if (!isRecord(item.arc)) {
      errors.push(`角色 ${index + 1} 缺少完整弧线`);
      return [];
    }
    exactKeys(item.arc, ARC_KEYS, `角色 ${index + 1} 弧线`, errors);
    const tier = item.tier;
    if (!TIERS.has(tier as CharacterTier)) errors.push(`角色 ${index + 1} 的层级无效`);
    validateId(item.id, `角色 ${index + 1}`, errors);
    requiredStrings(item, CHARACTER_KEYS.filter((key) => !['tier', 'arc', 'hard_boundaries'].includes(key)), `角色 ${index + 1}`, errors);
    requiredStrings(item.arc, ARC_KEYS, `角色 ${index + 1} 弧线`, errors);
    validateAppearanceWindow(item.first_appearance_window, `角色 ${index + 1}`, errors);
    const hardBoundaries = stringList(item.hard_boundaries, `角色 ${index + 1} 的硬边界`, errors);
    return [{
      id: String(item.id ?? ''),
      name: String(item.name ?? ''),
      tier: tier as CharacterTier,
      narrative_function: String(item.narrative_function ?? ''),
      external_goal: String(item.external_goal ?? ''),
      inner_need: String(item.inner_need ?? ''),
      arc: {
        start: String(item.arc.start ?? ''),
        turning_point: String(item.arc.turning_point ?? ''),
        end: String(item.arc.end ?? ''),
      },
      first_appearance_window: String(item.first_appearance_window ?? ''),
      hard_boundaries: hardBoundaries,
    }];
  });
}

function parseRelationships(value: unknown, errors: string[]): CharacterRelationship[] {
  if (!Array.isArray(value)) {
    errors.push('relationships 必须是数组');
    return [];
  }
  return value.flatMap((item, index) => {
    if (!isRecord(item)) {
      errors.push(`关系 ${index + 1} 不是对象`);
      return [];
    }
    exactKeys(item, RELATIONSHIP_KEYS, `关系 ${index + 1}`, errors);
    requiredStrings(item, RELATIONSHIP_KEYS, `关系 ${index + 1}`, errors);
    return [{
      source_id: String(item.source_id ?? ''),
      target_id: String(item.target_id ?? ''),
      nature: String(item.nature ?? ''),
      initial_state: String(item.initial_state ?? ''),
      pressure: String(item.pressure ?? ''),
    }];
  });
}

function parseNpcSlots(value: unknown, errors: string[]): NpcSlot[] {
  if (!Array.isArray(value)) {
    errors.push('npc_slots 必须是数组');
    return [];
  }
  return value.flatMap((item, index) => {
    if (!isRecord(item)) {
      errors.push(`NPC 槽位 ${index + 1} 不是对象`);
      return [];
    }
    exactKeys(item, NPC_KEYS, `NPC 槽位 ${index + 1}`, errors);
    validateId(item.id, `NPC 槽位 ${index + 1}`, errors);
    requiredStrings(item, ['id', 'function', 'first_appearance_window'], `NPC 槽位 ${index + 1}`, errors);
    validateAppearanceWindow(item.first_appearance_window, `NPC 槽位 ${index + 1}`, errors);
    return [{
      id: String(item.id ?? ''),
      function: String(item.function ?? ''),
      first_appearance_window: String(item.first_appearance_window ?? ''),
      limits: stringList(item.limits, `NPC 槽位 ${index + 1} 的限制`, errors),
    }];
  });
}

function validateRegistry(
  characters: CharacterRecord[],
  relationships: CharacterRelationship[],
  npcSlots: NpcSlot[],
  errors: string[],
) {
  const characterIds = characters.map((item) => item.id);
  const npcIds = npcSlots.map((item) => item.id);
  if (new Set(characterIds).size !== characterIds.length) errors.push('人物 ID 必须唯一');
  if (new Set(npcIds).size !== npcIds.length) errors.push('NPC 槽位 ID 必须唯一');
  if (npcIds.some((id) => characterIds.includes(id))) errors.push('NPC 槽位不能复用人物 ID');
  const known = new Set(characterIds);
  relationships.forEach((item, index) => {
    if (item.source_id === item.target_id) errors.push(`关系 ${index + 1} 不能指向自身`);
    if (!known.has(item.source_id) || !known.has(item.target_id)) errors.push(`关系 ${index + 1} 引用了未登记人物`);
  });
}

function exactKeys(record: Record<string, unknown>, allowed: readonly string[], label: string, errors: string[]) {
  const unknown = Object.keys(record).filter((key) => !allowed.includes(key));
  if (unknown.length) errors.push(`${label} 包含未支持字段：${unknown.join('、')}`);
  const missing = allowed.filter((key) => !(key in record));
  if (missing.length) errors.push(`${label} 缺少字段：${missing.join('、')}`);
}

function requiredStrings(record: Record<string, unknown>, keys: readonly string[], label: string, errors: string[]) {
  keys.forEach((key) => {
    if (typeof record[key] !== 'string' || !record[key].trim()) errors.push(`${label} 的 ${key} 不能为空`);
  });
}

function validateId(value: unknown, label: string, errors: string[]) {
  if (typeof value !== 'string' || !ID_PATTERN.test(value)) errors.push(`${label} 的 ID 无效`);
}

function validateAppearanceWindow(value: unknown, label: string, errors: string[]) {
  if (typeof value !== 'string') return;
  const match = APPEARANCE_WINDOW_PATTERN.exec(value.trim());
  if (!match || (match[2] && Number(match[2]) < Number(match[1]))) {
    errors.push(`${label} 的首次出现窗口必须使用 chapter:N 或 chapter:N-M`);
  }
}

function stringList(value: unknown, label: string, errors: string[]) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || !item.trim())) {
    errors.push(`${label} 必须是非空字符串数组`);
    return [];
  }
  return value.map((item) => String(item));
}

function nextId(prefix: string, used: Set<string>) {
  let suffix = 1;
  while (used.has(`${prefix}-${suffix}`)) suffix += 1;
  return `${prefix}-${suffix}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
