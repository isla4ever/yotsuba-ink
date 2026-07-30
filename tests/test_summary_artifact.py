from __future__ import annotations

import asyncio
import copy

import pytest

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.helpers import character_graph
from novel_workflow.orchestration.summary_artifact import commit_summary_writebacks, summary_reference_errors
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeImageProvider, FakeTextProvider


def test_summary_rejects_unknown_and_duplicate_info_character_references():
    state = _state()
    unknown = _summary_artifact()
    unknown["character_arcs"][0]["name"] = "陌生角色"
    duplicate = _summary_artifact()
    duplicate["character_arcs"].append(copy.deepcopy(duplicate["character_arcs"][0]))

    assert summary_reference_errors(state, unknown) == [
        "character_arcs.0.name must reference a confirmed Info character"
    ]
    assert summary_reference_errors(state, duplicate) == [
        "character_arcs.1.name duplicates an existing character arc"
    ]


def test_summary_contract_requires_character_writebacks_and_consistency_checks():
    artifact = _summary_artifact()
    artifact["character_arcs"] = []
    artifact["consistency_checks"] = []

    validation = validate_stage_artifact("summary", artifact)

    assert validation.valid is False
    assert any("character_arcs" in error for error in validation.errors)
    assert any("consistency_checks" in error for error in validation.errors)


def test_summary_writeback_updates_graph_story_bible_and_memory_once(tmp_path):
    workflow = default_workflow()
    summary = next(node for node in workflow.nodes if node.id == "summary")
    state = _state()
    artifact = _summary_artifact()
    run_id = state.run_id
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    store.create(run_id, workflow, state.inputs)
    store.update_state(run_id, state)
    runner = NovelWorkflowRunner(providers=_fake_registry(), wiki_store=wiki, run_store=store)

    first_events = commit_summary_writebacks(runner, summary, artifact, state, run_id)
    second_events = commit_summary_writebacks(runner, summary, artifact, state, run_id)

    profile = state.story_bible.character_profiles["林澈"]
    assert [event["type"] for event in first_events] == [
        "memory_writeback_completed",
        "story_bible_updated",
        "character_graph_updated",
    ]
    assert second_events == []
    assert len(state.wiki_refs) == 1
    assert wiki.status(state.project_id)["documents"] == 1
    assert profile["arc"] == "从回避旧案到主动公开证据"
    assert profile["pressure"] == "父亲签章可能证明家人参与蓝潮实验"
    assert profile["next"] == "在分卷阶段继续核验证据与亲情边界"
    assert state.character_graph.nodes[0].status == "父亲签章可能证明家人参与蓝潮实验"
    assert state.character_graph.updated_by == "summary"


@pytest.mark.asyncio
async def test_deep_summary_approval_uses_edited_artifact_for_writeback_and_next_stage(tmp_path):
    class RecordingProvider(FakeTextProvider):
        def __init__(self) -> None:
            self.summary_seen_by_outline = ""

        async def generate_structured(self, prompt, *, task_name, context, schema=None):
            if task_name == "outline":
                self.summary_seen_by_outline = str(context["artifacts"]["summary"]["full_synopsis"])
            return await super().generate_structured(prompt, task_name=task_name, context=context, schema=schema)

    workflow = default_workflow()
    workflow.quality_mode = "deep"
    allowed = {"info", "summary", "outline"}
    workflow.nodes = [node for node in workflow.nodes if node.id in allowed]
    workflow.edges = [edge for edge in workflow.edges if edge.source in allowed and edge.target in allowed]
    provider = RecordingProvider()
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    runner = NovelWorkflowRunner(providers=_fake_registry(provider), wiki_store=wiki, run_store=store)
    run_id = "deep-summary-edited"
    inputs = {"project_id": "p-deep-summary", "title": "雾港编辑稿", "quality_mode": "deep"}
    store.create(run_id, workflow, inputs)
    edited_synopsis = "人工编辑后的完整梗概：林澈选择公开档案，并承担家族秘密曝光的代价。"
    edited_pressure = "人工改写后的关系压力"

    async def approve_stages() -> None:
        approved: set[str] = set()
        for _ in range(300):
            await asyncio.sleep(0.02)
            stored = store.read(run_id)
            approval = stored.get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id not in approved:
                artifact = copy.deepcopy(approval.get("artifact"))
                if node_id == "summary":
                    artifact["full_synopsis"] = edited_synopsis
                    artifact["character_arcs"][0]["pressure"] = edited_pressure
                store.approve_artifact(
                    run_id,
                    node_id=node_id,
                    output_key=str(approval.get("output_key") or node_id),
                    artifact=artifact,
                )
                approved.add(node_id)
            if (stored.get("state") or {}).get("runtime_phase") in {"completed", "failed"}:
                return

    approver = asyncio.create_task(approve_stages())
    events = []
    try:
        async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
            events.append(event)
    finally:
        await approver

    saved = store.read(run_id)["state"]
    summary_events = [
        event for event in events
        if event["type"] == "memory_writeback_completed" and event.get("node_id") == "summary"
    ]
    assert saved["artifacts"]["summary"]["full_synopsis"] == edited_synopsis
    assert saved["approved_artifacts"]["summary"]["full_synopsis"] == edited_synopsis
    assert saved["story_bible"]["character_profiles"]["林澈"]["pressure"] == edited_pressure
    assert saved["character_graph"]["updated_by"] == "outline"
    assert provider.summary_seen_by_outline == edited_synopsis
    assert len(summary_events) == 1


@pytest.mark.asyncio
async def test_resuming_completed_summary_finalizes_writeback_only_once(tmp_path):
    workflow = default_workflow()
    summary = next(node for node in workflow.nodes if node.id == "summary")
    workflow.nodes = [summary]
    workflow.edges = []
    state = _state(run_id="summary-resume")
    artifact = _summary_artifact()
    state.run_has_started = True
    state.completed_stage_ids = ["summary"]
    state.artifacts["summary"] = artifact
    state.approved_artifacts["summary"] = artifact
    state.stage_confirmation_state["summary"] = {
        "status": "confirmed",
        "node_id": "summary",
        "node_type": "summary",
        "output_key": "summary",
        "event_emitted": True,
    }
    store = RunStore(tmp_path / "runs")
    wiki = WikiStore(tmp_path / "wiki")
    store.create(state.run_id, workflow, state.inputs)
    store.update_state(state.run_id, state)
    runner = NovelWorkflowRunner(providers=_fake_registry(), wiki_store=wiki, run_store=store)

    for _ in range(2):
        async for _event in runner.run(workflow, run_id=state.run_id, inputs=state.inputs):
            pass

    saved = store.read(state.run_id)
    summary_memory_events = [
        event for event in saved["events"]
        if event["type"] == "memory_writeback_completed" and event.get("node_id") == "summary"
    ]
    assert len(summary_memory_events) == 1
    assert wiki.status(state.project_id)["documents"] == 1
    assert saved["state"]["stage_display_artifacts"]["summary_confirmed_writeback"]["status"] == "committed"


def _state(run_id: str = "summary-writeback") -> NovelRunState:
    info = _info_artifact()
    return NovelRunState(
        run_id=run_id,
        project_id="p-summary",
        workflow_id="default-novel-workflow",
        inputs={"project_id": "p-summary", "quality_mode": "deep"},
        approved_artifacts={"info_recommend": info},
        artifacts={"info_recommend": info},
        story_brief={"source": "approved_artifact", "content": info},
        character_graph=character_graph("info", info),
    )


def _fake_registry(provider: FakeTextProvider | None = None) -> ProviderRegistry:
    text = provider or FakeTextProvider()
    return ProviderRegistry(
        text_provider=text,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": text},
        image_providers={},
    )


def _info_artifact() -> dict:
    return {
        "selected_title": "雾港旧声",
        "title_candidates": ["雾港旧声"],
        "synopsis": "林澈从旧磁带中追查蓝潮实验。",
        "worldbuilding_detail": "旧港雾钟记录声纹证词。",
        "characters": [{
            "name": "林澈",
            "identity": "声纹修复师",
            "motivation": "查清父亲与旧案关系",
            "relations": "与许望舒合作",
            "growth_direction": "从回避到公开证据",
        }],
        "relationships": [],
        "tags": ["悬疑"],
        "downstream_constraints": ["雾钟是技术装置"],
        "risk_notes": [],
    }


def _summary_artifact() -> dict:
    return {
        "one_liner": "一盘旧磁带重新打开旧港失踪案。",
        "full_synopsis": "林澈追查旧案，最终公开第一层真相并承担代价。",
        "act_structure": [{"title": "入局", "goal": "确认旧案存在", "turn": "证词被改写"}],
        "core_conflict": "个人记忆与公共档案冲突。",
        "character_arcs": [{
            "name": "林澈",
            "arc": "从回避旧案到主动公开证据",
            "pressure": "父亲签章可能证明家人参与蓝潮实验",
            "next": "在分卷阶段继续核验证据与亲情边界",
        }],
        "key_turns": [{"label": "缺页名单", "detail": "三人确认删改记录。"}],
        "ending_resolution": "公开第一层真相，保留父亲签章长线。",
        "consistency_checks": ["雾钟仍是技术装置"],
    }
