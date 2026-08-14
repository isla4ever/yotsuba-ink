from __future__ import annotations

import pytest

from novel_workflow.runtime.graph.output_budget import (
    OutputBudgetExceeded,
    OutputBudgetPlanner,
)
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.phase27_bindings import provider_binding


def _binding(max_tokens: int = 12_000) -> ProviderBinding:
    return provider_binding("detail", max_tokens=max_tokens)


def test_structured_budget_is_smaller_than_frozen_provider_ceiling() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile())
    plan = planner.for_stage(
        "spine",
        _binding(),
        {"target": "spine", "material": {}},
    )

    assert plan.kind == "spine"
    assert plan.item_cap == 8
    assert plan.max_tokens < 12_000
    assert plan.bind(_binding()).max_tokens == plan.max_tokens


def test_unit_that_exceeds_frozen_item_cap_fails_before_provider_call() -> None:
    planner = OutputBudgetPlanner(
        NarrativeScaleProfile(json_item_caps={"cast_dossiers": 2})
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
    planner = OutputBudgetPlanner(NarrativeScaleProfile())

    with pytest.raises(OutputBudgetExceeded, match="frozen Provider ceiling"):
        planner.for_stage(
            "brief",
            _binding(max_tokens=1_000),
            {"target": "brief", "material": {}},
        )


def test_detail_capacity_changes_with_provider_ceiling() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile(chapter_scene_cap=6))

    assert planner.detail_chapter_capacity(_binding(6_000)) < planner.detail_chapter_capacity(
        _binding(12_000)
    )


def test_budget_sidecar_is_strict_and_does_not_change_artifact_context() -> None:
    planner = OutputBudgetPlanner(NarrativeScaleProfile())
    context = {"target": "cover", "material": {"accepted_story_metadata": {}}}
    plan = planner.for_stage("cover", _binding(), context)

    attached = planner.attach(context, plan)

    assert attached["material"] == context["material"]
    assert attached["output_budget"]["max_tokens"] == plan.max_tokens
    assert "estimated_chars" not in attached["output_budget"]


def test_detail_segments_may_outnumber_sparse_volume_turns() -> None:
    """A 100k-word volume can need more capacity segments than it has turns.

    Adjacent segments then share an anchor turn (ordered, full coverage)
    instead of failing the run at detail.load_context.
    """
    from novel_workflow.runtime.graph.context_compiler import _partition_contiguous

    turns = [f"turn-{index}" for index in range(1, 7)]
    groups = _partition_contiguous(turns, 9)

    assert len(groups) == 9
    assert all(len(group) == 1 for group in groups)
    anchors = [group[0] for group in groups]
    assert anchors == sorted(anchors, key=lambda ref: int(ref.split("-")[1]))
    assert set(anchors) == set(turns)

    # The dense case keeps its exact contiguous split.
    dense = _partition_contiguous(turns, 3)
    assert dense == [turns[0:2], turns[2:4], turns[4:6]]
