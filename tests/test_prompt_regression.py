from __future__ import annotations

import json
from pathlib import Path

from novel_workflow.stages.prompt_layers import PromptSection, assemble_user

from tests.prompt_regression_harness import (
    PROMPT_STAGE_IDS,
    build_stage_plan,
    plan_snapshot,
    prompt_template,
)

FIXTURE_DIR = Path(__file__).with_name("fixtures")


def test_all_generation_stage_prompt_snapshots_are_stable_and_deterministic():
    expected = json.loads((FIXTURE_DIR / "prompt_plan_snapshots.json").read_text(encoding="utf-8"))
    actual = {stage_id: plan_snapshot(build_stage_plan(stage_id)) for stage_id in PROMPT_STAGE_IDS}
    repeated = {stage_id: plan_snapshot(build_stage_plan(stage_id)) for stage_id in PROMPT_STAGE_IDS}
    assert actual == repeated
    assert actual == expected["stages"]


def test_snapshot_contract_retains_hard_constraints_schema_and_stage_quotas():
    schema_markers = {
        "info": ("selected_title", "background", "voice_spec", "title_candidates 恰好 5 个"),
        "summary": ("full_synopsis", "character_arcs", "ending_resolution", "禁止新增任何人物"),
        "outline": ("volumes", "character_progression", "foreshadow_plan", "new_characters 0-4 条"),
        "detail": ("chapters", "character_shift", "wiki_candidates", "new_npcs 引入最多 2 名"),
        "text": ("chapter_title", "wiki_writebacks", "foreshadow_updates", "禁止引入任何未注册的人物"),
        "cover": ("visual_keywords", "copy_suggestions", "selected_candidate_id", "candidates 2-3 个"),
    }
    for stage_id, markers in schema_markers.items():
        plan = build_stage_plan(stage_id)
        assert "## 硬约束（不可违背，优先级最高）" in plan.system
        assert "## 输出结构" in plan.system
        assert "## 输出长度配置" in plan.system
        assert all(marker in plan.system or marker in plan.user for marker in markers)
        assert plan.dropped_layers == []


def test_compact_contracts_match_runtime_validators_and_continuity_policy():
    outline = build_stage_plan("outline")
    detail = build_stage_plan("detail")
    text = build_stage_plan("text")
    cover = build_stage_plan("cover")

    assert all(marker in outline.system for marker in ("new_characters", "tier", "faction_stance"))
    assert "fact_reveals/foreshadow/wiki_candidates 各 1-3 条" in detail.system
    assert "image_url" not in cover.system
    assert "默认沿上一章结果连续续写" in text.system
    assert "上一卷结局造成的后果" in text.system
    assert "只有细纲明确标注时才允许视角转移、倒叙或时间跳切" in text.system


def test_text_prompt_makes_continuation_the_default_and_carries_real_volume_handoff_context():
    plan = build_stage_plan("text")

    assert "默认沿上一章结果连续续写" in plan.system
    assert "只有细纲明确标注时才允许视角转移、倒叙或时间跳切" in plan.system
    assert "用动作、后果、物证或人物反应" in plan.system
    assert "卷首先呈现上一卷结局造成的后果" in plan.system
    assert "所属卷: 潮声证词 / 第1-6章" in plan.user
    assert "下一卷目标: 追查潮汐钟改写记录的机制" in plan.user
    assert "叙事衔接指令" in plan.user


def test_same_story_input_ab_cases_only_change_the_experiment_template_layer():
    fixture = json.loads((FIXTURE_DIR / "prompt_ab_cases.json").read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        baseline = build_stage_plan(case["stage_id"])
        candidate = build_stage_plan(case["stage_id"], template_suffix=case["candidate_instruction"])
        baseline_template = prompt_template(f"prompt-{case['stage_id']}")
        candidate_template = f"{baseline_template}\n\n{case['candidate_instruction']}"

        assert baseline.system == candidate.system
        assert candidate.user == baseline.user.replace(baseline_template, candidate_template, 1)
        assert baseline.render() != candidate.render()
        assert baseline.dropped_layers == candidate.dropped_layers == []
        assert all(marker in candidate.system for marker in case["required_system_markers"])
        assert case["candidate_instruction"] in candidate.user


def test_crop_order_is_exact_and_never_drops_task_or_upstream_layers():
    user, dropped = assemble_user(
        [
            PromptSection(1, "task", "T" * 100),
            PromptSection(2, "upstream", "U" * 100),
            PromptSection(3, "entities", "E" * 100),
            PromptSection(4, "voice", "V" * 100),
            PromptSection(5, "reference", "R" * 100),
        ],
        char_budget=250,
    )
    assert dropped == ["reference", "voice", "entities"]
    assert "T" * 100 in user and "U" * 100 in user
    assert "E" not in user and "V" not in user and "R" not in user
