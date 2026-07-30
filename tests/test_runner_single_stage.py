from __future__ import annotations

import pytest

from tests.workflow_runner_harness import (
    CapturingInfoProvider,
    CapturingPlanningProvider,
    build_runner,
    planning_workflow,
    run_and_approve,
)


@pytest.mark.asyncio
async def test_single_info_node_runs_through_runner_checkpoint_and_store(tmp_path):
    workflow = planning_workflow(["info"], provider_profile_id="openai-compatible")
    workflow.nodes[0].model_settings.max_tokens = 768
    workflow.stage_configs["info"].model_settings = workflow.nodes[0].model_settings
    provider = CapturingInfoProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "single-info-runner"
    inputs = {"project_id": "p-single-info", "title": "单阶段真实接入门禁", "quality_mode": "balanced"}
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[:4] == ["run_started", "node_started", "artifact_validated", "node_completed"]
    assert "stage_checkpoint_ready" in event_types
    assert "demo_checkpoint_ready" not in event_types
    assert "approval_required" in event_types
    assert "stage_artifact_confirmed" in event_types
    assert event_types[-1] == "run_completed"
    assert {event.get("node_id") for event in events if event.get("node_id")} == {"info"}
    assert provider.calls[0]["task_name"] == "info_recommend"
    assert provider.calls[0]["schema"] == workflow.nodes[0].output_schema

    state = store.read(run_id)["state"]
    assert state["runtime_phase"] == "completed"
    assert state["approval_required"] is False
    assert state["completed_stage_ids"] == ["info"]
    assert state["progress"]["info"] == {"status": "completed", "output_key": "info_recommend"}
    assert state["artifacts"]["info_recommend"]["selected_title"] == "单阶段真实接入门禁"
    assert state["approved_artifacts"]["info_recommend"]["selected_title"] == "单阶段真实接入门禁"
    assert state["story_brief"]["source"] == "approved_artifact"
    assert state["wiki_refs"]
    assert state["story_bible"]["world_rules"]
    assert not state["errors"]


@pytest.mark.asyncio
async def test_info_to_summary_runner_uses_approved_brief_and_stops_before_outline(tmp_path):
    workflow = planning_workflow(["info", "summary"], provider_profile_id="openai-compatible")
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "info-summary-runner"
    inputs = {"project_id": "p-info-summary", "title": "两阶段梗概门禁", "quality_mode": "balanced"}
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[0] == "run_started"
    assert event_types[-1] == "run_completed"
    assert [event["node_id"] for event in events if event["type"] == "node_started"] == ["info", "summary"]
    assert "outline" not in {str(event.get("node_id") or "") for event in events}
    assert "memory_context_loaded" in event_types
    assert "quality_check_completed" in event_types
    assert "memory_writeback_completed" in event_types
    assert "story_bible_updated" in event_types
    assert "stage_checkpoint_ready" in event_types
    assert "demo_checkpoint_ready" not in event_types
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "summary" for event in events)

    assert [call["task_name"] for call in provider.calls] == ["info_recommend", "summary"]
    summary_call = provider.calls[1]
    assert summary_call["schema"] == workflow.nodes[1].output_schema
    assert "approved_story_brief" in summary_call["prompt"]
    assert "两阶段梗概门禁" in summary_call["prompt"]
    assert "只返回 JSON object" in summary_call["prompt"]

    state = store.read(run_id)["state"]
    assert state["runtime_phase"] == "completed"
    assert state["completed_stage_ids"] == ["info", "summary"]
    assert state["progress"]["summary"] == {"status": "completed", "output_key": "summary"}
    assert state["story_brief"]["source"] == "approved_artifact"
    assert state["artifacts"]["summary"]["full_synopsis"]
    assert len(state["artifacts"]["summary"]["act_structure"]) == 3
    assert len(state["quality_reports"]) >= 1
    assert state["worldbuilding_state"]["updated_by"] == "summary"
    assert state["story_bible"]["updated_by"] == "summary"
    assert state["story_bible"]["timeline"]
    assert state["wiki_refs"]
    assert not state["errors"]


@pytest.mark.asyncio
async def test_checkpoint_resume_reuses_confirmed_info_artifact_without_regenerating(tmp_path):
    workflow = planning_workflow(["info", "summary"], provider_profile_id="openai-compatible")
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "checkpoint-resume-info-summary"
    inputs = {"project_id": "p-checkpoint-resume", "title": "断线续跑门禁", "quality_mode": "balanced"}
    store.create(run_id, workflow, inputs)

    first_events: list[dict[str, object]] = []
    async for event in runner.run(workflow, run_id=run_id, inputs=inputs):
        first_events.append(event)
        if event["type"] == "approval_required" and event.get("node_id") == "info":
            break

    approval = store.read(run_id)["approval"]
    store.approve_artifact(
        run_id,
        node_id="info",
        output_key=str(approval["output_key"]),
        artifact=approval["artifact"],
    )

    resumed_events = [event async for event in runner.run(workflow, run_id=run_id, inputs=inputs)]

    assert first_events[-1]["type"] == "approval_required"
    assert resumed_events[0]["type"] == "run_resumed"
    assert [call["task_name"] for call in provider.calls] == ["info_recommend", "summary"]
    assert any(event["type"] == "stage_artifact_confirmed" and event.get("node_id") == "info" for event in resumed_events)
    assert any(event["type"] == "node_started" and event.get("node_id") == "summary" for event in resumed_events)
    assert resumed_events[-1]["type"] == "run_completed"

    state = store.read(run_id)["state"]
    assert state["completed_stage_ids"] == ["info", "summary"]
    assert state["story_brief"]["source"] == "approved_artifact"
    assert state["artifacts"]["summary"]["full_synopsis"]
    assert not state["errors"]


@pytest.mark.asyncio
async def test_info_summary_outline_runner_validates_volume_beats_and_stops_before_detail(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline"], provider_profile_id="openai-compatible")
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "info-summary-outline-runner"
    inputs = {
        "project_id": "p-outline",
        "title": "三阶段大纲门禁",
        "quality_mode": "balanced",
        "stage_configs": {"outline": {"volume_count": 1, "chapters_per_volume": 3, "conflict_density": "中高"}},
    }
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "run_completed"
    assert [event["node_id"] for event in events if event["type"] == "node_started"] == ["info", "summary", "outline"]
    assert "detail" not in {str(event.get("node_id") or "") for event in events}
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "outline" for event in events)
    assert event_types.count("quality_check_completed") >= 3
    assert event_types.count("memory_writeback_completed") >= 3

    assert [call["task_name"] for call in provider.calls] == ["info_recommend", "summary", "outline"]
    outline_call = provider.calls[2]
    assert outline_call["schema"] == workflow.nodes[2].output_schema
    assert "### summary" in outline_call["prompt"]
    assert "volumes" in outline_call["prompt"]
    assert "foreshadow_plan" in outline_call["prompt"]

    state = store.read(run_id)["state"]
    outline = state["artifacts"]["outline"]
    volume = outline["volumes"][0]
    assert state["runtime_phase"] == "completed"
    assert state["completed_stage_ids"] == ["info", "summary", "outline"]
    assert state["progress"]["outline"] == {"status": "completed", "output_key": "outline"}
    assert volume["title"] == "第一卷：7A-13 母带"
    assert volume["opening"]
    assert volume["development"]
    assert volume["midpoint"]
    assert volume["climax"]
    assert volume["resolution"]
    assert volume["character_progression"]
    assert volume["world_reveal"]
    assert volume["foreshadow_plan"]
    assert state["worldbuilding_state"]["updated_by"] == "outline"
    assert state["story_bible"]["updated_by"] == "outline"
    assert state["story_bible"]["volumes"]
    assert state["foreshadow_ledger"]
    assert state["wiki_refs"]
    assert not state["errors"]


@pytest.mark.asyncio
async def test_info_summary_outline_detail_runner_validates_chapter_blueprints_and_stops_before_text(tmp_path):
    workflow = planning_workflow(["info", "summary", "outline", "detail"], provider_profile_id="openai-compatible")
    provider = CapturingPlanningProvider()
    store, runner = build_runner(tmp_path, provider)
    run_id = "info-summary-outline-detail-runner"
    inputs = {
        "project_id": "p-detail",
        "title": "四阶段细纲门禁",
        "quality_mode": "balanced",
        "stage_configs": {
            "outline": {"volume_count": 1, "chapters_per_volume": 3, "conflict_density": "中高"},
            "detail": {"chapter_count": 3, "must_include": ["目标", "冲突", "伏笔", "章末钩子"]},
        },
    }
    store.create(run_id, workflow, inputs)

    events = await run_and_approve(runner, workflow, store, run_id, inputs)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "run_completed"
    assert [event["node_id"] for event in events if event["type"] == "node_started"] == ["info", "summary", "outline", "detail"]
    assert "text" not in {str(event.get("node_id") or "") for event in events}
    assert any(event["type"] == "artifact_validated" and event.get("node_id") == "detail" for event in events)
    assert event_types.count("quality_check_completed") >= 4
    assert event_types.count("memory_writeback_completed") >= 4

    assert [call["task_name"] for call in provider.calls] == ["info_recommend", "summary", "outline", "detail_outline"]
    detail_call = provider.calls[3]
    assert detail_call["schema"] == workflow.nodes[3].output_schema
    assert "### outline" in detail_call["prompt"]
    assert "chapters" in detail_call["prompt"]
    assert "wiki_candidates" in detail_call["prompt"]

    state = store.read(run_id)["state"]
    detail = state["artifacts"]["detail_outline"]
    chapters = detail["chapters"]
    assert state["runtime_phase"] == "completed"
    assert state["completed_stage_ids"] == ["info", "summary", "outline", "detail"]
    assert state["progress"]["detail"] == {"status": "completed", "output_key": "detail_outline"}
    assert len(chapters) == 3
    for chapter in chapters:
        assert chapter["chapter"]
        assert chapter["pov"]
        assert chapter["scene"]
        assert chapter["goal"]
        assert chapter["entry_state"]
        assert chapter["conflict"]
        assert chapter["stakes"]
        assert chapter["fact_reveals"]
        assert chapter["foreshadow"]
        assert chapter["character_shift"]
        assert chapter["hook"]
        assert chapter["continuity_notes"]
        assert chapter["wiki_candidates"]
    assert state["worldbuilding_state"]["updated_by"] == "detail"
    assert state["story_bible"]["updated_by"] == "detail"
    assert state["story_bible"]["timeline"]
    assert state["continuity_state"]["open_foreshadows"] >= 1
    assert state["wiki_refs"]
    assert "chapters" not in state["artifacts"]
    assert not state["errors"]
