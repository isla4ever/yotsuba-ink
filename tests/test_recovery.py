from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.recovery import (
    mark_stable_checkpoint,
    prepare_checkpoint_recovery,
    register_failure,
)
from novel_workflow.providers.base import TextProvider
from novel_workflow.usage.budget import authorize_provider_call, settle_provider_call
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.workflow_runner_harness import build_runner, detail_outline_fixture, planning_workflow


class InvalidChapterProvider(TextProvider):
    name = "invalid-chapter"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise AssertionError("chapter runner should request structured output")

    async def generate_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any] | None = None,
    ) -> Any:
        del prompt, task_name, context, schema
        self.calls += 1
        return {"content": ""}


def test_recovery_state_opens_circuit_after_three_failures_and_preserves_checkpoint() -> None:
    state = NovelRunState(run_id="recovery-state", project_id="p-recovery", workflow_id="workflow")
    artifact = {"full_synopsis": "已确认梗概"}
    checkpoint = mark_stable_checkpoint(
        state,
        node_id="summary",
        node_type="summary",
        output_key="summary",
        status="completed",
        artifact=artifact,
    )

    for attempt in range(1, 4):
        failure = register_failure(
            state,
            node_id="outline",
            node_type="outline",
            code="provider_error",
            message=f"provider timeout {attempt}",
        )
        assert failure["consecutive"] == attempt

    assert state.recovery_state["status"] == "open"
    assert state.recovery_state["needs_recovery"] is True
    assert state.recovery_state["last_stable_checkpoint"] == checkpoint
    assert state.recovery_state["total_failures"] == 3
    with pytest.raises(ValueError, match="熔断上限"):
        prepare_checkpoint_recovery(state)


def test_recovery_refuses_to_restart_without_a_stable_checkpoint() -> None:
    state = NovelRunState(run_id="no-checkpoint", project_id="p-no-checkpoint", workflow_id="workflow")
    register_failure(
        state,
        node_id="info",
        node_type="info_recommend",
        code="provider_error",
        message="provider timeout",
    )

    with pytest.raises(ValueError, match="稳定检查点"):
        prepare_checkpoint_recovery(state)


def test_fail_resume_fail_keeps_streak_until_a_new_stable_checkpoint() -> None:
    state = NovelRunState(run_id="failure-streak", project_id="p-failure-streak", workflow_id="workflow")
    mark_stable_checkpoint(
        state,
        node_id="summary",
        node_type="summary",
        output_key="summary",
        status="completed",
        artifact={"full_synopsis": "稳定梗概"},
    )

    for attempt in range(1, 4):
        register_failure(
            state,
            node_id="outline",
            node_type="outline",
            code="provider_error",
            message=f"provider timeout {attempt}",
        )
        assert state.recovery_state["consecutive_failures"] == attempt
        if attempt < 3:
            prepare_checkpoint_recovery(state)
            assert state.recovery_state["consecutive_failures"] == attempt

    assert state.recovery_state["status"] == "open"
    with pytest.raises(ValueError, match="熔断上限"):
        prepare_checkpoint_recovery(state)

    mark_stable_checkpoint(
        state,
        node_id="outline",
        node_type="outline",
        output_key="outline",
        status="completed",
        artifact={"volumes": []},
    )
    assert state.recovery_state["consecutive_failures"] == 0


def test_resume_api_unlocks_a_degraded_run_from_last_stable_checkpoint(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    workflow = default_workflow()
    run_id = "checkpoint-recovery-api"
    app.state.run_store.create(run_id, workflow, {"project_id": "p-checkpoint-recovery"})
    state = NovelRunState(
        run_id=run_id,
        project_id="p-checkpoint-recovery",
        workflow_id=workflow.id,
        run_has_started=True,
        current_stage_id="outline",
        current_stage_type="outline",
        runtime_phase="failed",
    )
    checkpoint = mark_stable_checkpoint(
        state,
        node_id="summary",
        node_type="summary",
        output_key="summary",
        status="completed",
        artifact={"full_synopsis": "稳定梗概"},
    )
    failure = register_failure(
        state,
        node_id="outline",
        node_type="outline",
        code="provider_error",
        message="provider timeout",
    )
    state.errors = [{"type": "node_failed", "node_id": "outline", "error": failure["message"]}]
    state.progress["outline"] = {"status": "failed", "error": failure["message"]}
    app.state.run_store.update_state(run_id, state)

    response = TestClient(app).post(f"/api/runs/{run_id}/resume")

    assert response.status_code == 200
    assert response.json()["status"] == "checkpoint_recovery_requested"
    assert response.json()["checkpoint"] == checkpoint
    stored = app.state.run_store.read(run_id)
    recovered = stored["state"]
    assert recovered["errors"] == []
    assert recovered["runtime_phase"] == "checkpoint_recovery"
    assert recovered["progress"]["outline"]["status"] == "planned"
    assert recovered["recovery_state"]["needs_recovery"] is False
    assert recovered["recovery_state"]["failure_history"][0]["message"] == "provider timeout"
    assert stored["events"][-1]["type"] == "run_checkpoint_recovery_requested"


def test_snapshot_restore_resume_prepares_one_budget_retry(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    workflow = default_workflow()
    run_id = "snapshot-budget-recovery"
    inputs = {"project_id": "p-snapshot-budget", "quality_mode": "balanced"}
    app.state.run_store.create(run_id, workflow, inputs)
    state = NovelRunState(
        run_id=run_id,
        project_id="p-snapshot-budget",
        workflow_id=workflow.id,
        inputs=inputs,
        run_has_started=True,
        current_stage_id="summary",
        current_stage_type="summary",
        runtime_phase="cockpit_streaming",
    )
    mark_stable_checkpoint(
        state,
        node_id="info",
        node_type="info_recommend",
        output_key="info_recommend",
        status="completed",
        artifact={"selected_title": "稳定立项"},
    )
    app.state.run_store.update_state(run_id, state)
    app.state.run_store.append_event(
        run_id,
        {"type": "stage_checkpoint_ready", "run_id": run_id, "node_id": "info", "output_key": "info_recommend"},
    )
    snapshot_id = app.state.run_store.latest_snapshot(run_id)["snapshot_id"]

    node = workflow.nodes[1]
    prompt = "会失败的梗概生成"
    decision = authorize_provider_call(state, node, prompt_text=prompt)
    settle_provider_call(
        state,
        scope_key=decision["scope_key"],
        operation_id=decision["operation_id"],
        prompt_text=prompt,
        output_text="",
        failed=True,
    )
    register_failure(
        state,
        node_id=node.id,
        node_type=node.type,
        code="provider_error",
        message="provider timeout",
    )
    state.runtime_phase = "failed"
    state.errors = [{"type": "node_failed", "node_id": node.id, "error": "provider timeout"}]
    app.state.run_store.update_state(run_id, state)
    app.state.run_store.append_event(run_id, {"type": "run_failed", "run_id": run_id})
    consumed_before = state.budget_state["run_consumed_tokens"]
    app.state.run_store.restore_snapshot(
        run_id,
        snapshot_id,
        request_id="snapshot-budget-restore",
        expected_revision=app.state.run_store.read(run_id)["state_revision"],
    )

    response = TestClient(app).post(f"/api/runs/{run_id}/resume")
    assert response.status_code == 200
    stored = app.state.run_store.read(run_id)
    recovered = NovelRunState.model_validate(stored["state"])
    scope = recovered.budget_state["scopes"][node.id]
    assert scope["recovery_retry_ready"] is True
    assert recovered.budget_state["run_consumed_tokens"] == consumed_before
    retry = authorize_provider_call(recovered, node, prompt_text=prompt)
    assert retry["allowed"] is True
    assert recovered.budget_state["scopes"][node.id]["attempts"]["retry"] == 1
    assert authorize_provider_call(recovered, node, prompt_text=prompt)["allowed"] is False


@pytest.mark.asyncio
async def test_invalid_chapter_candidates_do_not_complete_text_stage(tmp_path: Any) -> None:
    provider = InvalidChapterProvider()
    store, runner = build_runner(tmp_path, provider)
    workflow = planning_workflow(["text"], provider_profile_id="openai-compatible")
    text_node = workflow.nodes[0]
    text_node.variant_policy.enabled = False
    workflow.stage_configs["text"].variant_policy.enabled = False
    inputs = {
        "project_id": "p-invalid-chapter",
        "quality_mode": "balanced",
        "stage_configs": {"text": {"max_chapters_to_generate": 1}},
    }
    run_id = "invalid-chapter-recovery"
    store.create(run_id, workflow, inputs)
    state = NovelRunState(
        run_id=run_id,
        project_id="p-invalid-chapter",
        workflow_id=workflow.id,
        inputs=inputs,
        run_has_started=True,
        mode_locked=True,
        current_stage_id="text",
        current_stage_type="chapter_text",
        artifacts={"detail_outline": {"chapters": detail_outline_fixture()["chapters"][:1]}},
    )
    store.update_state(run_id, state)

    events = [event async for event in runner.run(workflow, run_id=run_id, inputs=inputs)]

    assert provider.calls == 1
    assert any(event["type"] == "node_failed" for event in events)
    assert events[-1]["type"] == "run_failed"
    assert not any(event["type"] == "node_completed" and event.get("node_id") == "text" for event in events)
    stored_state = store.read(run_id)["state"]
    assert "text" not in stored_state["completed_stage_ids"]
    assert stored_state["recovery_state"]["needs_recovery"] is True
