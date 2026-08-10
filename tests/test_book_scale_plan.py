from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from novel_workflow.workflows.book_scale_plan import (
    book_acceptance_maximum,
    book_scale_plan_from_inputs,
    build_book_scale_plan,
    chapter_acceptance_maximum,
    freeze_book_scale_inputs,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "apps"
    / "web"
    / "test-fixtures"
    / "book-scale-contract-cases.json"
)


@pytest.mark.parametrize("case", json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
def test_book_scale_contract_cases(case: dict[str, Any]) -> None:
    plan = build_book_scale_plan(
        target_mode=case["target_mode"],
        target_value=case["target_value"],
    )
    expected = case["expected"]

    assert plan.total_chars == expected["total_chars"]
    assert plan.total_chapters == expected["total_chapters"]
    assert plan.volume_count == expected["volume_count"]
    assert plan.chapters_per_volume == expected["chapters_per_volume"]
    assert plan.chapter_target_chars == expected["chapter_target_chars"]
    assert [plan.chapter_soft_min_chars, plan.chapter_soft_max_chars] == expected[
        "chapter_soft_chars"
    ]
    assert [plan.chapter_hard_min_chars, plan.chapter_hard_max_chars] == expected[
        "chapter_hard_chars"
    ]
    assert [plan.book_soft_min_chars, plan.book_soft_max_chars] == expected[
        "book_soft_chars"
    ]
    assert [volume.target_chars for volume in plan.volumes] == expected[
        "volume_target_chars"
    ]
    assert sum(volume.chapter_count for volume in plan.volumes) == plan.total_chapters
    assert sum(volume.target_chars for volume in plan.volumes) == plan.total_chars
    assert plan.volumes[0].chapter_start == 1
    assert plan.volumes[-1].chapter_end == plan.total_chapters


@pytest.mark.parametrize(
    ("target_mode", "target_value"),
    [
        ("total_chars", 2_999),
        ("total_chars", 5_000_001),
        ("total_chapters", 0),
        ("total_chapters", 2_501),
        ("total_chapters", 1.5),
        ("total_chapters", True),
        ("total_chapters", "3"),
    ],
)
def test_freeze_rejects_invalid_targets(
    target_mode: str,
    target_value: object,
) -> None:
    with pytest.raises(ValueError):
        freeze_book_scale_inputs(
            {
                "book_scale_target": {
                    "target_mode": target_mode,
                    "target_value": target_value,
                }
            }
        )


def test_freeze_derives_plan_and_removes_start_target() -> None:
    frozen = freeze_book_scale_inputs(
        {
            "title": "体量测试",
            "book_scale_target": {
                "target_mode": "total_chapters",
                "target_value": 17,
            },
        }
    )

    assert "book_scale_target" not in frozen
    assert frozen["title"] == "体量测试"
    plan = book_scale_plan_from_inputs(frozen)
    assert plan.total_chapters == 17
    assert plan.chapters_per_volume == [9, 8]


def test_freeze_rejects_client_derived_plan() -> None:
    plan = build_book_scale_plan(target_mode="total_chapters", target_value=17)

    with pytest.raises(ValueError, match="不得提交派生 BookScalePlan"):
        freeze_book_scale_inputs(
            {
                "book_scale_target": {
                    "target_mode": "total_chapters",
                    "target_value": 17,
                },
                "book_scale_plan": plan.model_dump(mode="json"),
            }
        )


def test_stage_budgets_expand_without_scaling_linearly_with_book_length() -> None:
    short = build_book_scale_plan(target_mode="total_chapters", target_value=3)
    long = build_book_scale_plan(target_mode="total_chars", target_value=1_000_000)

    assert short.budget_for_stage("text").target_chars == 2_000
    assert long.budget_for_stage("text").target_chars == 2_000
    assert long.budget_for_stage("info").target_chars > short.budget_for_stage("info").target_chars
    assert long.budget_for_stage("summary").target_chars > short.budget_for_stage("summary").target_chars
    assert long.budget_for_stage("cover").target_chars == short.budget_for_stage("cover").target_chars


def test_book_acceptance_capacity_scales_without_turning_soft_target_into_hard_limit() -> None:
    short = build_book_scale_plan(target_mode="total_chapters", target_value=3)
    long = build_book_scale_plan(target_mode="total_chars", target_value=100_000)

    assert short.book_soft_max_chars == 7_200
    assert book_acceptance_maximum(short) == 8_940
    assert long.book_soft_max_chars == 105_000
    assert book_acceptance_maximum(long) == 108_000


def test_run_g_final_chapter_can_use_controlled_book_overage() -> None:
    plan = build_book_scale_plan(target_mode="total_chapters", target_value=3)

    assert chapter_acceptance_maximum(
        plan,
        chapter_index=3,
        completed_chapter_chars=5_662,
    ) == 3_450


def test_run_h_chapter_target_does_not_reapply_derived_book_chars() -> None:
    plan = build_book_scale_plan(target_mode="total_chapters", target_value=3)

    assert chapter_acceptance_maximum(
        plan,
        chapter_index=3,
        completed_chapter_chars=6_063,
    ) == 3_450
