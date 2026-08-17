from __future__ import annotations

import pytest

from novel_workflow.runtime.graph.output_budget import (
    OutputBudgetExceeded,
    OutputBudgetPlanner,
)
from novel_workflow.runtime.graph.provider_prompt_compiler import render_structured_prompt
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.phase27_bindings import provider_binding


def _binding(max_tokens: int = 12_000) -> ProviderBinding:
    return provider_binding("detail", max_tokens=max_tokens)


def test_structured_budget_is_smaller_than_frozen_provider_ceiling() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))
    binding = _binding(max_tokens=8_000)
    context = {
        "target": "spine",
        "material": {
            "scale_plan": {
                "turn_target": 27,
                "turn_capacity_range": [23, 34],
                "chapter_target": 40,
            }
        },
    }
    plan = planner.for_stage(
        "spine",
        binding,
        context,
    )

    assert plan.kind == "spine"
    assert plan.expected_items == 27
    assert plan.item_cap == 27
    assert plan.max_tokens < 6_307
    assert plan.bind(binding).max_tokens == plan.max_tokens


def test_spine_budget_rejects_a_profile_cap_below_frozen_scale_range() -> None:
    planner = OutputBudgetPlanner(
        NarrativeScaleProfile(
            word_target_soft=100_000,
            json_item_caps={"spine_turns": 24},
        )
    )
    context = {
        "target": "spine",
        "material": {
            "scale_plan": {
                "turn_target": 27,
                "turn_capacity_range": [23, 34],
                "chapter_target": 40,
            }
        },
    }

    with pytest.raises(OutputBudgetExceeded, match="requires 27 turns"):
        planner.for_stage("spine", _binding(), context)


def test_non_thinking_pro_brief_uses_compact_structured_budget() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))
    binding = provider_binding(
        "brief",
        template_id="deepseek-text",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-pro",
        max_tokens=4_600,
    )

    context = {"target": "brief", "material": {}}
    plan = planner.for_stage(
        "brief",
        binding,
        context,
    )

    assert plan.max_tokens < binding.max_tokens
    assert plan.field_char_cap == 1_801
    assert plan.bind(binding).max_tokens == plan.max_tokens
    prompt = render_structured_prompt(
        plan.bind(binding),
        "brief",
        planner.attach(context, plan),
        {"type": "object"},
    )
    assert "within about 1801 characters" in prompt
    assert "within about 1 characters" not in prompt


def test_non_thinking_flash_brief_uses_compact_structured_budget() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))
    binding = provider_binding(
        "brief",
        template_id="deepseek-text",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        max_tokens=4_600,
    )

    plan = planner.for_stage(
        "brief",
        binding,
        {"target": "brief", "material": {}},
    )

    assert plan.max_tokens < binding.max_tokens
    assert plan.bind(binding).max_tokens == plan.max_tokens


def test_unit_that_exceeds_frozen_item_cap_fails_before_provider_call() -> None:
    planner = OutputBudgetPlanner(
        NarrativeScaleProfile(
            word_target_soft=100_000,
            json_item_caps={"cast_dossiers": 2},
        )
    )
    context = {
        "target": "cast",
        "material": {
            "subject_refs": [
                {"id": "subject-1"},
                {"id": "subject-2"},
                {"id": "subject-3"},
            ]
        },
    }

    with pytest.raises(OutputBudgetExceeded, match="split the unit"):
        planner.for_stage("cast", _binding(), context)


def test_unit_that_exceeds_provider_ceiling_fails_without_clamping() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))

    with pytest.raises(OutputBudgetExceeded, match="frozen Provider ceiling"):
        planner.for_stage(
            "brief",
            _binding(max_tokens=1_000),
            {"target": "brief", "material": {}},
        )


def test_role_demand_budget_reserves_the_dynamic_hard_max_not_the_editorial_center() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=240_000))
    context = {
        "target": "cast",
        "material": {
            "scale_plan": {
                "cast_recommended_range": [3, 16],
                "cast_hard_max": 16,
            }
        },
    }

    plan = planner.for_proposal("role_demand", _binding(10_000), context)

    assert plan.expected_items == 16
    assert plan.item_cap == 16
    assert plan.max_tokens == 8_963


def test_role_demand_budget_rejects_a_second_character_count_authority() -> None:
    planner = OutputBudgetPlanner(
        NarrativeScaleProfile(
            word_target_soft=240_000,
            json_item_caps={"role_demands": 12},
        )
    )
    context = {
        "target": "cast",
        "material": {
            "scale_plan": {
                "cast_recommended_range": [3, 16],
                "cast_hard_max": 16,
            }
        },
    }

    with pytest.raises(OutputBudgetExceeded, match="scale allows 16 subjects"):
        planner.for_proposal("role_demand", _binding(10_000), context)


def test_cast_planning_review_budgets_are_bounded_sidecars() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))

    role_review = planner.for_proposal("role_demand_review", _binding(10_000), {})
    cast_review = planner.for_proposal("cast_review", _binding(10_000), {})

    assert (role_review.expected_items, role_review.item_cap) == (8, 8)
    assert (cast_review.expected_items, cast_review.item_cap) == (8, 8)


def test_detail_capacity_changes_with_provider_ceiling() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))

    assert planner.detail_chapter_capacity(_binding(6_000)) == 3
    assert planner.detail_chapter_capacity(_binding(6_000)) < planner.detail_chapter_capacity(
        _binding(12_000)
    )


def test_detail_budget_uses_the_run_specific_scene_range() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))
    context = {
        "target": "detail",
        "budget_basis": {"expected_chapters": 2},
        "material": {
            "scale_projection": {
                "scenes_per_chapter_min": 1,
                "scenes_per_chapter_max": 4,
            }
        },
    }

    compact = planner.for_stage("detail", _binding(), context)
    expanded = planner.for_stage(
        "detail",
        _binding(),
        {
            **context,
            "material": {
                "scale_projection": {
                    "scenes_per_chapter_min": 2,
                    "scenes_per_chapter_max": 6,
                }
            },
        },
    )

    assert compact.scene_cap == 4
    assert expanded.scene_cap == 6
    assert expanded.max_tokens > compact.max_tokens


def test_budget_sidecar_is_strict_and_does_not_change_artifact_context() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))
    context = {"target": "cover", "material": {"accepted_story_metadata": {}}}
    plan = planner.for_stage("cover", _binding(), context)

    attached = planner.attach(context, plan)

    assert attached["material"] == context["material"]
    assert attached["output_budget"]["max_tokens"] == plan.max_tokens
    assert "estimated_chars" not in attached["output_budget"]


def test_detail_layout_budget_uses_the_dynamic_chapter_slot_count() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(word_target_soft=100_000))
    context = {
        "target": "detail",
        "material": {
            "scale_plan": {
                "chapter_target": 45,
                "chapter_range": [34, 50],
                "volume_ranges": [],
            }
        },
    }

    plan = planner.for_proposal("detail_layout", _binding(12_000), context)

    assert plan.kind == "detail_layout"
    assert plan.expected_items == 45
    assert plan.item_cap == 200
    assert plan.max_tokens < 12_000


def test_detail_layout_budget_rejects_a_frozen_cap_below_the_book_range() -> None:
    planner = OutputBudgetPlanner(
        NarrativeScaleProfile(
            word_target_soft=100_000,
            json_item_caps={"detail_layout_chapters": 40},
        )
    )
    context = {
        "target": "detail",
        "material": {"scale_plan": {"chapter_range": [34, 50]}},
    }

    with pytest.raises(OutputBudgetExceeded, match="expects 50 items"):
        planner.for_proposal("detail_layout", _binding(12_000), context)


def test_volume_boundary_budget_uses_the_frozen_volume_target_inside_the_cap() -> None:
    planner = OutputBudgetPlanner(
        NarrativeScaleProfile(
            word_target_soft=100_000,
            volume_candidate_cap=9,
            json_item_caps={"volume_boundaries": 7},
        )
    )
    context = {
        "target": "volumes",
        "material": {
            "story_spine": {"turns": [{"id": f"turn-{index}"} for index in range(12)]},
            "scale_plan": {"volume_target": 3},
        },
    }

    plan = planner.for_proposal("volume_boundary", _binding(12_000), context)

    assert plan.expected_items == 3
    assert plan.item_cap == 7
