import type { LengthEnvelope, NarrativeScaleProfile, WorkflowStage } from '../contracts';

const DEFAULT_LENGTH_ENVELOPE: LengthEnvelope = {
  word_target_soft: 100_000,
  chapter_target_soft: 50,
};

export function lengthEnvelopeFromStage(stage: WorkflowStage): LengthEnvelope {
  const values = Object.fromEntries(stage.input_schema.map((field) => [field.key, field.default]));
  return {
    word_target_soft: positiveInteger(values.word_target_soft) ?? DEFAULT_LENGTH_ENVELOPE.word_target_soft,
    chapter_target_soft: positiveInteger(values.chapter_target_soft),
  };
}

export function scaleProfileFromLengthEnvelope(envelope: LengthEnvelope): NarrativeScaleProfile {
  return {
    ...envelope,
    chapter_scene_cap: 4,
    detail_segment_char_cap: 30_000,
    volume_candidate_cap: 12,
    json_item_caps: {},
    cast_pressure_budget: 12,
    pov_pressure_budget: 8,
    thread_pressure_budget: 8,
  };
}

export type ScaleSuggestion = {
  chapterTarget: number;
  wordsPerChapter: number | null;
  volumeTarget: number;
  volumeRange: [number, number];
  turnTarget: number;
  turnRange: [number, number];
  castTarget: number;
  castRange: [number, number];
};

const VOLUME_CANDIDATE_CAP = 12;
const CAST_PRESSURE_BUDGET = 12;

/** Mirror of the backend plan_narrative_scale derivation, for live preview. */
export function suggestScalePlan(envelope: LengthEnvelope): ScaleSuggestion {
  const chapters = envelope.chapter_target_soft
    ?? (envelope.word_target_soft == null ? 40 : Math.max(1, Math.round(envelope.word_target_soft / 2_500)));
  const wordsPerChapter = envelope.word_target_soft == null
    ? null
    : Math.max(1, Math.round(envelope.word_target_soft / chapters));
  const volumeMin = Math.max(1, Math.floor(chapters / 16));
  const volumeMax = Math.min(VOLUME_CANDIDATE_CAP, Math.max(1, Math.ceil(chapters / 8)));
  const volumeTarget = Math.min(volumeMax, Math.max(volumeMin, Math.round(chapters / 12), 1));
  const turnTarget = Math.min(20, Math.max(5, 4 + Math.round(chapters * 0.5)));
  const castTarget = Math.min(CAST_PRESSURE_BUDGET, Math.max(3, 3 + Math.round(chapters / 4)));
  return {
    chapterTarget: chapters,
    wordsPerChapter,
    volumeTarget,
    volumeRange: [volumeMin, volumeMax],
    turnTarget,
    turnRange: [Math.max(4, turnTarget - 2), Math.min(24, turnTarget + 3)],
    castTarget,
    castRange: [Math.max(2, castTarget - 1), Math.min(CAST_PRESSURE_BUDGET, castTarget + 2)],
  };
}

function positiveInteger(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
}
