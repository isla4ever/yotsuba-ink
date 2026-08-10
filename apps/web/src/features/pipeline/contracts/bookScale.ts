export type BookScaleTargetMode = 'total_chars' | 'total_chapters';

export type BookScaleTarget = {
  target_mode: BookScaleTargetMode;
  target_value: number;
};

export type StageContentBudget = {
  scope: 'per_book' | 'per_volume' | 'per_chapter' | 'per_plan';
  target_chars: number;
  min_chars: number;
  max_chars: number;
  max_tokens: number;
  description: string;
};

export type VolumeScalePlan = {
  volume_index: number;
  chapter_start: number;
  chapter_end: number;
  chapter_count: number;
  target_chars: number;
};

export type BookScalePlan = {
  contract_version: 'book-scale-plan-v1';
  target_mode: BookScaleTargetMode;
  target_value: number;
  counting_standard: 'cjk-visible-chars-v1';
  total_chars: number;
  total_chapters: number;
  volume_count: number;
  chapters_per_volume: number[];
  chapter_target_chars: number;
  chapter_soft_min_chars: number;
  chapter_soft_max_chars: number;
  chapter_hard_min_chars: number;
  chapter_hard_max_chars: number;
  book_soft_min_chars: number;
  book_soft_max_chars: number;
  stage_budgets: Record<string, StageContentBudget>;
  story_scope: {
    character_min: number;
    character_max: number;
    relationship_min: number;
    relationship_max: number;
  };
  capacity_policy: {
    primary_shifts_per_chapter: number;
    default_scenes_per_chapter: number;
    max_scenes_per_chapter: number;
    exceptional_scenes_per_chapter: number;
    max_independent_reveals_per_chapter: number;
    split_rule: string;
  };
  volumes: VolumeScalePlan[];
};
