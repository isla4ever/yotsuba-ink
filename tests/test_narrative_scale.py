from __future__ import annotations

import pytest

from novel_workflow.output_contracts.artifacts_vnext import VolumeArchitectureArtifact
from novel_workflow.workflows.narrative_scale import (
    ChapterNarrativeLoad,
    DetailScaleProjection,
    NarrativeScaleProfile,
    allocate_chapter_character_targets,
    chapter_count_range,
    chapter_count_range_for_spine,
    chapter_length_contract,
    detail_scene_count_range,
    chapter_target_band,
    plan_narrative_scale,
    project_turn_chapter_window,
    project_volume_scales,
    scale_profile_from_inputs,
    soft_book_length_bounds,
    volume_count_range,
)


def chapter_load(
    scene_count: int,
    *,
    cast_count: int = 1,
    turn_count: int = 1,
    place_count: int | None = None,
    length_hint: str = "standard",
) -> ChapterNarrativeLoad:
    return ChapterNarrativeLoad(
        scene_count=scene_count,
        active_cast_count=cast_count,
        turn_count=turn_count,
        distinct_place_count=place_count or scene_count,
        length_hint=length_hint,
    )


def test_scale_profile_preserves_only_the_book_length_intent() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {
                "word_target_soft": 100_000,
            }
        }
    )

    assert profile.word_target_soft == 100_000
    assert not hasattr(profile, "chapter_target_soft")
    assert not hasattr(profile, "chapter_min_reasonable")
    assert not hasattr(profile, "chapter_max_reasonable")
    assert not hasattr(profile, "volume_count")


@pytest.mark.parametrize(
    "value",
    [
        {"chapter_target_soft": 0},
        {"chapter_target_soft": 8, "chapter_min_reasonable": 1},
        {"chapter_min_reasonable": 5, "chapter_max_reasonable": 2},
        {"pov_pressure_budget": 8},
        {"thread_pressure_budget": 8},
        {"cast_pressure_budget": 8},
        {"cast_demand_override": 8},
    ],
)
def test_scale_profile_rejects_invalid_bounds(value: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        NarrativeScaleProfile.model_validate(value)


def test_scale_profile_requires_length_envelope() -> None:
    with pytest.raises(ValueError):
        scale_profile_from_inputs({})


def test_scale_profile_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValueError):
        scale_profile_from_inputs(
            {
                "length_envelope": {
                    "word_target_soft": None,
                },
                "unrecognized_input": {},
            }
        )


def test_scale_profile_rejects_unknown_length_envelope_fields() -> None:
    with pytest.raises(ValueError):
        scale_profile_from_inputs(
            {
                "length_envelope": {
                    "word_target_soft": None,
                    "chapter_min_reasonable": 1,
                }
            }
        )


def test_scale_profile_keeps_only_the_user_length_envelope() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 100_000}}
    )

    assert profile.word_target_soft == 100_000
    assert not hasattr(profile, "chapter_target_soft")
    assert not hasattr(profile, "chapter_min_reasonable")
    assert not hasattr(profile, "chapter_max_reasonable")


def test_scale_plan_freezes_one_volume_for_a_short_story() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 8_000}}
    )

    plan = plan_narrative_scale(profile, "balanced")

    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (1, 1, 1)
    assert plan.turn_min <= plan.turn_target <= plan.turn_max
    assert plan.turn_target == 3
    assert not hasattr(plan, "cast_demand_target")
    assert not hasattr(plan, "cast_demand_min")
    assert not hasattr(plan, "cast_demand_max")
    targets = allocate_chapter_character_targets(
        profile,
        [chapter_load(3), chapter_load(4), chapter_load(3)],
    )
    assert sum(targets) == 7_500
    assert targets[1] > targets[0]
    assert targets[1] > targets[2]


def test_scale_plan_scales_spine_and_volume_capacity_without_character_quotas() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 240_000}}
    )

    plan = plan_narrative_scale(profile, "balanced")

    assert (plan.turn_min, plan.turn_target, plan.turn_max) == (39, 48, 64)
    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (5, 7, 12)
    assert (plan.cast_recommended_min, plan.cast_recommended_max, plan.cast_hard_max) == (3, 16, 16)
    assert not hasattr(plan, "cast_demand_target")


def test_long_book_cast_capacity_stays_within_the_role_demand_schema() -> None:
    profile = NarrativeScaleProfile(word_target_soft=240_000)

    plan = plan_narrative_scale(profile, "balanced")

    assert plan.cast_hard_max == 16
    assert plan.cast_recommended_max == 16


def test_100k_scale_uses_chapter_and_scene_capacity_ranges() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    plan = plan_narrative_scale(profile, "balanced")

    assert chapter_count_range(profile) == (34, 40, 50)
    assert (plan.chapter_min, plan.chapter_target, plan.chapter_max) == (34, 40, 50)
    assert (plan.turn_min, plan.turn_target, plan.turn_max) == (16, 20, 26)
    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (2, 3, 5)
    assert volume_count_range(profile) == (2, 3, 5)
    assert (plan.scenes_per_chapter_min, plan.scenes_per_chapter_max) == (1, 5)
    assert (plan.cast_recommended_min, plan.cast_recommended_max, plan.cast_hard_max) == (3, 7, 11)


def test_soft_book_length_bounds_keep_the_100k_demo_floor_without_exact_targeting() -> None:
    balanced_demo = NarrativeScaleProfile(word_target_soft=110_000)
    assert soft_book_length_bounds(balanced_demo) == (99_000, 121_000)

    short_run = NarrativeScaleProfile(word_target_soft=4_000)
    assert soft_book_length_bounds(short_run) == (3_600, 4_400)


def test_accepted_spine_density_never_changes_the_frozen_chapter_target() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    assert chapter_count_range_for_spine(profile, 16) == (34, 40, 40)
    assert chapter_count_range_for_spine(profile, 20) == (34, 40, 50)
    assert chapter_count_range_for_spine(profile, 26) == (39, 40, 50)


def test_minimum_spine_grammar_allows_multiple_turns_inside_a_micro_story_chapter() -> None:
    profile = NarrativeScaleProfile(
        word_target_soft=4_000,
    )

    assert plan_narrative_scale(profile, "balanced").turn_target == 3
    assert chapter_count_range_for_spine(profile, 3) == (2, 2, 2)
    with pytest.raises(ValueError, match="regenerate Spine instead of padding Detail"):
        chapter_count_range_for_spine(profile, 4)


def test_underdense_spine_cannot_be_padded_into_a_100k_detail() -> None:
    with pytest.raises(ValueError, match="regenerate Spine instead of changing"):
        chapter_count_range_for_spine(
            NarrativeScaleProfile(word_target_soft=100_000),
            15,
        )


def test_turn_positions_project_to_dynamic_debut_windows() -> None:
    assert project_turn_chapter_window(
        turn_number=1, turn_count=20, chapter_count=34
    ) == (1, 3)
    assert project_turn_chapter_window(
        turn_number=9, turn_count=20, chapter_count=34
    ) == (13, 17)
    assert project_turn_chapter_window(
        turn_number=19, turn_count=20, chapter_count=34
    ) == (30, 34)
    assert project_turn_chapter_window(
        turn_number=20, turn_count=20, chapter_count=34
    ) == (32, 34)


def test_scene_count_range_narrows_after_detail_selects_the_chapter_count() -> None:
    longer_chapters = NarrativeScaleProfile(
        word_target_soft=100_000,
    )
    shorter_chapters = NarrativeScaleProfile(
        word_target_soft=100_000,
    )

    assert detail_scene_count_range(longer_chapters, 34) == (1, 5)
    assert detail_scene_count_range(shorter_chapters, 50) == (1, 4)


def test_chapter_band_does_not_turn_the_selected_count_into_a_new_length_policy() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    short_layout = chapter_target_band(profile, 34)
    long_layout = chapter_target_band(profile, 50)

    assert short_layout == long_layout
    assert short_layout is not None
    assert (
        short_layout.min_characters,
        short_layout.preferred_characters,
        short_layout.max_characters,
    ) == (2_000, 2_500, 3_000)


def test_auto_scale_rejects_a_fragmented_detail_scene_load() -> None:
    profile = NarrativeScaleProfile(
        word_target_soft=100_000,
        capacity_policy={"scene_characters_min": 800},
    )

    with pytest.raises(ValueError, match="scene load"):
        allocate_chapter_character_targets(profile, [chapter_load(4)] * 40)


def test_auto_scale_rejects_a_detail_plan_without_enough_scene_capacity() -> None:
    profile = NarrativeScaleProfile(
        word_target_soft=100_000,
        capacity_policy={"scene_characters_max": 800},
    )

    with pytest.raises(ValueError, match="minimum viable"):
        allocate_chapter_character_targets(profile, [chapter_load(2)] * 40)


def test_auto_scale_uses_the_nearest_viable_book_budget_instead_of_forcing_target() -> None:
    profile = NarrativeScaleProfile(
        word_target_soft=100_000,
        capacity_policy={"scene_characters_max": 1_000},
    )

    targets = allocate_chapter_character_targets(profile, [chapter_load(2)] * 40)

    assert sum(targets) == 80_000
    assert all(target == 2_000 for target in targets)


def test_auto_scale_allocates_shorter_targets_to_lower_scene_load() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)
    chapter_loads = ([chapter_load(2), chapter_load(3)] * 20)[:40]

    targets = allocate_chapter_character_targets(profile, chapter_loads)

    assert sum(targets) == 100_000
    two_scene_targets = [
        target
        for target, load in zip(targets, chapter_loads, strict=True)
        if load.scene_count == 2
    ]
    three_scene_targets = [
        target
        for target, load in zip(targets, chapter_loads, strict=True)
        if load.scene_count == 3
    ]
    assert max(two_scene_targets) < min(three_scene_targets)


def test_obsolete_chapter_preference_cannot_override_the_code_target() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    assert chapter_count_range(profile) == (34, 40, 50)


def test_chapter_preference_keeps_the_intrinsic_capacity_range() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    assert chapter_count_range(profile) == (34, 40, 50)


def test_100k_character_budget_tracks_scene_load_inside_a_bounded_band() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)
    chapter_loads = ([chapter_load(3), chapter_load(4)] * 20)[:40]

    targets = allocate_chapter_character_targets(profile, chapter_loads)
    band = chapter_target_band(profile)

    assert band is not None
    assert len(targets) == 40
    assert sum(targets) == 100_000
    assert max(targets) - min(targets) > 1
    assert min(targets) >= band.min_characters
    assert max(targets) <= band.max_characters
    assert all(
        abs(left - right) <= band.max_adjacent_delta + 1
        for left, right in zip(targets, targets[1:])
    )
    assert min(
        target
        for target, load in zip(targets, chapter_loads, strict=True)
        if load.scene_count == 4
    ) > max(
        target
        for target, load in zip(targets, chapter_loads, strict=True)
        if load.scene_count == 3
    )


def test_shorter_layout_keeps_a_lean_chapter_without_forcing_the_preferred_center() -> None:
    profile = NarrativeScaleProfile(
        word_target_soft=100_000,
        capacity_policy={"scene_characters_max": 2_000},
    )

    targets = allocate_chapter_character_targets(
        profile,
        [chapter_load(1), *[chapter_load(3) for _ in range(39)]],
    )

    assert targets[0] == 2_000
    assert sum(targets) == 100_000


def test_dynamic_scene_range_and_rhythm_band_keep_varied_loads_feasible() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)
    chapter_loads = ([chapter_load(2), chapter_load(5)] * 20)[:40]

    targets = allocate_chapter_character_targets(profile, chapter_loads)
    band = chapter_target_band(profile, 40)

    assert band is not None
    assert sum(targets) == 100_000
    assert max(targets) > min(targets)
    assert all(
        abs(left - right) <= band.max_adjacent_delta
        for left, right in zip(targets, targets[1:])
    )


def test_default_scene_range_allows_one_scene_that_can_carry_viable_prose() -> None:
    profile = NarrativeScaleProfile(word_target_soft=7_500)

    assert detail_scene_count_range(profile, 3) == (1, 5)
    assert allocate_chapter_character_targets(
        profile,
        [chapter_load(1), chapter_load(1), chapter_load(1)],
    ) == [2_400, 2_400, 2_400]


def test_character_budget_rejects_a_detail_count_below_the_frozen_target() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    with pytest.raises(ValueError, match="frozen scale requires exactly 40"):
        allocate_chapter_character_targets(profile, [chapter_load(3)] * 39)


def test_character_budget_rejects_a_detail_count_outside_the_feasible_range() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)

    with pytest.raises(ValueError, match="frozen scale requires exactly 40"):
        allocate_chapter_character_targets(profile, [chapter_load(3)] * 33)


def test_character_budget_uses_multiple_load_signals_beyond_scene_count() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)
    loads = [chapter_load(2) for _ in range(40)]
    loads[20] = chapter_load(
        2,
        cast_count=4,
        turn_count=2,
        place_count=2,
        length_hint="expansive",
    )

    targets = allocate_chapter_character_targets(profile, loads)

    assert targets[20] > targets[19]
    assert max(targets) - min(targets) <= 500
    assert sum(targets) == 100_000


@pytest.mark.parametrize(
    ("word_target", "chapter_count", "expected_total"),
    [(85_000, 34, 85_000), (100_000, 40, 100_000), (125_000, 50, 125_000)],
)
def test_book_budget_preserves_preferred_chapter_length_inside_the_soft_envelope(
    word_target: int,
    chapter_count: int,
    expected_total: int,
) -> None:
    profile = NarrativeScaleProfile(word_target_soft=word_target)
    scene_minimum, _ = detail_scene_count_range(profile, chapter_count)

    targets = allocate_chapter_character_targets(
        profile,
        [chapter_load(max(2, scene_minimum)) for _ in range(chapter_count)],
    )

    assert sum(targets) == expected_total
    assert round(word_target * 0.9) <= sum(targets) <= round(word_target * 1.1)


def test_volume_projection_allocates_more_chapters_to_higher_narrative_load() -> None:
    architecture = VolumeArchitectureArtifact.model_validate({
        "volumes": [
            {
                "id": "volume-1",
                "title": "失钟之城",
                "promise": "建立异常规则",
                "conflict": "城市拒绝承认失时",
                "climax": "主角取得首份证据",
                "climax_turn_ref": "turn-5",
                "closure": "调查正式开始",
                "turn_refs": [f"turn-{turn}" for turn in range(1, 6)],
                "cast_ids": ["subject-lin"],
                "length_hint": "short",
            },
            {
                "id": "volume-2",
                "title": "被偷走的分钟",
                "promise": "揭开失时机制",
                "conflict": "多方争夺时间记录",
                "climax": "城市时钟同时停摆",
                "climax_turn_ref": "turn-11",
                "closure": "幕后系统暴露",
                "turn_refs": [f"turn-{turn}" for turn in range(6, 15)],
                "cast_ids": ["subject-lin", "subject-zhou", "subject-gu"],
                "length_hint": "long",
            },
        ]
    })
    profile = NarrativeScaleProfile(word_target_soft=60_000)

    projections = project_volume_scales(
        architecture,
        profile,
        spine_turn_count=14,
    )

    assert sum(item.chapter_target for item in projections) == 24
    assert [item.chapter_target for item in projections] == [8, 16]
    assert projections[1].chapter_target > projections[0].chapter_target
    assert all(item.chapter_min <= item.chapter_target <= item.chapter_max for item in projections)


def test_volume_projection_rejects_the_underdense_10_7_3_turn_regression() -> None:
    architecture = VolumeArchitectureArtifact.model_validate({
        "volumes": [
            {
                "id": f"volume-{index}",
                "title": title,
                "promise": "推进本卷承诺",
                "conflict": "形成不可回避的对抗",
                "climax": "完成本卷核心转折",
                "climax_turn_ref": f"turn-{turn_start + (turn_count * 3 + 4) // 5 - 1}",
                "closure": "形成下一阶段格局",
                "turn_refs": [
                    f"turn-{turn}"
                    for turn in range(turn_start, turn_start + turn_count)
                ],
                "cast_ids": [f"subject-{subject}" for subject in range(1, cast_count + 1)],
                "length_hint": length_hint,
            }
            for index, (title, turn_start, turn_count, cast_count, length_hint) in enumerate(
                (
                    ("潮声初现", 1, 12, 6, "long"),
                    ("沉箱证词", 13, 10, 4, "medium"),
                    ("潮落追责", 23, 3, 2, "short"),
                ),
                start=1,
            )
        ]
    })

    with pytest.raises(ValueError, match="regenerate Volumes"):
        project_volume_scales(
            architecture,
            NarrativeScaleProfile(word_target_soft=100_000),
            spine_turn_count=25,
        )


def test_volume_length_hint_never_changes_the_numeric_allocation() -> None:
    def architecture(hints: tuple[str, str, str]) -> VolumeArchitectureArtifact:
        return VolumeArchitectureArtifact.model_validate({
            "volumes": [
                {
                    "id": f"volume-{index}",
                    "title": title,
                    "promise": "推进承诺",
                    "conflict": "升级对抗",
                    "climax": "形成转折",
                    "climax_turn_ref": f"turn-{(index - 1) * 7 + 5}",
                    "closure": "完成闭合",
                    "turn_refs": [
                        f"turn-{turn}"
                        for turn in range((index - 1) * 7 + 1, index * 7 + 1)
                    ],
                    "cast_ids": ["subject-1"],
                    "length_hint": hint,
                }
                for index, (title, hint) in enumerate(
                    zip(("上卷", "中卷", "下卷"), hints, strict=True),
                    start=1,
                )
            ]
        })

    forward = project_volume_scales(
        architecture(("long", "medium", "short")),
        NarrativeScaleProfile(word_target_soft=100_000),
        spine_turn_count=21,
    )
    reversed_hints = project_volume_scales(
        architecture(("short", "medium", "long")),
        NarrativeScaleProfile(word_target_soft=100_000),
        spine_turn_count=21,
    )

    assert [(item.chapter_min, item.chapter_max) for item in forward] == [
        (item.chapter_min, item.chapter_max) for item in reversed_hints
    ]
    assert [item.chapter_target for item in forward] == [14, 13, 13]
    assert [item.chapter_target for item in reversed_hints] == [14, 13, 13]


def test_volume_projection_allows_a_code_selected_single_volume_arc() -> None:
    architecture = VolumeArchitectureArtifact.model_validate({
        "volumes": [
            {
                "id": "volume-1",
                "title": "失钟之城",
                "promise": "建立异常规则",
                "conflict": "城市拒绝承认失时",
                "climax": "主角取得首份证据",
                "climax_turn_ref": "turn-5",
                "closure": "调查正式开始",
                "turn_refs": [f"turn-{turn}" for turn in range(1, 9)],
                "cast_ids": ["subject-lin"],
                "length_hint": "long",
            }
        ]
    })
    profile = NarrativeScaleProfile(word_target_soft=30_000)

    projections = project_volume_scales(
        architecture,
        profile,
        spine_turn_count=8,
    )

    assert [
        (
            projection.chapter_min,
            projection.chapter_target,
            projection.chapter_max,
        )
        for projection in projections
    ] == [(12, 12, 12)]


def test_scale_plan_fast_mode_keeps_the_dynamic_spine_domain() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 100_000}}
    )

    plan = plan_narrative_scale(profile, "fast")

    assert (plan.turn_min, plan.turn_target, plan.turn_max) == (16, 20, 26)
    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (2, 3, 5)
    assert not hasattr(plan, "cast_demand_target")


def test_scale_plan_honors_deep_mode_spine_override_exactly() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {"word_target_soft": 100_000},
            "scale_overrides": {
                "turn_target": 24,
            },
        }
    )

    plan = plan_narrative_scale(profile, "deep")

    assert (plan.turn_min, plan.turn_target, plan.turn_max) == (24, 24, 24)
    assert not hasattr(plan, "cast_demand_target")
    assert plan.user_locked == ["turn_target"]


def test_deep_mode_rejects_a_spine_override_outside_dynamic_density() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {"word_target_soft": 100_000},
            "scale_overrides": {"turn_target": 14},
        }
    )

    with pytest.raises(ValueError, match="must fit the range.*16-26"):
        plan_narrative_scale(profile, "deep")


def test_scale_profile_rejects_the_obsolete_volume_override() -> None:
    with pytest.raises(ValueError):
        scale_profile_from_inputs(
            {
                "length_envelope": {
                    "word_target_soft": 100_000,
                },
                "scale_overrides": {"volume_target": 2, "turn_target": None},
            }
        )


def test_scale_plan_ignores_overrides_outside_deep_mode() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {"word_target_soft": 100_000},
            "scale_overrides": {"turn_target": 14},
        }
    )

    plan = plan_narrative_scale(profile, "balanced")

    assert plan.user_locked == []
    assert plan.turn_min < plan.turn_max


def test_volume_projection_rejects_more_volumes_than_the_exact_chapter_target() -> None:
    architecture = VolumeArchitectureArtifact.model_validate(
        {
            "volumes": [
                {
                    "id": f"volume-{index}",
                    "title": f"雾港余声{index}",
                    "promise": "承接主线",
                    "conflict": "证据被封锁",
                    "climax": "夺回证据",
                    "climax_turn_ref": f"turn-{index}",
                    "closure": "形成新局面",
                    "turn_refs": [f"turn-{index}"],
                    "cast_ids": ["subject-lin"],
                    "length_hint": "short",
                }
                for index in range(1, 3)
            ]
        }
    )
    profile = NarrativeScaleProfile(word_target_soft=2_500)

    with pytest.raises(ValueError, match="requires exactly 1"):
        project_volume_scales(architecture, profile, spine_turn_count=2)


def test_detail_segment_carries_its_position_and_scene_budget() -> None:
    profile = NarrativeScaleProfile(word_target_soft=100_000)
    segment = DetailScaleProjection(
        volume_ref="volume-1",
        segment_ref="volume-1.segment-2",
        segment_index=2,
        segment_count=3,
        chapter_target=3,
        chapter_beats=[
            {
                "chapter_offset": 1,
                "turn_refs": ["turn-1"],
                "dramatic_job": "建立不可撤回的调查风险",
                "length_hint": "compact",
            },
            {
                "chapter_offset": 2,
                "turn_refs": ["turn-1"],
                "dramatic_job": "迫使主角公开选择立场",
                "length_hint": "standard",
            },
            {
                "chapter_offset": 3,
                "turn_refs": ["turn-1"],
                "dramatic_job": "让选择造成公开后果",
                "length_hint": "expansive",
            },
        ],
        chapter_target_band=chapter_target_band(profile),
        scenes_per_chapter_min=2,
        scenes_per_chapter_max=5,
        chapter_number_start=4,
    )

    assert segment.chapter_number_start == 4
    assert segment.chapter_target_band is not None
    assert segment.chapter_target_band.preferred_characters == 2_500
    assert not segment.is_final_volume


def test_detail_segment_rejects_an_inverted_scene_band() -> None:
    with pytest.raises(ValueError):
        DetailScaleProjection(
            volume_ref="volume-1",
            segment_ref="volume-1.segment-1",
            segment_index=1,
            segment_count=1,
            chapter_target=3,
            chapter_beats=[
                {
                    "chapter_offset": 1,
                    "turn_refs": ["turn-1"],
                    "dramatic_job": "建立风险",
                    "length_hint": "compact",
                },
                {
                    "chapter_offset": 2,
                    "turn_refs": ["turn-1"],
                    "dramatic_job": "迫使选择",
                    "length_hint": "standard",
                },
                {
                    "chapter_offset": 3,
                    "turn_refs": ["turn-1"],
                    "dramatic_job": "形成后果",
                    "length_hint": "expansive",
                },
            ],
            scenes_per_chapter_min=5,
            scenes_per_chapter_max=2,
        )


@pytest.mark.parametrize(
    ("quality_mode", "expected"),
    [("fast", (2125, 2875)), ("balanced", (2050, 2950)), ("deep", (2300, 2700))],
)
def test_chapter_length_contract_uses_mode_tolerance(
    quality_mode: str,
    expected: tuple[int, int],
) -> None:
    contract = chapter_length_contract(2_500, quality_mode, scene_count=2)

    assert contract is not None
    assert (contract.min_characters, contract.max_characters) == expected
    assert contract.characters_per_scene_target == 1_250
