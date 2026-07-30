from __future__ import annotations

from typing import Any

import pytest
import asyncio

from novel_workflow.providers.base import TextProvider
from novel_workflow.orchestration.draft_regeneration import DraftRegenerationError, regenerate_stage_drafts, select_stage_draft_candidate
from novel_workflow.workflows.schemas import NovelRunState
from tests.workflow_runner_harness import (
    CapturingPlanningProvider,
    build_runner,
    detail_outline_fixture,
    outline_fixture,
    planning_workflow,
    run_and_approve,
    story_brief_fixture,
    summary_fixture,
)


class CapturingCoverExportProvider(TextProvider):
    name = "capturing-cover-export"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.text_calls = 0

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise AssertionError("runner should request structured output")

    async def generate_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append({"prompt": prompt, "task_name": task_name, "context": context, "schema": schema})
        if task_name == "info_recommend":
            return story_brief_fixture(str(context.get("title") or "雾港封面"))
        if task_name == "summary":
            return summary_fixture()
        if task_name == "outline":
            return outline_fixture()
        if task_name == "detail_outline":
            return detail_outline_fixture()
        if task_name == "chapter_text":
            self.text_calls += 1
            return _chapter_fixture(self.text_calls)
        if task_name == "cover_image":
            return _cover_fixture()
        raise AssertionError(f"unexpected task: {task_name}")


class FailingDraftProvider(CapturingCoverExportProvider):
    async def generate_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any] | None = None,
    ) -> Any:
        raise RuntimeError("provider draft failure")


@pytest.mark.asyncio
async def test_balanced_info_regeneration_keeps_three_candidates_and_selectable_history(tmp_path):
    workflow = planning_workflow(["info"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "balanced"
    provider = CapturingCoverExportProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "balanced-info-candidates"
    inputs = {
        "project_id": "p-info-candidates",
        "title": "雾港候选",
        "quality_mode": "balanced",
        "stage_configs": {},
    }
    store.create(run_id, workflow, inputs)
    state = NovelRunState(
        run_id=run_id,
        project_id="p-info-candidates",
        workflow_id=workflow.id,
        inputs=inputs,
        artifacts={"info_recommend": story_brief_fixture("雾港当前稿")},
        approval_required=True,
        stage_confirmation_state={"info": {"status": "pending"}},
    )
    store.update_state(run_id, state)
    store.request_approval(run_id, node_id="info", output_key="info_recommend", artifact=state.artifacts["info_recommend"])

    first_events = await regenerate_stage_drafts(
        runner,
        workflow,
        run_id=run_id,
        node_id="info",
        direction="强化人物之间的利益冲突",
        candidate_count=3,
    )
    first_candidates = [event for event in first_events if event["type"] == "draft_candidate_generated"]
    assert len(first_candidates) == 3
    assert len({event["candidate_id"] for event in first_candidates}) == 3
    assert "强化人物之间的利益冲突" in provider.calls[-1]["prompt"]

    await regenerate_stage_drafts(
        runner,
        workflow,
        run_id=run_id,
        node_id="info",
        direction="强化世界观硬规则",
        candidate_count=3,
    )
    draft_state = store.read(run_id)["state"]["draft_regeneration_state"]["info"]
    assert len(draft_state["candidates"]) == 3
    assert len(draft_state["history"]) == 3

    selected = select_stage_draft_candidate(
        runner,
        workflow,
        run_id=run_id,
        node_id="info",
        section=first_candidates[0]["candidate_id"],
    )
    assert selected["type"] == "draft_candidate_selected"
    assert selected["candidate_id"] == first_candidates[0]["candidate_id"]
    stored = store.read(run_id)
    assert stored["approval"]["required"] is True
    assert stored["approval"]["artifact"]["selected_title"]


@pytest.mark.asyncio
async def test_info_regeneration_failure_is_persisted_with_the_client_request_id(tmp_path):
    workflow = planning_workflow(["info"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "balanced"
    provider = FailingDraftProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "balanced-info-candidate-failure"
    inputs = {"project_id": "p-info-failure", "quality_mode": "balanced", "stage_configs": {}}
    store.create(run_id, workflow, inputs)
    state = NovelRunState(
        run_id=run_id,
        project_id="p-info-failure",
        workflow_id=workflow.id,
        inputs=inputs,
        artifacts={"info_recommend": story_brief_fixture("雾港当前稿")},
        approval_required=True,
        stage_confirmation_state={"info": {"status": "pending"}},
    )
    store.update_state(run_id, state)
    store.request_approval(run_id, node_id="info", output_key="info_recommend", artifact=state.artifacts["info_recommend"])

    with pytest.raises(DraftRegenerationError, match="provider draft failure"):
        await regenerate_stage_drafts(
            runner,
            workflow,
            run_id=run_id,
            node_id="info",
            direction="强化人物冲突",
            candidate_count=3,
            request_id="info-client-request-1",
        )

    stored = store.read(run_id)
    failure = next(event for event in reversed(stored["events"]) if event["type"] == "draft_regeneration_failed")
    assert failure["request_id"] == "info-client-request-1"
    assert stored["state"]["draft_regeneration_state"]["info"]["status"] == "failed"


@pytest.mark.asyncio
async def test_deep_chain_reaches_cover_and_export_without_returning_to_info(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text", "cover", "export"], provider_profile_id="openai-compatible")
    workflow.nodes[-2].provider_profile_id = "openai-compatible"
    workflow.stage_configs["cover"].provider_profile_id = "openai-compatible"
    workflow.nodes[-1].variant_policy.enabled = False
    workflow.stage_configs["text"].variant_policy = workflow.nodes[4].variant_policy
    provider = CapturingCoverExportProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "deep-cover-export"
    inputs = {
        "project_id": "p-cover-export",
        "title": "封面导出门禁",
        "quality_mode": "deep",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 1, "conflict_density": "中高"},
            "detail": {"chapter_count": 1, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
            "text": {"chapter_count": 1, "chapter_words": 900, "batch_generate": False},
            "cover": {"cover_style": "电影感悬疑", "aspect_ratio": "2:3"},
            "export": {"export_format": "Markdown + JSON"},
        },
    }
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "run_export_ready"
    assert "run_completed" not in event_types
    assert "cover" in {str(event.get("node_id") or "") for event in events}
    assert "export" in {str(event.get("node_id") or "") for event in events}
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "cover" for event in events)
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "export" for event in events)
    assert any(event["type"] == "node_completed" and event.get("node_id") == "export" for event in events)
    assert any(event["type"] == "parallel_delivery_started" for event in events)
    assert any(event["type"] == "parallel_delivery_ready" for event in events)
    parallel_start = next(index for index, event in enumerate(events) if event["type"] == "parallel_delivery_started")
    text_complete = next(index for index, event in enumerate(events) if event["type"] == "node_completed" and event.get("node_id") == "text")
    assert parallel_start < text_complete

    task_names = [call["task_name"] for call in provider.calls]
    assert task_names[0] == "info_recommend"
    assert "chapter_text" in task_names
    assert set(task_names) <= {"info_recommend", "summary", "outline", "detail_outline", "chapter_text", "model_review", "cover_image"}
    assert "model_review" in task_names
    assert "cover_image" in task_names
    assert provider.text_calls == 1
    state = store.read(run_id)["state"]
    assert state["runtime_phase"] == "stage_ready_to_continue"
    assert state["pending_export_return"] is True
    assert state["completed_stage_ids"] == ["info", "summary", "outline", "detail", "text", "cover", "export"]
    assert state["progress"]["cover"] == {"status": "completed", "output_key": "cover"}
    assert state["progress"]["export"] == {"status": "completed", "output_key": "export"}
    assert state["artifacts"]["cover"]["candidates"]
    assert state["artifacts"]["cover"]["selected_candidate_id"]
    export_artifact = state["artifacts"]["export"]
    assert export_artifact["manifest"]
    assert export_artifact["chapters"]
    assert export_artifact["package_status"]["ready"] is True
    assert export_artifact["package_status"]["kind"] == "md"
    assert export_artifact["validation"]["cover"] == "ready"
    assert export_artifact["validation"]["quality"] == "ready"
    assert not state["errors"]


@pytest.mark.asyncio
async def test_resume_pending_cover_checkpoint_reuses_artifact_without_regenerating(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail", "text", "cover", "export"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "deep"
    workflow.nodes[-2].provider_profile_id = "openai-compatible"
    workflow.stage_configs["cover"].provider_profile_id = "openai-compatible"
    provider = CapturingCoverExportProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "deep-cover-pending-resume"
    inputs = {
        "project_id": "p-cover-pending-resume",
        "title": "封面断线续跑门禁",
        "quality_mode": "deep",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 1, "conflict_density": "中高"},
            "detail": {"chapter_count": 1, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
            "text": {"chapter_count": 1, "chapter_words": 900, "batch_generate": False},
            "cover": {"cover_style": "电影感悬疑", "aspect_ratio": "2:3"},
            "export": {"export_format": "Markdown + JSON"},
        },
    }
    store.create(run_id, workflow, inputs)

    async def approve_until_cover() -> None:
        confirmed: set[str] = set()
        for _ in range(240):
            await asyncio.sleep(0.05)
            approval = store.read(run_id).get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id != "cover" and node_id not in confirmed:
                store.approve_artifact(run_id, node_id=node_id, output_key=str(approval["output_key"]), artifact=approval["artifact"])
                confirmed.add(node_id)
            if approval.get("required") and node_id == "cover":
                return

    first_events: list[dict[str, Any]] = []
    approver = asyncio.create_task(approve_until_cover())
    async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
        first_events.append(event)
        if event["type"] == "approval_required" and event.get("node_id") == "cover":
            break
    await approver

    cover_calls_before = [call for call in provider.calls if call["task_name"] == "cover_image"]
    assert len(cover_calls_before) == 1
    approval = store.read(run_id)["approval"]
    store.approve_artifact(run_id, node_id="cover", output_key=str(approval["output_key"]), artifact=approval["artifact"])

    resumed_events = [event async for event in runner.run(workflow, run_id=run_id, inputs=inputs)]
    cover_calls_after = [call for call in provider.calls if call["task_name"] == "cover_image"]

    assert len(cover_calls_after) == 1
    assert any(event["type"] == "stage_artifact_confirmed" and event.get("node_id") == "cover" for event in resumed_events)
    assert any(event["type"] == "node_started" and event.get("node_id") == "export" for event in resumed_events)
    assert resumed_events[-1]["type"] == "run_export_ready"


@pytest.mark.asyncio
async def test_deep_stage_draft_regeneration_emits_manual_candidate_events(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "deep"
    provider = CapturingCoverExportProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "deep-draft-regeneration"
    inputs = {
        "project_id": "p-draft-regeneration",
        "title": "换稿门禁",
        "quality_mode": "deep",
        "stage_configs": {"outline": {"volume_count": 1, "chapters_per_volume": 1, "conflict_density": "中高"}},
    }
    store.create(run_id, workflow, inputs)

    async def approve_until_outline() -> None:
        confirmed: set[str] = set()
        for _ in range(180):
            await asyncio.sleep(0.05)
            approval = store.read(run_id).get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id != "outline" and node_id not in confirmed:
                store.approve_artifact(run_id, node_id=node_id, output_key=str(approval["output_key"]), artifact=approval["artifact"])
                confirmed.add(node_id)
            if approval.get("required") and node_id == "outline":
                return

    approver = asyncio.create_task(approve_until_outline())
    async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
        if event["type"] == "approval_required" and event.get("node_id") == "outline":
            break
    await approver
    state_before = store.read(run_id)["state"]
    assert state_before["artifacts"]["outline"]["volumes"]
    assert state_before["stage_confirmation_state"]["outline"]["status"] == "pending"

    draft_events = await regenerate_stage_drafts(
        runner,
        workflow,
        run_id=run_id,
        node_id="outline",
        direction="强化卷尾钩子与伏笔回收压力",
        candidate_count=2,
    )
    event_types = [event["type"] for event in draft_events]

    assert event_types[0] == "draft_regeneration_requested"
    assert draft_events[0]["candidate_count"] == 2
    assert event_types.count("draft_candidate_generated") == 2
    assert "best_variant_selected" not in event_types
    assert all(event.get("section") in {"候选 1", "候选 2"} for event in draft_events if event["type"] == "draft_candidate_generated")
    state = store.read(run_id)["state"]
    assert state["draft_regeneration_state"]["outline"]["status"] == "completed"
    assert state["draft_regeneration_state"]["outline"]["generated_count"] == 2
    assert state["stage_confirmation_state"]["outline"]["status"] == "pending"

    approval = store.read(run_id)["approval"]
    store.approve_artifact(run_id, node_id="outline", output_key=str(approval["output_key"]), artifact=approval["artifact"])
    with pytest.raises(DraftRegenerationError):
        await regenerate_stage_drafts(
            runner,
            workflow,
            run_id=run_id,
            node_id="outline",
            direction="已确认后不允许继续换稿",
            candidate_count=1,
        )


@pytest.mark.asyncio
async def test_deep_stage_draft_candidate_selection_writes_back_selected_artifact(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline"], provider_profile_id="openai-compatible")
    workflow.quality_mode = "deep"
    provider = CapturingCoverExportProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "deep-draft-selection"
    inputs = {
        "project_id": "p-draft-selection",
        "title": "选稿写回门禁",
        "quality_mode": "deep",
        "stage_configs": {"outline": {"volume_count": 1, "chapters_per_volume": 1, "conflict_density": "中高"}},
    }
    store.create(run_id, workflow, inputs)

    async def approve_until_outline() -> None:
        confirmed: set[str] = set()
        for _ in range(180):
            await asyncio.sleep(0.05)
            approval = store.read(run_id).get("approval") or {}
            node_id = str(approval.get("node_id") or "")
            if approval.get("required") and node_id and node_id != "outline" and node_id not in confirmed:
                store.approve_artifact(run_id, node_id=node_id, output_key=str(approval["output_key"]), artifact=approval["artifact"])
                confirmed.add(node_id)
            if approval.get("required") and node_id == "outline":
                return

    approver = asyncio.create_task(approve_until_outline())
    async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
        if event["type"] == "approval_required" and event.get("node_id") == "outline":
            break
    await approver

    draft_events = await regenerate_stage_drafts(
        runner,
        workflow,
        run_id=run_id,
        node_id="outline",
        direction="强化卷尾钩子与伏笔回收压力",
        candidate_count=2,
    )
    assert any(event["type"] == "draft_candidate_generated" and event.get("section") == "候选 2" for event in draft_events)
    from novel_workflow.orchestration.draft_regeneration import select_stage_draft_candidate

    event = select_stage_draft_candidate(
        runner,
        workflow,
        run_id=run_id,
        node_id="outline",
        section="候选 2",
    )
    assert event["type"] == "draft_candidate_selected"
    state = store.read(run_id)["state"]
    assert state["draft_regeneration_state"]["outline"]["status"] == "selected"
    assert state["draft_regeneration_state"]["outline"]["selected_section"] == "候选 2"
    assert state["artifacts"]["outline"] == event["artifact"]
    assert state["progress"]["outline"] == {"status": "completed", "output_key": "outline"}
    assert store.read(run_id)["approval"]["artifact"] == event["artifact"]
    assert store.read(run_id)["approval"]["node_id"] == "outline"
    assert store.read(run_id)["approval"]["required"] is True
    assert state["stage_confirmation_state"]["outline"]["status"] == "pending"
    assert state["stage_confirmation_state"]["outline"]["node_id"] == "outline"
    assert state["stage_confirmation_state"]["outline"]["output_key"] == "outline"

    store.approve_artifact(run_id, node_id="outline", output_key="outline", artifact=event["artifact"])
    with pytest.raises(DraftRegenerationError):
        select_stage_draft_candidate(
            runner,
            workflow,
            run_id=run_id,
            node_id="outline",
            section="候选 2",
        )


def _chapter_fixture(index: int) -> dict[str, Any]:
    return {
        "chapter_title": f"第{index}章",
        "content": f"第{index}章 正文\n\n林澈沿着母带线索继续追查，伏笔与事实在旧港里彼此咬合。",
        "summary": f"第{index}章摘要",
        "wiki_writebacks": [{"target": f"第{index}章事实", "fact": "正文承接", "source_chapter": f"第{index}章"}],
        "character_shift": "人物状态推进。",
        "foreshadow_updates": [{"name": f"伏笔{index}", "status": "推进"}],
    }


def _cover_fixture() -> dict[str, Any]:
    return {
        "brief": "旧港雾夜、声纹磁带和档案馆形成悬疑封面气质。",
        "visual_keywords": ["旧港", "磁带", "雾钟", "档案馆"],
        "composition": "2:3 竖版，主角背影面对雾钟，前景放置磁带波形。",
        "copy_suggestions": ["雾港旧声", "每段回声都在改写证词"],
        "prompt": "cinematic mist harbor, cassette tape waveform, archive room, suspense novel cover",
        "candidates": [{"id": "cover-1", "image_url": "/assets/test-cover-1.png", "composition": "背影+雾钟", "palette": "冷灰蓝", "quality_summary": "主题明确，标题留白充足"}],
        "selected_candidate_id": "cover-1",
    }
