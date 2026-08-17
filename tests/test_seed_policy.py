"""Phase 12 M1 — 演示种子数据治理：叙事种子清单与 create 时清空的回归测试。"""

from __future__ import annotations

from novel_workflow.workflows.schemas import WorkflowDefinition
from novel_workflow.workflows.seed_policy import (
    NARRATIVE_SEED_FIELD_KEYS,
    materialize_project_workflow,
    scrub_narrative_seeds,
)
from novel_workflow.workflows.templates import default_workflow


def _stage_fields(workflow_data: dict, stage_id: str) -> dict[str, dict]:
    node = next(node for node in workflow_data["nodes"] if node["id"] == stage_id)
    return {field["key"]: field for field in node["input_schema"]}


def test_narrative_seed_catalog_matches_template_demo_defaults():
    """清单里的每个字段都必须真实存在于默认模板并且带非空演示值，防止改模板后清单漂移。"""
    assert NARRATIVE_SEED_FIELD_KEYS == {
        "audience",
        "core_concept",
        "keywords",
        "taboos",
        "reference_keywords",
        "reference_query_intent",
        "ending_direction",
    }
    workflow = default_workflow()
    stage_fields = {field.key: field for node in workflow.nodes for field in node.input_schema}
    for key in NARRATIVE_SEED_FIELD_KEYS:
        assert key in stage_fields, key
        assert stage_fields[key].default not in ("", [], None), key
    assert workflow.global_inputs == []


def test_scrub_clears_narrative_seeds_and_keeps_structural_defaults():
    original = default_workflow().model_dump()
    scrubbed = scrub_narrative_seeds(original)

    brief = _stage_fields(scrubbed, "brief")
    assert brief["audience"]["default"] == ""
    assert brief["core_concept"]["default"] == ""
    assert brief["keywords"]["default"] == []
    assert brief["taboos"]["default"] == ""
    assert brief["reference_keywords"]["default"] == []
    assert brief["reference_query_intent"]["default"] == ""
    # 一段创作想法是唯一硬输入；其余立项提示可由 Brief 推断。
    assert brief["core_concept"]["required"] is True
    assert brief["audience"]["required"] is False
    assert brief["keywords"]["required"] is False
    assert brief["taboos"]["required"] is False

    spine = _stage_fields(scrubbed, "spine")
    assert spine["ending_direction"]["default"] == ""

    # 结构性默认保留；成书体量由 LengthEnvelope 与 ScaleProfile 提供软约束。
    assert brief["genre"]["default"] == "自动判断"
    assert brief["genre"]["required"] is False
    assert "target_words_range" not in brief
    assert brief["reference_mode"]["default"] == "smart_search"
    assert brief["enable_web_search"]["default"] is True
    assert "target_words" not in spine
    assert spine["structure"]["default"] == "自适应因果链"
    assert scrubbed["global_inputs"] == []

    assert "stage_configs" not in scrubbed

    # 清空结果仍是合法工作流
    WorkflowDefinition.model_validate(scrubbed)


def test_scrub_does_not_mutate_input_and_handles_minimal_payloads():
    original = default_workflow().model_dump()
    scrub_narrative_seeds(original)
    assert _stage_fields(original, "brief")["core_concept"]["default"].startswith("旧港")
    assert original["global_inputs"] == []

    assert scrub_narrative_seeds({}) == {}
    minimal = {"nodes": [{"id": "brief", "input_schema": [{"key": "core_concept", "type": "textarea", "default": "x"}]}]}
    assert scrub_narrative_seeds(minimal)["nodes"][0]["input_schema"][0]["default"] == ""
    assert minimal["nodes"][0]["input_schema"][0]["default"] == "x"


def test_materialize_project_workflow_writes_the_users_idea_into_brief():
    materialized = materialize_project_workflow(
        default_workflow().model_dump(mode="json"),
        "  一名修表匠发现整座城市每天都会丢失一分钟。  ",
    )

    assert _stage_fields(materialized, "brief")["core_concept"]["default"] == (
        "一名修表匠发现整座城市每天都会丢失一分钟。"
    )
    assert _stage_fields(materialized, "brief")["keywords"]["default"] == []
