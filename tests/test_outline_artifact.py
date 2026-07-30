from __future__ import annotations

import asyncio
import copy

import pytest

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.helpers import character_graph, update_worldbuilding_state
from novel_workflow.orchestration.outline_artifact import commit_outline_writebacks, outline_reference_errors
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeImageProvider, FakeTextProvider
from tests.workflow_runner_harness import outline_fixture, story_brief_fixture


def test_outline_contract_requires_structured_dependency_writebacks():
    artifact = outline_fixture()
    artifact["volumes"][0]["character_progression"][0].pop("pressure")
    artifact["volumes"][0]["world_reveal"] = []
    artifact["volumes"][0]["foreshadow_plan"][0]["status"] = "open"

    validation = validate_stage_artifact("outline", artifact)

    assert validation.valid is False
    assert any("pressure" in error for error in validation.errors)
    assert any("world_reveal" in error for error in validation.errors)
    assert any("foreshadow_plan.0.status" in error for error in validation.errors)


def test_outline_rejects_unknown_references_and_duplicate_entries():
    state = _state()
    artifact = outline_fixture()
    volume = artifact["volumes"][0]
    volume["character_progression"][0]["related_to"] = "陌生角色"
    volume["character_progression"].append(copy.deepcopy(volume["character_progression"][0]))
    volume["world_reveal"][0]["anchor"] = "不存在的世界观"
    volume["foreshadow_plan"].append(copy.deepcopy(volume["foreshadow_plan"][0]))

    errors = outline_reference_errors(state, artifact)

    assert any("related_to must reference" in error for error in errors)
    assert any("duplicates an existing character relationship" in error for error in errors)
    assert any("anchor must reference" in error for error in errors)
    assert any("duplicates an existing clue" in error for error in errors)


def test_outline_writeback_updates_all_targets_and_memory_once(tmp_path):
    workflow = default_workflow()
    outline = next(node for node in workflow.nodes if node.id == "outline")
    state = _state()
    artifact = outline_fixture()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    runner = NovelWorkflowRunner(providers=_registry(), wiki_store=wiki, run_store=store)

    first_events = commit_outline_writebacks(runner, outline, artifact, state, state.run_id)
    second_events = commit_outline_writebacks(runner, outline, artifact, state, state.run_id)

    progression = state.story_bible.character_profiles["林澈"]["outline_progressions"][0]
    reveal = state.worldbuilding_state["outline_reveals"][0]
    clue = next(item for item in state.foreshadow_ledger if item["name"] == "父亲签章")
    assert [event["type"] for event in first_events] == [
        "memory_writeback_completed", "story_bible_updated", "character_graph_updated", "worldbuilding_updated"
    ]
    assert second_events == []
    assert len(state.wiki_refs) == 1
    assert progression["pressure"] == "公开证据可能暴露证人"
    assert state.character_graph.updated_by == "outline"
    assert reveal["anchor"] == "雾钟"
    assert "只能记录和筛选既有声纹" in state.story_bible.world_rules
    assert clue["status"] == "投放"
    assert state.continuity_state["open_foreshadows"] >= 1


@pytest.mark.asyncio
async def test_deep_outline_approval_commits_edited_artifact_for_detail_context(tmp_path):
    class RecordingProvider(FakeTextProvider):
        def __init__(self) -> None:
            self.outline_seen_by_detail: dict = {}

        async def generate_structured(self, prompt, *, task_name, context, schema=None):
            if task_name == "detail_outline":
                self.outline_seen_by_detail = copy.deepcopy(context["artifacts"]["outline"])
            return await super().generate_structured(prompt, task_name=task_name, context=context, schema=schema)

    workflow = default_workflow()
    workflow.quality_mode = "deep"
    allowed = {"info", "summary", "outline", "detail"}
    workflow.nodes = [node for node in workflow.nodes if node.id in allowed]
    workflow.edges = [edge for edge in workflow.edges if edge.source in allowed and edge.target in allowed]
    provider = RecordingProvider()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    runner = NovelWorkflowRunner(providers=_registry(provider), wiki_store=wiki, run_store=store)
    run_id = "deep-outline-edited"
    inputs = {"project_id": "p-deep-outline", "title": "雾港大纲编辑稿", "quality_mode": "deep"}
    store.create(run_id, workflow, inputs)
    edited_pressure = "人工定稿后的调查同盟压力"
    edited_reveal = "人工定稿后的雾钟揭示"

    async def approve_stages() -> None:
        approved: set[str] = set()
        for _ in range(400):
            await asyncio.sleep(0.02)
            stored = store.read(run_id)
            approval = stored.get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id not in approved:
                artifact = copy.deepcopy(approval["artifact"])
                if node_id == "outline":
                    artifact["volumes"][0]["character_progression"][0]["pressure"] = edited_pressure
                    artifact["volumes"][0]["world_reveal"][0]["reveal"] = edited_reveal
                store.approve_artifact(run_id, node_id=node_id, output_key=str(approval["output_key"]), artifact=artifact)
                approved.add(node_id)
            if (stored.get("state") or {}).get("runtime_phase") in {"completed", "failed"}:
                return

    approver = asyncio.create_task(approve_stages())
    events: list[dict] = []
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        await approver

    saved = store.read(run_id)["state"]
    outline_memory_events = [event for event in events if event["type"] == "memory_writeback_completed" and event.get("node_id") == "outline"]
    assert saved["artifacts"]["outline"]["volumes"][0]["character_progression"][0]["pressure"] == edited_pressure
    assert saved["story_bible"]["character_profiles"]["林澈"]["outline_progressions"][0]["pressure"] == edited_pressure
    assert saved["worldbuilding_state"]["outline_reveals"][0]["reveal"] == edited_reveal
    assert provider.outline_seen_by_detail["volumes"][0]["world_reveal"][0]["reveal"] == edited_reveal
    assert len(outline_memory_events) == 1


def _state() -> NovelRunState:
    info = story_brief_fixture("雾港大纲")
    state = NovelRunState(
        run_id="outline-writeback",
        project_id="p-outline",
        workflow_id="default-novel-workflow",
        inputs={"project_id": "p-outline", "quality_mode": "deep"},
        approved_artifacts={"info_recommend": info},
        artifacts={"info_recommend": info},
        story_brief={"source": "approved_artifact", "content": info},
        character_graph=character_graph("info", info),
    )
    info_node = next(node for node in default_workflow().nodes if node.id == "info")
    update_worldbuilding_state(info_node, info, state)
    return state


def _registry(provider: FakeTextProvider | None = None) -> ProviderRegistry:
    text = provider or FakeTextProvider()
    return ProviderRegistry(
        text_provider=text,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": text},
        image_providers={},
    )
