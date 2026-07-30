from __future__ import annotations

import copy

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.detail_artifact import detail_reference_errors
from novel_workflow.orchestration.helpers import character_graph, update_worldbuilding_state
from novel_workflow.orchestration.outline_artifact import commit_outline_writebacks, outline_reference_errors
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.quality.engine import QualityEngine
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeImageProvider, FakeTextProvider
from tests.workflow_runner_harness import detail_outline_fixture, outline_fixture, story_brief_fixture

NEW_SUPPORTING = {"name": "程雾侦", "role": "港务集团内线", "faction": "港务集团", "stance": "立场摇摆", "relation_to_protagonist": "向林澈出售情报"}


def _state(run_id: str = "quota-run") -> NovelRunState:
    info = story_brief_fixture("雾港配额")
    state = NovelRunState(
        run_id=run_id,
        project_id="p-quota",
        workflow_id="default-novel-workflow",
        inputs={"project_id": "p-quota", "quality_mode": "deep"},
        approved_artifacts={"info_recommend": info},
        artifacts={"info_recommend": info},
        story_brief={"source": "approved_artifact", "content": info},
        character_graph=character_graph("info", info),
    )
    info_node = next(node for node in default_workflow().nodes if node.id == "info")
    update_worldbuilding_state(info_node, info, state)
    return state


def test_outline_new_character_becomes_referencable_in_same_artifact():
    state = _state()
    artifact = outline_fixture()
    volume = artifact["volumes"][0]
    volume["new_characters"] = [copy.deepcopy(NEW_SUPPORTING)]
    volume["character_progression"].append(
        {"character": "程雾侦", "related_to": "林澈", "relation": "情报交易", "kind": "trade", "polarity": "complex", "pressure": "身份可能暴露", "change": "开始倒向调查同盟", "impact": "为第二卷提供内部证据"}
    )
    assert outline_reference_errors(state, artifact) == []


def test_outline_new_character_rejects_major_tier_and_duplicates():
    state = _state()
    artifact = outline_fixture()
    volume = artifact["volumes"][0]
    volume["new_characters"] = [
        {**copy.deepcopy(NEW_SUPPORTING), "tier": "主角"},
        {"name": "林澈", "role": "重复已有人物"},
    ]
    errors = outline_reference_errors(state, artifact)
    assert any("cannot introduce protagonist/major" in error for error in errors)
    assert any("duplicates an existing character" in error for error in errors)


def test_outline_contract_caps_new_characters_at_four_per_volume():
    artifact = outline_fixture()
    artifact["volumes"][0]["new_characters"] = [
        {"name": f"配角{index}", "role": "结构职责"} for index in range(5)
    ]
    validation = validate_stage_artifact("outline", artifact)
    assert validation.valid is False
    assert any("new_characters" in error for error in validation.errors)


def test_outline_commit_registers_supporting_character_with_provenance(tmp_path):
    workflow = default_workflow()
    outline_node = next(node for node in workflow.nodes if node.id == "outline")
    state = _state("quota-outline-commit")
    artifact = outline_fixture()
    artifact["volumes"][0]["new_characters"] = [copy.deepcopy(NEW_SUPPORTING)]
    store = RunStore(tmp_path / "runs")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    runner = NovelWorkflowRunner(providers=_registry(), wiki_store=WikiStore(tmp_path / "wiki"), run_store=store)

    commit_outline_writebacks(runner, outline_node, artifact, state, state.run_id)

    node = next(item for item in state.character_graph.nodes if item.name == "程雾侦")
    assert node.tier == "supporting"
    assert node.first_appearance_stage == "outline"
    assert node.faction == "港务集团" and node.faction_id
    assert any(faction.name == "港务集团" for faction in state.character_graph.factions)
    assert state.story_bible.character_profiles["程雾侦"]["tier"] == "supporting"


def test_detail_new_npcs_register_but_cannot_take_pov_or_shift():
    state = _state()
    artifact = detail_outline_fixture()
    chapter = artifact["chapters"][0]
    chapter["new_npcs"] = [{"name": "守闸员老蔡", "role": "码头闸口守夜人"}]
    assert detail_reference_errors(state, artifact) == []

    npc_pov = copy.deepcopy(artifact)
    npc_pov["chapters"][0]["pov"] = "守闸员老蔡"
    errors = detail_reference_errors(state, npc_pov)
    assert any("pov must reference" in error for error in errors)

    duplicate = copy.deepcopy(artifact)
    duplicate["chapters"][1]["new_npcs"] = [{"name": "守闸员老蔡", "role": "重复登记"}]
    errors = detail_reference_errors(state, duplicate)
    assert any("new_npcs.0.name duplicates" in error for error in errors)


def test_detail_contract_caps_new_npcs_at_two_per_chapter():
    artifact = detail_outline_fixture()
    artifact["chapters"][0]["new_npcs"] = [
        {"name": f"路人{index}", "role": "背景人物"} for index in range(3)
    ]
    validation = validate_stage_artifact("detail_outline", artifact)
    assert validation.valid is False
    assert any("new_npcs" in error for error in validation.errors)


def test_info_quota_findings_flag_thin_cast_and_overloaded_worldbuilding():
    workflow = default_workflow()
    info_node = next(node for node in workflow.nodes if node.id == "info")
    engine = QualityEngine()
    state = _state()

    thin = story_brief_fixture("配额-人物过少")
    report = engine.check_stage(info_node, thin, story_bible=state.story_bible, mode="deep")
    quota_findings = [item for item in report.findings if item.dimension == "expansion_quota"]
    assert any("低于立项基线配额" in item.message for item in quota_findings)
    assert all(not item.blocking for item in quota_findings)

    overloaded = story_brief_fixture("配额-设定过载")
    overloaded["characters"] = [
        {"name": f"角色{index}", "identity": "身份", "motivation": "动机", "relations": "关系"} for index in range(10)
    ]
    overloaded["worldbuilding_detail"] = "；".join(f"硬设定{index}" for index in range(14))
    report = engine.check_stage(info_node, overloaded, story_bible=state.story_bible, mode="deep")
    messages = [item.message for item in report.findings if item.dimension == "expansion_quota"]
    assert any("超过立项基线配额" in message for message in messages)
    assert any("世界观硬设定" in message for message in messages)


def _registry() -> ProviderRegistry:
    text = FakeTextProvider()
    return ProviderRegistry(
        text_provider=text,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": text},
        image_providers={},
    )
