from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_workflow.orchestration.recovery import register_failure
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow


def test_history_cursor_sorting_and_filters_are_stable(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    _create_run(store, "run-a", project_id="project-a", runtime_phase="idle_config")
    _create_run(store, "run-b", project_id="project-b", runtime_phase="completed")
    _create_run(store, "run-c", project_id="project-a", runtime_phase="stage_ready_to_continue")
    _set_history_time(store, "run-a", "2026-07-19T01:00:00+00:00")
    _set_history_time(store, "run-b", "2026-07-19T01:00:00+00:00")
    _set_history_time(store, "run-c", "2026-07-19T02:00:00+00:00")

    first_page, cursor = store.list_history(limit=2)
    second_page, final_cursor = store.list_history(limit=2, cursor=cursor)

    assert [item["run_id"] for item in first_page] == ["run-c", "run-b"]
    assert [item["run_id"] for item in second_page] == ["run-a"]
    assert cursor
    assert final_cursor == ""
    assert len({item["run_id"] for item in [*first_page, *second_page]}) == 3
    assert [item["run_id"] for item in store.list_history(project_id="project-a")[0]] == ["run-c", "run-a"]
    assert [item["run_id"] for item in store.list_history(status="completed")[0]] == ["run-b"]


def test_restore_rejects_foreign_old_and_completed_snapshots(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    first_snapshot = _create_checkpointed_run(store, "run-a", title="第一版")
    state = NovelRunState.model_validate(store.read("run-a")["state"])
    state.artifacts["summary"] = {"full_synopsis": "第二版"}
    store.update_state("run-a", state)
    store.append_event("run-a", {"type": "stage_checkpoint_ready", "run_id": "run-a", "node_id": "summary"})
    latest_snapshot = store.latest_snapshot("run-a")["snapshot_id"]
    foreign_snapshot = _create_checkpointed_run(store, "run-b", title="其他运行")

    with pytest.raises(ValueError, match="不属于当前运行"):
        store.restore_snapshot(
            "run-a",
            foreign_snapshot,
            request_id="restore-foreign-snapshot",
            expected_revision=store.read("run-a")["state_revision"],
        )
    with pytest.raises(ValueError, match="最新稳定检查点"):
        store.restore_snapshot(
            "run-a",
            first_snapshot,
            request_id="restore-old-snapshot",
            expected_revision=store.read("run-a")["state_revision"],
        )

    completed = NovelRunState.model_validate(store.read("run-a")["state"])
    completed.runtime_phase = "completed"
    store.update_state("run-a", completed)
    store.append_event("run-a", {"type": "run_completed", "run_id": "run-a", "node_id": "export"})
    with pytest.raises(ValueError, match="已完成运行"):
        store.restore_snapshot(
            "run-a",
            store.latest_snapshot("run-a")["snapshot_id"],
            request_id="restore-completed-run",
            expected_revision=store.read("run-a")["state_revision"],
        )
    assert latest_snapshot != first_snapshot
    assert store.list_history(status="completed")[0][0]["can_resume"] is False


def test_repeated_restore_does_not_append_events_or_roll_back_ledgers(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    snapshot_id = _create_checkpointed_run(store, "restore-idempotent", title="稳定稿")
    state = NovelRunState.model_validate(store.read("restore-idempotent")["state"])
    state.budget_state = {"run_consumed_tokens": 321, "run_reserved_tokens": 0}
    register_failure(
        state,
        node_id="outline",
        node_type="outline",
        code="provider_error",
        message="provider timeout",
    )
    state.runtime_phase = "failed"
    store.update_state("restore-idempotent", state)
    store.append_event("restore-idempotent", {"type": "run_failed", "run_id": "restore-idempotent"})
    revision = store.read("restore-idempotent")["state_revision"]

    first = store.restore_snapshot(
        "restore-idempotent",
        snapshot_id,
        request_id="repeatable-restore-request",
        expected_revision=revision,
    )
    after_first = store.read("restore-idempotent")
    second = store.restore_snapshot(
        "restore-idempotent",
        snapshot_id,
        request_id="repeatable-restore-request",
        expected_revision=revision,
    )
    after_second = store.read("restore-idempotent")

    assert second == first
    assert after_second["state_revision"] == after_first["state_revision"]
    assert len(after_second["events"]) == len(after_first["events"])
    assert after_second["state"]["budget_state"]["run_consumed_tokens"] == 321
    assert after_second["state"]["recovery_state"]["total_failures"] == 1
    assert after_second["paused"] is True
    assert after_second["state"]["runtime_phase"] == "checkpoint_recovery"


def _create_run(store: RunStore, run_id: str, *, project_id: str, runtime_phase: str) -> None:
    workflow = default_workflow()
    store.create(run_id, workflow, {"project_id": project_id, "title": run_id, "quality_mode": "balanced"})
    state = NovelRunState(
        run_id=run_id,
        project_id=project_id,
        workflow_id=workflow.id,
        inputs={"project_id": project_id, "title": run_id, "quality_mode": "balanced"},
        run_has_started=runtime_phase != "idle_config",
        runtime_phase=runtime_phase,
        current_stage_id="export" if runtime_phase == "completed" else "info",
        current_stage_label="导出交付" if runtime_phase == "completed" else "小说信息推荐",
        current_stage_type="export" if runtime_phase == "completed" else "info_recommend",
    )
    store.update_state(run_id, state)


def _create_checkpointed_run(store: RunStore, run_id: str, *, title: str) -> str:
    workflow = default_workflow()
    store.create(run_id, workflow, {"project_id": run_id, "title": title, "quality_mode": "deep"})
    state = NovelRunState(
        run_id=run_id,
        project_id=run_id,
        workflow_id=workflow.id,
        inputs={"project_id": run_id, "title": title, "quality_mode": "deep"},
        run_has_started=True,
        runtime_phase="stage_ready_to_continue",
        current_stage_id="summary",
        current_stage_label="全书梗概",
        current_stage_type="summary",
        artifacts={"summary": {"full_synopsis": title}},
        budget_state={"run_consumed_tokens": 12},
    )
    store.update_state(run_id, state)
    store.append_event(run_id, {"type": "stage_checkpoint_ready", "run_id": run_id, "node_id": "summary"})
    return str(store.latest_snapshot(run_id)["snapshot_id"])


def _set_history_time(store: RunStore, run_id: str, timestamp: str) -> None:
    run_path = store.run_dir(run_id) / "run.json"
    data = json.loads(run_path.read_text(encoding="utf-8"))
    data["created_at"] = timestamp
    data["updated_at"] = timestamp
    if (data.get("state") or {}).get("runtime_phase") == "completed":
        data["completed_at"] = timestamp
        data["state"]["run_completed_at"] = timestamp
    run_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (store.run_dir(run_id) / "run_meta.json").unlink(missing_ok=True)
