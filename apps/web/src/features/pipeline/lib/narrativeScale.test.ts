import { describe, expect, it } from 'vitest';
import {
  DEFAULT_CAPACITY_POLICY,
  scaleProfileFromLengthEnvelope,
  suggestChapterCount,
  suggestScalePlan,
} from './narrativeScale';

describe('narrative scale capacity policy', () => {
  it('uses the frozen capacity policy when deriving the chapter target', () => {
    const suggestion = suggestChapterCount(
      { word_target_soft: 100_000 },
      { ...DEFAULT_CAPACITY_POLICY, chapter_characters_preferred: 2_500 },
    );

    expect(suggestion.chapterTarget).toBe(40);
    expect(suggestion.chapterRange).toEqual([34, 50]);
  });

  it('derives chapter and scene ranges from a 100k target', () => {
    const plan = suggestScalePlan({ word_target_soft: 100_000 });

    expect(plan.chapterRange).toEqual([34, 50]);
    expect(plan.chapterTarget).toBe(40);
    expect(plan.chapterCharacterRange).toEqual([2_000, 3_000]);
    expect(plan.sceneRange).toEqual([2, 5]);
    expect(plan.volumeTarget).toBe(3);
    expect(plan.volumeRange).toEqual([2, 5]);
    expect(plan.turnTarget).toBe(20);
    expect(plan.turnRange).toEqual([16, 26]);
  });

  it('freezes the capacity policy into the run scale profile', () => {
    const profile = scaleProfileFromLengthEnvelope({ word_target_soft: 100_000 });

    expect(profile.capacity_policy.chapter_characters_preferred).toBe(2_500);
    expect(profile.capacity_policy.scene_characters_min).toBe(500);
    expect(profile.capacity_policy.scene_characters_max).toBe(2_400);
    expect(profile.capacity_policy.volume_chapters_min).toBe(8);
    expect(profile.capacity_policy.volume_chapters_preferred).toBe(14);
    expect(profile.capacity_policy.volume_chapters_max).toBe(20);
    expect(profile.capacity_policy.spine_chapters_per_turn_min).toBe(1.5);
    expect(profile.capacity_policy.spine_chapters_per_turn_preferred).toBe(2);
    expect(profile.capacity_policy.spine_chapters_per_turn_max).toBe(2.5);
    expect(profile.capacity_policy.book_target_tolerance_percent).toBe(10);
    expect(profile.capacity_policy.adjacent_chapter_delta_percent).toBe(15);
    expect(profile).not.toHaveProperty('chapter_scene_cap');
  });

  it('keeps the capacity range visible when a valid chapter preference is supplied', () => {
    const plan = suggestScalePlan({ word_target_soft: 100_000 });

    expect(plan.chapterRange).toEqual([34, 50]);
    expect(plan.chapterTarget).toBe(40);
    expect(plan.chapterPreferenceValid).toBe(true);
  });

  it('ignores an obsolete chapter preference and keeps the code target', () => {
    const plan = suggestScalePlan({ word_target_soft: 100_000 });

    expect(plan.chapterRange).toEqual([34, 50]);
    expect(plan.chapterTarget).toBe(40);
    expect(plan.chapterPreferenceValid).toBe(true);
  });

  it('keeps chapter and scene capacity stable when obsolete preferences differ', () => {
    const longer = suggestScalePlan({ word_target_soft: 100_000 });
    const shorter = suggestScalePlan({ word_target_soft: 100_000 });

    expect(longer.chapterCharacterRange).toEqual([2_000, 3_000]);
    expect(longer.sceneRange).toEqual([2, 5]);
    expect(shorter.chapterCharacterRange).toEqual([2_000, 3_000]);
    expect(shorter.sceneRange).toEqual([2, 5]);
  });

  it('uses the frozen run policy for chapter and scene suggestions', () => {
    const policy = {
      ...DEFAULT_CAPACITY_POLICY,
      chapter_characters_min: 2_500,
      chapter_characters_preferred: 2_500,
      chapter_characters_max: 2_500,
      scene_characters_min: 1_000,
      scene_characters_max: 1_500,
    };

    const plan = suggestScalePlan(
      { word_target_soft: 100_000 },
      policy,
    );

    expect(plan.chapterRange).toEqual([40, 40]);
    expect(plan.chapterTarget).toBe(40);
    expect(plan.sceneRange).toEqual([2, 2]);
    expect(plan.volumeRange).toEqual([2, 5]);
    expect(plan.volumeTarget).toBe(3);
  });

  it('collapses the Spine domain when the frozen policy has one density', () => {
    const plan = suggestScalePlan(
      { word_target_soft: 100_000 },
      {
        ...DEFAULT_CAPACITY_POLICY,
        spine_chapters_per_turn_min: 1.25,
        spine_chapters_per_turn_preferred: 1.25,
        spine_chapters_per_turn_max: 1.25,
      },
    );

    expect(plan.turnTarget).toBe(32);
    expect(plan.turnRange).toEqual([32, 32]);
  });
});
