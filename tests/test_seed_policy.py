"""Phase 12 M1 — 演示种子数据治理：叙事种子清单与 create 时清空的回归测试。"""

from __future__ import annotations

from novel_workflow.workflows.schemas import WorkflowDefinition
from novel_workflow.workflows.seed_policy import (
    NARRATIVE_SEED_FIELD_KEYS,
    NARRATIVE_SEED_GLOBAL_INPUT_KEYS,
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
    assert NARRATIVE_SEED_GLOBAL_INPUT_KEYS == {"title"}

    workflow = default_workflow()
    stage_fields = {field.key: field for node in workflow.nodes for field in node.input_schema}
    for key in NARRATIVE_SEED_FIELD_KEYS:
        assert key in stage_fields, key
        assert stage_fields[key].default not in ("", [], None), key
    global_fields = {field.key: field for field in workflow.global_inputs}
    for key in NARRATIVE_SEED_GLOBAL_INPUT_KEYS:
        assert key in global_fields, key
        assert global_fields[key].default, key


def test_scrub_clears_narrative_seeds_and_keeps_structural_defaults():
    original = default_workflow().model_dump()
    scrubbed = scrub_narrative_seeds(original)

    info = _stage_fields(scrubbed, "info")
    assert info["audience"]["default"] == ""
    assert info["core_concept"]["default"] == ""
    assert info["keywords"]["default"] == []
    assert info["taboos"]["default"] == ""
    assert info["reference_keywords"]["default"] == []
    assert info["reference_query_intent"]["default"] == ""
    # 必填标记不变：清空后这些字段回到「真实必填未填」状态
    assert info["core_concept"]["required"] is True
    assert info["keywords"]["required"] is True

    summary = _stage_fields(scrubbed, "summary")
    assert summary["ending_direction"]["default"] == ""

    global_fields = {field["key"]: field for field in scrubbed["global_inputs"]}
    assert global_fields["title"]["default"] == ""

    # 结构性默认（篇幅档位、模式、数值参数）保留
    assert info["genre"]["default"] == "悬疑"
    assert info["target_words_range"]["default"] == "80-120 万字"
    assert info["reference_mode"]["default"] == "smart_search"
    assert info["enable_web_search"]["default"] is True
    assert summary["target_words"]["default"] == 1200
    assert summary["structure"]["default"] == "起承转合"
    assert set(global_fields) == {"title"}

    # stage_configs 中的 input_schema 镜像同步清空，避免双真相源
    info_config = {field["key"]: field for field in scrubbed["stage_configs"]["info"]["input_schema"]}
    assert info_config["core_concept"]["default"] == ""
    assert info_config["keywords"]["default"] == []
    summary_config = {field["key"]: field for field in scrubbed["stage_configs"]["summary"]["input_schema"]}
    assert summary_config["ending_direction"]["default"] == ""

    # 清空结果仍是合法工作流
    WorkflowDefinition.model_validate(scrubbed)


def test_scrub_does_not_mutate_input_and_handles_minimal_payloads():
    original = default_workflow().model_dump()
    scrub_narrative_seeds(original)
    assert _stage_fields(original, "info")["core_concept"]["default"].startswith("旧港")
    assert {field["key"]: field["default"] for field in original["global_inputs"]}["title"] == "雾港旧声"

    assert scrub_narrative_seeds({}) == {}
    minimal = {"nodes": [{"id": "info", "input_schema": [{"key": "core_concept", "type": "textarea", "default": "x"}]}]}
    assert scrub_narrative_seeds(minimal)["nodes"][0]["input_schema"][0]["default"] == ""
    assert minimal["nodes"][0]["input_schema"][0]["default"] == "x"
