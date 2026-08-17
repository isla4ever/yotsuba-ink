import type { LengthEnvelope, NarrativeCapacityPolicy, NarrativeScaleProfile, WorkflowStage } from '../contracts';

const DEFAULT_LENGTH_ENVELOPE: LengthEnvelope = {
  word_target_soft: 100_000,
};

export const DEFAULT_CAPACITY_POLICY: NarrativeCapacityPolicy = {
  chapter_characters_min: 2_000,
  chapter_characters_preferred: 2_500,
  chapter_characters_max: 3_000,
  volume_chapters_min: 8,
  volume_chapters_preferred: 14,
  volume_chapters_max: 20,
  scene_characters_min: 500,
  scene_characters_max: 2_400,
  spine_chapters_per_turn_min: 1.5,
  spine_chapters_per_turn_preferred: 2,
  spine_chapters_per_turn_max: 2.5,
  cast_chapters_per_subject_min: 4,
  cast_chapters_per_subject_preferred: 6,
  cast_subjects_recommended_min: 3,
  cast_subjects_hard_max: 16,
  cast_subject_burst_allowance: 1,
  book_target_tolerance_percent: 10,
  adjacent_chapter_delta_percent: 15,
};

export function lengthEnvelopeFromStage(stage: WorkflowStage): LengthEnvelope {
  const values = Object.fromEntries(stage.input_schema.map((field) => [field.key, field.default]));
  return {
    word_target_soft: positiveInteger(values.word_target_soft) ?? DEFAULT_LENGTH_ENVELOPE.word_target_soft,
  };
}

export function scaleProfileFromLengthEnvelope(envelope: LengthEnvelope): NarrativeScaleProfile {
  return {
    ...envelope,
    detail_segment_char_cap: 30_000,
    volume_candidate_cap: 12,
    json_item_caps: {},
    capacity_policy: DEFAULT_CAPACITY_POLICY,
  };
}

export type ScaleSuggestion = {
  chapterTarget: number;
  chapterRange: [number, number];
  chapterPreferenceValid: boolean;
  chapterCharacterRange: [number, number];
  sceneRange: [number, number];
  volumeTarget: number;
  volumeRange: [number, number];
  turnTarget: number;
  turnRange: [number, number];
  castRecommendedRange: [number, number];
  castHardMax: number;
};

/** Mirror of the backend plan_narrative_scale derivation, for live preview. */
export function suggestScalePlan(
  envelope: LengthEnvelope,
  policy: NarrativeCapacityPolicy = DEFAULT_CAPACITY_POLICY,
): ScaleSuggestion {
  const {
    chapterPreferenceValid,
    chapterRange,
    chapterTarget: chapters,
  } = suggestChapterCount(envelope, policy);
  const chapterCharacterRange = deriveChapterCharacterRange(policy);
  const sceneRange = deriveSceneRange(envelope, chapters, chapterCharacterRange, policy);
  const [volumeMinimum, volumeTarget, volumeMaximum] = deriveVolumeRange(chapters, policy);
  const turnMinimum = Math.max(
    3,
    Math.ceil(chapters / policy.spine_chapters_per_turn_max),
  );
  const turnTarget = Math.max(
    turnMinimum,
    Math.round(chapters / policy.spine_chapters_per_turn_preferred),
  );
  const turnMaximum = Math.max(
    turnTarget,
    Math.floor(chapters / policy.spine_chapters_per_turn_min),
  );
  const castHardMax = Math.min(
    policy.cast_subjects_hard_max,
    Math.max(1, Math.ceil(chapters / policy.cast_chapters_per_subject_min) + policy.cast_subject_burst_allowance),
  );
  const castRecommendedMin = Math.min(policy.cast_subjects_recommended_min, castHardMax);
  const castRecommendedMax = Math.min(
    castHardMax,
    Math.max(castRecommendedMin, Math.ceil(chapters / policy.cast_chapters_per_subject_preferred)),
  );
  return {
    chapterTarget: chapters,
    chapterRange,
    chapterPreferenceValid,
    chapterCharacterRange,
    sceneRange,
    volumeTarget,
    volumeRange: [volumeMinimum, volumeMaximum],
    turnTarget,
    turnRange: [turnMinimum, turnMaximum],
    castRecommendedRange: [castRecommendedMin, castRecommendedMax],
    castHardMax,
  };
}

export function suggestChapterCount(
  envelope: LengthEnvelope,
  policy: NarrativeCapacityPolicy = DEFAULT_CAPACITY_POLICY,
) {
  const chapterRange = deriveChapterRange(envelope, policy);
  const chapterTarget = preferredChapterCount(envelope, chapterRange, policy);
  return { chapterPreferenceValid: true, chapterRange, chapterTarget };
}

function deriveVolumeRange(
  chapterTarget: number,
  policy: NarrativeCapacityPolicy,
): [number, number, number] {
  if (chapterTarget < policy.volume_chapters_min) return [1, 1, 1];
  const minimum = Math.max(1, Math.ceil(chapterTarget / policy.volume_chapters_max));
  const maximum = Math.max(minimum, Math.floor(chapterTarget / policy.volume_chapters_min));
  const target = Math.min(
    maximum,
    Math.max(minimum, Math.round(chapterTarget / policy.volume_chapters_preferred)),
  );
  return [minimum, target, maximum];
}

function deriveChapterCharacterRange(
  policy: NarrativeCapacityPolicy,
): [number, number] {
  return [
    policy.chapter_characters_min,
    policy.chapter_characters_max,
  ];
}

function deriveSceneRange(
  envelope: LengthEnvelope,
  chapterCount: number,
  [chapterMinimum, chapterMaximum]: [number, number],
  policy: NarrativeCapacityPolicy,
): [number, number] {
  const chapterCenter = envelope.word_target_soft == null
    ? null
    : preferredBookCharacterBudget(envelope.word_target_soft, chapterCount, policy) / chapterCount;
  const capacityMinimum = chapterCenter ?? chapterMinimum;
  const capacityMaximum = chapterCenter ?? chapterMaximum;
  const minimum = Math.max(
    1,
    Math.ceil(capacityMinimum / policy.scene_characters_max),
  );
  const maximum = Math.max(
    minimum,
    Math.floor(capacityMaximum / policy.scene_characters_min),
  );
  return [minimum, maximum];
}

function preferredBookCharacterBudget(
  wordTargetSoft: number,
  chapterCount: number,
  policy: NarrativeCapacityPolicy,
): number {
  const tolerance = policy.book_target_tolerance_percent;
  const softMinimum = Math.ceil(wordTargetSoft * (100 - tolerance) / 100);
  const softMaximum = Math.floor(wordTargetSoft * (100 + tolerance) / 100);
  const minimum = Math.max(softMinimum, chapterCount * policy.chapter_characters_min);
  const maximum = Math.min(softMaximum, chapterCount * policy.chapter_characters_max);
  const preferred = chapterCount * policy.chapter_characters_preferred;
  return Math.min(maximum, Math.max(minimum, preferred));
}

function deriveChapterRange(
  envelope: LengthEnvelope,
  policy: NarrativeCapacityPolicy,
): [number, number] {
  const minimum = Math.max(1, Math.ceil(envelope.word_target_soft / policy.chapter_characters_max));
  const maximum = Math.max(minimum, Math.floor(envelope.word_target_soft / policy.chapter_characters_min));
  return [minimum, maximum];
}

function preferredChapterCount(
  envelope: LengthEnvelope,
  [minimum, maximum]: [number, number],
  policy: NarrativeCapacityPolicy,
): number {
  return Math.min(maximum, Math.max(minimum, Math.round(envelope.word_target_soft / policy.chapter_characters_preferred)));
}

function positiveInteger(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
}
