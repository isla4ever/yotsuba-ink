from __future__ import annotations

import pytest

from novel_workflow.output_contracts.artifacts_vnext import VolumeArchitectureArtifact
from novel_workflow.workflows.narrative_scale import (
    DetailScaleProjection,
    NarrativeScaleProfile,
    chapter_character_targets,
    chapter_length_contract,
    plan_narrative_scale,
    project_volume_scales,
    scale_profile_from_inputs,
)


def test_scale_profile_preserves_soft_intent_without_deriving_boundaries() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {
                "word_target_soft": 100_000,
                "chapter_target_soft": 24,
            }
        }
    )

    assert profile.word_target_soft == 100_000
    assert profile.chapter_target_soft == 24
    assert not hasattr(profile, "chapter_min_reasonable")
    assert not hasattr(profile, "chapter_max_reasonable")
    assert not hasattr(profile, "volume_count")


@pytest.mark.parametrize(
    "value",
    [
        {"chapter_target_soft": 0},
        {"chapter_target_soft": 8, "chapter_min_reasonable": 1},
        {"chapter_min_reasonable": 5, "chapter_max_reasonable": 2},
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
                    "chapter_target_soft": None,
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
                    "chapter_target_soft": None,
                    "chapter_min_reasonable": 1,
                }
            }
        )


def test_scale_profile_keeps_only_the_user_length_envelope() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 100_000, "chapter_target_soft": None}}
    )

    assert profile.chapter_target_soft is None
    assert not hasattr(profile, "chapter_min_reasonable")
    assert not hasattr(profile, "chapter_max_reasonable")


def test_scale_plan_keeps_a_short_story_in_one_volume() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 8_000, "chapter_target_soft": 3}}
    )

    plan = plan_narrative_scale(profile, "balanced")

    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (1, 1, 1)
    assert plan.turn_min <= plan.turn_target <= plan.turn_max
    assert plan.turn_target == 6
    assert plan.cast_demand_target == 4
    assert plan.cast_demand_min >= 3
    assert plan.characters_per_chapter == round(8_000 / 3)
    assert chapter_character_targets(profile) == [2667, 2667, 2666]


def test_scale_plan_scales_volumes_and_cast_for_a_long_novel() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 1_000_000, "chapter_target_soft": 120}}
    )

    plan = plan_narrative_scale(profile, "balanced")

    assert plan.volume_min >= 7
    assert plan.volume_target == 10
    assert plan.volume_max <= 12
    assert plan.turn_target == 20
    assert plan.cast_demand_max <= 12


def test_scale_plan_fast_mode_collapses_ranges_to_system_values() -> None:
    profile = scale_profile_from_inputs(
        {"length_envelope": {"word_target_soft": 100_000, "chapter_target_soft": 40}}
    )

    plan = plan_narrative_scale(profile, "fast")

    assert plan.volume_min == plan.volume_target == plan.volume_max
    assert plan.turn_min == plan.turn_target == plan.turn_max
    assert plan.cast_demand_min == plan.cast_demand_target == plan.cast_demand_max


def test_scale_plan_honors_deep_mode_user_overrides_exactly() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {"word_target_soft": 100_000, "chapter_target_soft": 40},
            "scale_overrides": {
                "volume_target": 5,
                "turn_target": 14,
                "cast_demand_target": 9,
            },
        }
    )

    plan = plan_narrative_scale(profile, "deep")

    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (5, 5, 5)
    assert (plan.turn_min, plan.turn_target, plan.turn_max) == (14, 14, 14)
    assert (plan.cast_demand_min, plan.cast_demand_target, plan.cast_demand_max) == (9, 9, 9)
    assert set(plan.user_locked) == {"volume_target", "turn_target", "cast_demand_target"}


def test_scale_plan_ignores_overrides_outside_deep_mode() -> None:
    profile = scale_profile_from_inputs(
        {
            "length_envelope": {"word_target_soft": 100_000, "chapter_target_soft": 40},
            "scale_overrides": {"volume_target": 5, "turn_target": None, "cast_demand_target": None},
        }
    )

    plan = plan_narrative_scale(profile, "balanced")

    assert plan.user_locked == []
    assert plan.volume_min < plan.volume_max


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
                    "closure": "形成新局面",
                    "turn_refs": [f"turn-{index}"],
                    "cast_ids": ["subject-lin"],
                    "thread_ids": [],
                    "length_hint": "short",
                }
                for index in range(1, 3)
            ]
        }
    )
    profile = NarrativeScaleProfile(word_target_soft=2_500)

    with pytest.raises(ValueError, match="at least one chapter per volume"):
        project_volume_scales(architecture, profile)


def test_detail_segment_carries_its_position_and_scene_budget() -> None:
    segment = DetailScaleProjection(
        volume_ref="volume-1",
        segment_ref="volume-1.segment-2",
        segment_index=2,
        segment_count=3,
        chapter_target=3,
        chapter_character_targets=[2_500, 2_500, 2_500],
        scenes_per_chapter_min=2,
        scenes_per_chapter_max=5,
        chapter_number_start=4,
    )

    assert segment.chapter_number_start == 4
    assert not segment.is_final_volume


def test_detail_segment_rejects_an_inverted_scene_band() -> None:
    with pytest.raises(ValueError):
        DetailScaleProjection(
            volume_ref="volume-1",
            segment_ref="volume-1.segment-1",
            segment_index=1,
            segment_count=1,
            chapter_target=3,
            scenes_per_chapter_min=5,
            scenes_per_chapter_max=2,
        )


@pytest.mark.parametrize(
    ("quality_mode", "expected"),
    [("fast", (2125, 2875)), ("balanced", (2200, 2800)), ("deep", (2300, 2700))],
)
def test_chapter_length_contract_uses_mode_tolerance(
    quality_mode: str,
    expected: tuple[int, int],
) -> None:
    contract = chapter_length_contract(2_500, quality_mode, scene_count=2)

    assert contract is not None
    assert (contract.min_characters, contract.max_characters) == expected
    assert contract.characters_per_scene_target == 1_250
