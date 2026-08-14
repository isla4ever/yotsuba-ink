export type LengthEnvelope = {
  word_target_soft: number | null;
  chapter_target_soft: number | null;
};

export type NarrativeScaleProfile = LengthEnvelope & {
  chapter_min_reasonable: number;
  chapter_max_reasonable: number;
  chapter_scene_cap: number;
  detail_segment_char_cap: number;
  volume_candidate_cap: number;
  json_item_caps: Record<string, number>;
  cast_pressure_budget: number;
  pov_pressure_budget: number;
  thread_pressure_budget: number;
};
