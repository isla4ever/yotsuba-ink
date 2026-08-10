import type {
  BookScalePlan,
  BookScaleTargetMode,
  StageContentBudget,
  VolumeScalePlan,
} from '../contracts';

export const bookScaleLimits = {
  total_chars: { min: 3_000, max: 5_000_000, step: 1_000 },
  total_chapters: { min: 1, max: 2_500, step: 1 },
} as const;

const DEFAULT_CHAPTER_TARGET = 2_000;
const PREFERRED_CHAPTERS_PER_VOLUME = 12;
const MIN_CHAPTERS_PER_VOLUME = 8;
const MAX_CHAPTERS_PER_VOLUME = 16;

export function buildBookScalePlan(
  targetMode: BookScaleTargetMode,
  rawTargetValue: number,
): BookScalePlan {
  const limits = bookScaleLimits[targetMode];
  const targetValue = clamp(Math.round(rawTargetValue), limits.min, limits.max);
  const totalChars = targetMode === 'total_chars'
    ? targetValue
    : targetValue * DEFAULT_CHAPTER_TARGET;
  const totalChapters = targetMode === 'total_chars'
    ? Math.max(1, roundHalfUp(totalChars / DEFAULT_CHAPTER_TARGET))
    : targetValue;
  const chapterTarget = targetMode === 'total_chars'
    ? roundHalfUp(totalChars / totalChapters)
    : DEFAULT_CHAPTER_TARGET;
  const chaptersPerVolume = distributeChapters(totalChapters);
  const volumeTargets = distributeTotal(totalChars, chaptersPerVolume);
  let chapterStart = 1;
  const volumes: VolumeScalePlan[] = chaptersPerVolume.map((chapterCount, index) => {
    const chapterEnd = chapterStart + chapterCount - 1;
    const volume = {
      volume_index: index + 1,
      chapter_start: chapterStart,
      chapter_end: chapterEnd,
      chapter_count: chapterCount,
      target_chars: volumeTargets[index],
    };
    chapterStart = chapterEnd + 1;
    return volume;
  });
  const chapterSoftMin = Math.max(700, Math.floor(chapterTarget * 0.8));
  const chapterSoftMax = Math.max(chapterSoftMin, Math.ceil(chapterTarget * 1.2));
  const chapterHardMin = Math.max(500, Math.floor(chapterTarget * 0.65));
  const chapterHardMax = Math.max(chapterSoftMax, Math.ceil(chapterTarget * 1.5));
  const bookSoftMin = targetMode === 'total_chars'
    ? Math.floor(totalChars * 0.95)
    : chapterSoftMin * totalChapters;
  const bookSoftMax = targetMode === 'total_chars'
    ? Math.ceil(totalChars * 1.05)
    : chapterSoftMax * totalChapters;

  return {
    contract_version: 'book-scale-plan-v1',
    target_mode: targetMode,
    target_value: targetValue,
    counting_standard: 'cjk-visible-chars-v1',
    total_chars: totalChars,
    total_chapters: totalChapters,
    volume_count: chaptersPerVolume.length,
    chapters_per_volume: chaptersPerVolume,
    chapter_target_chars: chapterTarget,
    chapter_soft_min_chars: chapterSoftMin,
    chapter_soft_max_chars: chapterSoftMax,
    chapter_hard_min_chars: chapterHardMin,
    chapter_hard_max_chars: chapterHardMax,
    book_soft_min_chars: bookSoftMin,
    book_soft_max_chars: bookSoftMax,
    stage_budgets: stageBudgets({
      totalChars,
      totalChapters,
      volumeCount: chaptersPerVolume.length,
      chapterTarget,
      chapterSoftMin,
      chapterSoftMax,
    }),
    story_scope: storyScope(totalChapters),
    capacity_policy: {
      primary_shifts_per_chapter: 1,
      default_scenes_per_chapter: 1,
      max_scenes_per_chapter: 2,
      exceptional_scenes_per_chapter: 3,
      max_independent_reveals_per_chapter: 1,
      split_rule: '一个章节只承担一个主要叙事位移；独立选择、重大揭示、关系反转或时空视角转换同时出现时，优先在选择与代价、结果与应对之间拆成相邻章节，并通过 continuity_handoff 交接。',
    },
    volumes,
  };
}

export function distributeChapters(totalChapters: number): number[] {
  const chapters = Math.max(1, Math.round(totalChapters));
  if (chapters <= MAX_CHAPTERS_PER_VOLUME) return [chapters];
  const preferred = roundHalfUp(chapters / PREFERRED_CHAPTERS_PER_VOLUME);
  const minimumVolumes = Math.ceil(chapters / MAX_CHAPTERS_PER_VOLUME);
  const maximumVolumes = Math.max(1, Math.floor(chapters / MIN_CHAPTERS_PER_VOLUME));
  const volumeCount = Math.min(maximumVolumes, Math.max(minimumVolumes, preferred));
  const base = Math.floor(chapters / volumeCount);
  const remainder = chapters % volumeCount;
  return Array.from({ length: volumeCount }, (_, index) => base + (index < remainder ? 1 : 0));
}

export function formatBookChars(value: number): string {
  if (value >= 10_000) {
    const wan = value / 10_000;
    return `${Number.isInteger(wan) ? wan.toFixed(0) : wan.toFixed(1)} 万字`;
  }
  return `${value.toLocaleString('zh-CN')} 字`;
}

function stageBudgets(input: {
  totalChars: number;
  totalChapters: number;
  volumeCount: number;
  chapterTarget: number;
  chapterSoftMin: number;
  chapterSoftMax: number;
}): Record<string, StageContentBudget> {
  let info = [2_200, 1_400, 3_200];
  if (input.totalChars <= 20_000) info = [1_600, 1_100, 2_400];
  else if (input.totalChars <= 150_000) info = [2_200, 1_400, 3_200];
  else if (input.totalChars <= 600_000) info = [2_800, 1_800, 4_000];
  else info = [3_200, 2_000, 4_600];
  const summaryTarget = Math.min(4_200, Math.max(1_200, 1_100 + input.volumeCount * 140));
  const detailTarget = Math.min(2_200, Math.max(1_400, 1_250 + Math.floor(input.totalChapters / 80) * 100));
  return {
    info: budget('per_book', info[0], info[1], info[2], '立项 Story DNA，按全书体量配置人物与关系基线。'),
    summary: budget('per_book', summaryTarget, Math.max(900, Math.floor(summaryTarget * 0.72)), Math.ceil(summaryTarget * 1.45), '完整因果梗概；篇幅随分卷复杂度增长，但不重放逐章剧情。'),
    outline: budget('per_volume', 1_000, 650, 1_600, '单卷 Volume Program；长篇按卷分批生成并连续合并。'),
    detail: budget('per_chapter', detailTarget, 1_000, 3_200, '单章结构化剧本；每章一个主要叙事位移，超载内容顺延到相邻章节。'),
    text: {
      scope: 'per_chapter',
      target_chars: input.chapterTarget,
      min_chars: input.chapterSoftMin,
      max_chars: input.chapterSoftMax,
      max_tokens: Math.max(1_200, Math.ceil(input.chapterSoftMax * 1.25)),
      description: '单章正文软预算；转场章可略短，高潮章可略长，全书目标负责最终闭合。',
    },
    cover: budget('per_plan', 700, 450, 1_200, '封面 brief、构图和图像提示词，不随正文章数线性增长。'),
  };
}

function budget(
  scope: StageContentBudget['scope'],
  target: number,
  minimum: number,
  maximum: number,
  description: string,
): StageContentBudget {
  return {
    scope,
    target_chars: target,
    min_chars: minimum,
    max_chars: maximum,
    max_tokens: Math.max(1_200, Math.ceil(maximum * 1.45)),
    description,
  };
}

function storyScope(chapters: number): BookScalePlan['story_scope'] {
  if (chapters <= 5) return { character_min: 3, character_max: 5, relationship_min: 3, relationship_max: 8 };
  if (chapters <= 50) return { character_min: 5, character_max: 8, relationship_min: 7, relationship_max: 16 };
  return { character_min: 7, character_max: 11, relationship_min: 10, relationship_max: 26 };
}

function distributeTotal(total: number, weights: number[]): number[] {
  const weightTotal = weights.reduce((sum, item) => sum + item, 0);
  const values = weights.map((weight) => Math.floor((total * weight) / weightTotal));
  let remainder = total - values.reduce((sum, item) => sum + item, 0);
  for (let index = 0; remainder > 0; index = (index + 1) % values.length) {
    values[index] += 1;
    remainder -= 1;
  }
  return values;
}

function roundHalfUp(value: number): number {
  return Math.floor(value + 0.5);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
