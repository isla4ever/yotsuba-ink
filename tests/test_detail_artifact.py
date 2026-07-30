from __future__ import annotations

import copy

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.detail_artifact import commit_detail_writebacks, detail_reference_errors
from novel_workflow.orchestration.helpers import character_graph, update_worldbuilding_state
from novel_workflow.orchestration.outline_artifact import commit_outline_writebacks
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeImageProvider, FakeTextProvider
from tests.workflow_runner_harness import detail_outline_fixture, outline_fixture, story_brief_fixture


def test_detail_contract_requires_structured_chapter_writebacks():
    artifact = detail_outline_fixture()
    chapter = artifact["chapters"][0]
    chapter["character_shift"] = "legacy free text"
    chapter["fact_reveals"] = []
    chapter["foreshadow"][0]["status"] = "open"

    validation = validate_stage_artifact("detail_outline", artifact)

    assert validation.valid is False
    assert any("character_shift" in error for error in validation.errors)
    assert any("fact_reveals" in error for error in validation.errors)
    assert any("foreshadow.0.status" in error for error in validation.errors)


def test_detail_contract_trims_text_and_rejects_duplicate_writeback_names():
    artifact = detail_outline_fixture()
    chapter = artifact["chapters"][0]
    chapter["scene"] = " 旧港档案馆 "

    trimmed = validate_stage_artifact("detail_outline", artifact)

    assert trimmed.valid is True
    assert trimmed.artifact["chapters"][0]["scene"] == "旧港档案馆"

    chapter["fact_reveals"].append(copy.deepcopy(chapter["fact_reveals"][0]))
    chapter["wiki_candidates"].append(copy.deepcopy(chapter["wiki_candidates"][0]))
    duplicate = validate_stage_artifact("detail_outline", artifact)

    assert duplicate.valid is False
    assert any("fact_reveals" in error for error in duplicate.errors)
    assert any("wiki_candidates" in error for error in duplicate.errors)


def test_detail_rejects_unknown_references_and_duplicate_entries(tmp_path):
    state, _runner = _state_and_runner(tmp_path)
    artifact = detail_outline_fixture()
    chapter = artifact["chapters"][0]
    chapter["pov"] = "陌生视角"
    chapter["character_shift"]["related_to"] = "陌生角色"
    chapter["fact_reveals"][0]["anchor"] = "不存在的设定"
    chapter["wiki_candidates"][0]["source_anchor"] = "不存在的设定"
    chapter["fact_reveals"].append(copy.deepcopy(chapter["fact_reveals"][0]))
    chapter["wiki_candidates"].append(copy.deepcopy(chapter["wiki_candidates"][0]))
    chapter["foreshadow"].append(copy.deepcopy(chapter["foreshadow"][0]))
    artifact["chapters"][1]["chapter"] = chapter["chapter"]

    errors = detail_reference_errors(state, artifact)

    assert any("pov must reference" in error for error in errors)
    assert any("related_to must reference" in error for error in errors)
    assert any("fact_reveals.0.anchor must reference" in error for error in errors)
    assert any("source_anchor must reference" in error for error in errors)
    assert any("duplicates an existing chapter fact" in error for error in errors)
    assert any("duplicates an existing chapter Wiki candidate" in error for error in errors)
    assert any("duplicates an existing chapter clue" in error for error in errors)
    assert any("chapter duplicates" in error for error in errors)


def test_detail_final_writeback_updates_all_targets_once(tmp_path):
    state, runner = _state_and_runner(tmp_path)
    node = next(item for item in default_workflow().nodes if item.id == "detail")
    artifact = detail_outline_fixture()
    artifact["chapters"][0]["character_shift"]["change"] = "人工定稿后主动保护母带"
    artifact["chapters"][0]["wiki_candidates"][0]["fact"] = "人工确认的十年前声纹证词"

    first_events = commit_detail_writebacks(runner, node, artifact, state, state.run_id)
    second_events = commit_detail_writebacks(runner, node, artifact, state, state.run_id)

    assert [event["type"] for event in first_events] == [
        "memory_writeback_completed", "story_bible_updated", "character_graph_updated", "worldbuilding_updated"
    ]
    assert second_events == []
    assert len(state.wiki_refs) == 2  # Outline and Detail each write once.
    assert state.character_graph.updated_by == "detail"
    assert state.story_bible.character_profiles["林澈"]["detail_shifts"][0]["change"] == "人工定稿后主动保护母带"
    assert state.worldbuilding_state["detail_facts"][0]["anchor"] == "雾钟"
    assert state.worldbuilding_state["wiki_candidates"][0]["fact"] == "人工确认的十年前声纹证词"
    assert any(item["source"] == "detail" and item["name"] == "父亲签章" for item in state.foreshadow_ledger)
    assert state.stage_display_artifacts["detail_confirmed_writeback"]["status"] == "committed"


def test_chapter_context_reads_confirmed_structured_detail(tmp_path):
    state, runner = _state_and_runner(tmp_path)
    artifact = detail_outline_fixture()
    artifact["chapters"][1]["goal"] = "人工定稿后的第二章追查目标"
    artifact["chapters"][1]["character_shift"]["motivation"] = "人工定稿后的证人保护动机"
    state.artifacts["detail_outline"] = artifact

    packet = runner.quality_engine.build_chapter_context(chapter_index=2, total_chapters=3, state=state)

    assert "人工定稿后的第二章追查目标" in packet.chapter_outline
    assert "人工定稿后的证人保护动机" in packet.chapter_outline
    assert "蓝潮名单" in packet.chapter_outline
    assert "匿名删改签名[投放]" in packet.chapter_outline


def test_chapter_context_uses_the_exact_previous_chapter_and_keeps_first_chapter_clean(tmp_path):
    state, runner = _state_and_runner(tmp_path)
    state.story_bible.chapter_summaries = [
        {"chapter": "第2章", "summary": "第二章真实摘要", "context_kind": "normal"},
        {"chapter": "第9章", "summary": "不相关的旧摘要", "context_kind": "normal"},
    ]

    first = runner.quality_engine.build_chapter_context(chapter_index=1, total_chapters=3, state=state)
    third = runner.quality_engine.build_chapter_context(chapter_index=3, total_chapters=3, state=state)

    assert first.previous_chapter_summary == ""
    assert third.previous_chapter_summary == "第二章真实摘要"


def _state_and_runner(tmp_path) -> tuple[NovelRunState, NovelWorkflowRunner]:
    workflow = default_workflow()
    info = story_brief_fixture("雾港细纲")
    outline = outline_fixture()
    state = NovelRunState(
        run_id="detail-writeback",
        project_id="p-detail",
        workflow_id=workflow.id,
        inputs={"project_id": "p-detail", "quality_mode": "deep"},
        approved_artifacts={"info_recommend": info, "outline": outline},
        artifacts={"info_recommend": info, "outline": outline},
        story_brief={"source": "approved_artifact", "content": info},
        character_graph=character_graph("info", info),
    )
    info_node = next(item for item in workflow.nodes if item.id == "info")
    outline_node = next(item for item in workflow.nodes if item.id == "outline")
    update_worldbuilding_state(info_node, info, state)
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    runner = NovelWorkflowRunner(providers=_registry(), wiki_store=wiki, run_store=store)
    commit_outline_writebacks(runner, outline_node, outline, state, state.run_id)
    return state, runner


def _registry() -> ProviderRegistry:
    text = FakeTextProvider()
    return ProviderRegistry(
        text_provider=text,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": text},
        image_providers={},
    )
