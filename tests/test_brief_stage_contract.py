from __future__ import annotations

import pytest

from novel_workflow.output_contracts.artifacts_vnext import StoryBriefArtifact
from novel_workflow.runtime.graph.stage_executor import _bind_story_brief
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from novel_workflow.workflows.prompt_templates import default_prompt_templates
from tests.fakes import fake_brief_payload


def test_brief_binding_preserves_the_run_length_envelope() -> None:
    payload = {
        **fake_brief_payload(),
        "title": "盐库遗证",
        "length_envelope": {
            "word_target_soft": 60_000,
        },
    }

    bound = _bind_story_brief(
        payload,
        NarrativeScaleProfile(
            word_target_soft=100_000,
        ),
    )

    assert bound["title"] == "盐库遗证"
    assert bound["length_envelope"] == {
        "word_target_soft": 100_000,
    }


def test_brief_prompt_freezes_story_strategy_without_preplanning_task_gates() -> None:
    prompt = next(
        item.content for item in default_prompt_templates() if item.stage_type == "brief"
    )

    assert "不替 Spine 预写行动方案" in prompt
    assert "不得提前决定潜入、闯入、取物、找工具、权限升级、抓捕逃脱" in prompt
    assert "只保留会在多个阶段持续成立" in prompt
    assert "一次性障碍属于后续剧情" in prompt
    assert "project_brief.taboos 是全书硬约束" in prompt


@pytest.mark.parametrize("field", ["premise", "promise", "theme", "ending_promise", "voice"])
def test_brief_rejects_meta_placeholders_before_spine(field: str) -> None:
    payload = {**fake_brief_payload(), field: "这个内容后续再补充。"}

    with pytest.raises(ValueError, match="resolved at Brief stage"):
        StoryBriefArtifact.model_validate(payload)


def test_brief_allows_story_level_unknowns_when_the_plan_is_concrete() -> None:
    payload = {
        **fake_brief_payload(),
        "premise": "她知道母带被删除，却不知道是谁留下了最后一段回声。",
    }

    StoryBriefArtifact.model_validate(payload)
