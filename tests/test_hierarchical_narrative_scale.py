import pytest

from novel_workflow.workflows.hierarchical_scale import (
    HierarchicalScaleOverrides,
    hierarchical_scale_plan_from_inputs,
    plan_hierarchical_narrative_scale,
)
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile


def test_million_character_plan_is_partitioned_into_bounded_parts() -> None:
    plan = plan_hierarchical_narrative_scale(
        NarrativeScaleProfile(word_target_soft=1_000_000),
        quality_mode="deep",
    )

    assert (plan.chapter_min, plan.chapter_target, plan.chapter_max) == (334, 400, 500)
    assert (plan.volume_min, plan.volume_target, plan.volume_max) == (20, 29, 50)
    assert (plan.part_min, plan.part_target, plan.part_max) == (4, 6, 9)
    assert len(plan.parts) == 6
    assert sum(part.chapter_target for part in plan.parts) == 400
    assert sum(part.volume_target for part in plan.parts) == 29
    assert all(part.turn_max <= 120 for part in plan.parts)
    assert not hasattr(plan, "turn_target")


def test_deep_mode_overrides_are_recorded_without_changing_hard_bounds() -> None:
    plan = plan_hierarchical_narrative_scale(
        NarrativeScaleProfile(word_target_soft=1_000_000),
        quality_mode="deep",
        overrides=HierarchicalScaleOverrides(
            chapter_target=450,
            volume_target=30,
            part_target=6,
            part_turn_targets={1: 40},
        ),
    )

    assert plan.chapter_target == 450
    assert plan.volume_target == 30
    assert plan.part_target == 6
    assert plan.parts[0].turn_target == 40
    assert plan.user_locked == [
        "chapter_target",
        "volume_target",
        "part_target",
        "part_turn_targets",
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"chapter_target": 333},
        {"volume_target": 19},
        {"part_target": 3},
        {"part_turn_targets": {1: 2}},
        {"part_turn_targets": {7: 20}},
    ],
)
def test_hierarchical_overrides_reject_values_outside_derived_capacity(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        plan_hierarchical_narrative_scale(
            NarrativeScaleProfile(word_target_soft=1_000_000),
            quality_mode="deep",
            overrides=HierarchicalScaleOverrides.model_validate(overrides),
        )


def test_hierarchical_overrides_are_deep_mode_only() -> None:
    with pytest.raises(ValueError, match="deep mode"):
        plan_hierarchical_narrative_scale(
            NarrativeScaleProfile(word_target_soft=1_000_000),
            quality_mode="balanced",
            overrides=HierarchicalScaleOverrides(chapter_target=450),
        )


def test_micro_story_keeps_one_part_without_forcing_part_minimum() -> None:
    plan = plan_hierarchical_narrative_scale(
        NarrativeScaleProfile(word_target_soft=8_000),
        quality_mode="deep",
    )

    assert plan.part_target == 1
    assert len(plan.parts) == 1
    assert plan.parts[0].chapter_target == plan.chapter_target


def test_run_inputs_freeze_hierarchical_locks_without_a_book_turn_override() -> None:
    plan = hierarchical_scale_plan_from_inputs(
        {
            "length_envelope": {"word_target_soft": 1_000_000},
            "scale_overrides": {
                "chapter_target": 450,
                "volume_target": 30,
                "part_target": 6,
                "part_turn_targets": {},
            },
        },
        quality_mode="deep",
    )

    assert (plan.chapter_target, plan.volume_target, plan.part_target) == (450, 30, 6)
    assert not hasattr(plan, "turn_target")


def test_run_inputs_reject_the_retired_book_wide_turn_override() -> None:
    with pytest.raises(ValueError):
        hierarchical_scale_plan_from_inputs(
            {
                "length_envelope": {"word_target_soft": 1_000_000},
                "scale_overrides": {"turn_target": 120},
            },
            quality_mode="deep",
        )
