import type { DetailBaseline } from './detailArtifactModel';
import type {
  DetailCharacterShift,
  DetailFactReveal,
  DetailForeshadow,
  DetailOutlineArtifact,
  DetailWikiCandidate,
} from './stageArtifacts';

export type DetailBlueprintDraft = Pick<
  DetailOutlineArtifact['chapters'][number],
  'chapter' | 'pov' | 'scene' | 'goal' | 'entry_state' | 'conflict' | 'stakes' | 'hook' | 'continuity_notes'
>;

export type DetailWorldWikiDraft = {
  fact_reveals: DetailFactReveal[];
  wiki_candidates: DetailWikiCandidate[];
};

export type DetailFieldErrors = Record<string, string>;

export type DetailDraftValidation<T> = {
  errors: DetailFieldErrors;
  value: T;
  valid: boolean;
};

const foreshadowStatuses = new Set<DetailForeshadow['status']>(['投放', '推进', '回收', '延后']);

export function validateDetailBlueprintDraft(
  draft: DetailBlueprintDraft,
  baseline: DetailBaseline,
  chapterNames: string[],
  chapterIndex: number,
): DetailDraftValidation<DetailBlueprintDraft> {
  const value = mapText(draft);
  const errors: DetailFieldErrors = {};
  requireText(errors, 'chapter', value.chapter, '填写章节名称');
  if (value.chapter && chapterNames.some((name, index) => index !== chapterIndex && name.trim() === value.chapter)) {
    errors.chapter = '章节名称不能与其他章节重复';
  }
  requireKnown(errors, 'pov', value.pov, baseline.characters.map((item) => item.name), '选择已确认的视角人物');
  requireText(errors, 'scene', value.scene, '填写主要场景');
  requireText(errors, 'entry_state', value.entry_state, '填写场景进入状态');
  requireText(errors, 'goal', value.goal, '填写章节行动目标');
  requireText(errors, 'conflict', value.conflict, '填写核心冲突');
  requireText(errors, 'stakes', value.stakes, '填写失败代价');
  requireText(errors, 'hook', value.hook, '填写章末钩子');
  requireText(errors, 'continuity_notes', value.continuity_notes, '填写正文交接与连续性');
  return result(value, errors);
}

export function validateDetailCharacterShiftDraft(
  draft: DetailCharacterShift,
  baseline: DetailBaseline,
): DetailDraftValidation<DetailCharacterShift> {
  const value = mapText(draft);
  const errors: DetailFieldErrors = {};
  const names = baseline.characters.map((item) => item.name);
  requireKnown(errors, 'character', value.character, names, '选择已确认的变化人物');
  if (value.related_to || value.relation) {
    requireKnown(errors, 'related_to', value.related_to, names, '选择已确认的关系对象');
    requireText(errors, 'relation', value.relation, '填写关系定义，或同时清空关系对象');
  }
  if (value.character && value.related_to === value.character) errors.related_to = '关系对象不能与变化人物相同';
  requireText(errors, 'pressure', value.pressure, '填写本章压力');
  requireText(errors, 'motivation', value.motivation, '填写行动动机');
  requireText(errors, 'change', value.change, '填写状态变化');
  requireText(errors, 'impact', value.impact, '填写后续影响');
  return result(value, errors);
}

export function validateDetailWorldWikiDraft(
  draft: DetailWorldWikiDraft,
  baseline: DetailBaseline,
): DetailDraftValidation<DetailWorldWikiDraft> {
  const value = {
    fact_reveals: draft.fact_reveals.map((item) => mapText(item)),
    wiki_candidates: draft.wiki_candidates.map((item) => mapText(item)),
  };
  const errors: DetailFieldErrors = {};
  if (!value.fact_reveals.length) errors.fact_reveals = '至少添加一条事实揭示';
  if (!value.wiki_candidates.length) errors.wiki_candidates = '至少添加一条 Wiki 候选';

  value.fact_reveals.forEach((item, index) => {
    requireAnchor(errors, `fact_reveals.${index}.anchor`, item.anchor, baseline);
    requireText(errors, `fact_reveals.${index}.fact`, item.fact, '填写本章确认事实');
    requireText(errors, `fact_reveals.${index}.impact`, item.impact, '填写事实对后续的影响');
  });
  markDuplicates(value.fact_reveals.map((item) => item.fact), 'fact_reveals', 'fact', '本章确认事实不能重复', errors);

  value.wiki_candidates.forEach((item, index) => {
    requireText(errors, `wiki_candidates.${index}.title`, item.title, '填写 Wiki 条目标题');
    requireText(errors, `wiki_candidates.${index}.fact`, item.fact, '填写可沉淀事实');
    requireAnchor(errors, `wiki_candidates.${index}.source_anchor`, item.source_anchor, baseline);
  });
  markDuplicates(value.wiki_candidates.map((item) => item.title), 'wiki_candidates', 'title', 'Wiki 条目标题不能重复', errors);
  return result(value, errors);
}

export function validateDetailForeshadowDraft(
  draft: DetailForeshadow[],
): DetailDraftValidation<DetailForeshadow[]> {
  const value = draft.map((item) => ({ ...mapText(item), status: item.status }));
  const errors: DetailFieldErrors = {};
  if (!value.length) errors.foreshadow = '至少添加一条伏笔动作';
  value.forEach((item, index) => {
    requireText(errors, `foreshadow.${index}.name`, item.name, '填写伏笔名称');
    if (!foreshadowStatuses.has(item.status)) errors[`foreshadow.${index}.status`] = '选择投放、推进、回收或延后';
    requireText(errors, `foreshadow.${index}.note`, item.note, '填写本章伏笔动作说明');
  });
  markDuplicates(value.map((item) => item.name), 'foreshadow', 'name', '同一章的伏笔名称不能重复', errors);
  return result(value, errors);
}

function requireAnchor(errors: DetailFieldErrors, field: string, value: string, baseline: DetailBaseline) {
  if (!value) {
    errors[field] = '选择已确认的世界观锚点';
    return;
  }
  if (!baseline.worldAnchors.includes(value) && !baseline.worldbuildingDetail.includes(value)) {
    errors[field] = '该锚点不属于已确认的 Info 或 Outline 设定';
  }
}

function requireKnown(errors: DetailFieldErrors, field: string, value: string, options: string[], message: string) {
  if (!value || !options.includes(value)) errors[field] = message;
}

function requireText(errors: DetailFieldErrors, field: string, value: string, message: string) {
  if (!value) errors[field] = message;
}

function markDuplicates(
  values: string[],
  collection: string,
  field: string,
  message: string,
  errors: DetailFieldErrors,
) {
  const counts = values.reduce((result, value) => {
    if (value) result.set(value, (result.get(value) ?? 0) + 1);
    return result;
  }, new Map<string, number>());
  values.forEach((value, index) => {
    if (value && (counts.get(value) ?? 0) > 1) errors[`${collection}.${index}.${field}`] = message;
  });
}

function mapText<T extends Record<string, unknown>>(value: T): T {
  return Object.fromEntries(Object.entries(value).map(([key, entry]) => [
    key,
    typeof entry === 'string' ? entry.trim() : entry,
  ])) as T;
}

function result<T>(value: T, errors: DetailFieldErrors): DetailDraftValidation<T> {
  return { errors, valid: Object.keys(errors).length === 0, value };
}
