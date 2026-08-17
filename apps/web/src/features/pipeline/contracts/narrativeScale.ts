export type LengthEnvelope = {
  word_target_soft: number;
};

export type NarrativeScaleProfile = LengthEnvelope & {
  detail_segment_char_cap: number;
  volume_candidate_cap: number;
  json_item_caps: Record<string, number>;
  capacity_policy: NarrativeCapacityPolicy;
};

export type NarrativeCapacityPolicy = {
  chapter_characters_min: number;
  chapter_characters_preferred: number;
  chapter_characters_max: number;
  volume_chapters_min: number;
  volume_chapters_preferred: number;
  volume_chapters_max: number;
  scene_characters_min: number;
  scene_characters_max: number;
  spine_chapters_per_turn_min: number;
  spine_chapters_per_turn_preferred: number;
  spine_chapters_per_turn_max: number;
  cast_chapters_per_subject_min: number;
  cast_chapters_per_subject_preferred: number;
  cast_subjects_recommended_min: number;
  cast_subjects_hard_max: number;
  cast_subject_burst_allowance: number;
  book_target_tolerance_percent: number;
  adjacent_chapter_delta_percent: number;
};
