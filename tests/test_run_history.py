from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.recovery import register_failure
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow


def _checkpointed_store(tmp_path: Path) -> tuple[RunStore, str, str]:
    store = RunStore(tmp_path / "runs")
    workflow = default_workflow()
    run_id = "history-run"
    store.create(run_id, workflow, {"project_id": "history-project", "title": "历史测试", "quality_mode": "balanced"})
    state = NovelRunState(
        run_id=run_id,
        project_id="history-project",
        workflow_id=workflow.id,
        inputs={"project_id": "history-project", "title": "历史测试", "quality_mode": "balanced"},
        run_has_started=True,
        current_stage_id="info",
        current_stage_label="小说信息推荐",
        current_stage_type="info_recommend",
        runtime_phase="stage_ready_to_continue",
        artifacts={"info_recommend": {"selected_title": "历史测试"}},
        budget_state={"run_consumed_tokens": 12},
    )
    store.update_state(run_id, state)
    store.append_event(run_id, {"type": "stage_checkpoint_ready", "run_id": run_id, "node_id": "info"})
    snapshot_id = store.latest_snapshot(run_id)["snapshot_id"]
    return store, run_id, snapshot_id


def test_run_history_is_compact_and_snapshots_are_restorable(tmp_path: Path) -> None:
    store, run_id, snapshot_id = _checkpointed_store(tmp_path)

    history, cursor = store.list_history(limit=5)
    assert cursor == ""
    assert history[0]["run_id"] == run_id
    assert history[0]["title"] == "历史测试"
    assert "state" not in history[0]
    assert "events" not in history[0]
    assert store.list_snapshots(run_id)[0]["snapshot_id"] == snapshot_id


def test_snapshot_restore_is_idempotent_and_keeps_monotonic_budget(tmp_path: Path) -> None:
    store, run_id, snapshot_id = _checkpointed_store(tmp_path)
    state = NovelRunState.model_validate(store.read(run_id)["state"])
    state.runtime_phase = "failed"
    state.errors = [{"error": "provider timeout"}]
    state.budget_state = {"run_consumed_tokens": 99}
    store.update_state(run_id, state)
    store.append_event(run_id, {"type": "run_failed", "run_id": run_id})
    revision = store.read(run_id)["state_revision"]

    first = store.restore_snapshot(run_id, snapshot_id, request_id="restore-request-1", expected_revision=revision)
    second = store.restore_snapshot(run_id, snapshot_id, request_id="restore-request-1", expected_revision=revision)
    assert second == first
    restored = store.read(run_id)["state"]
    assert restored["runtime_phase"] == "checkpoint_recovery"
    assert restored["errors"] == []
    assert restored["budget_state"]["run_consumed_tokens"] == 99
    history = store.list_history()[0][0]
    assert history["status"] == "paused"
    assert history["recovery_required"] is False
    assert history["latest_snapshot_id"] == store.latest_snapshot(run_id)["snapshot_id"]

    with pytest.raises(ValueError, match="不同的恢复参数"):
        store.restore_snapshot(run_id, snapshot_id, request_id="restore-request-1", expected_revision=0)


def test_history_routes_filter_and_restore_without_provider_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    store, run_id, snapshot_id = _checkpointed_store(tmp_path / "runtime" / "novel_workflow")
    app.state.run_store = store
    client = TestClient(app)

    response = client.get("/api/runs/history", params={"project_id": "history-project"})
    assert response.status_code == 200
    assert response.json()["items"][0]["run_id"] == run_id

    snapshots = client.get(f"/api/runs/{run_id}/snapshots")
    assert snapshots.status_code == 200
    assert snapshots.json()["latest_restorable_snapshot_id"] == snapshot_id

    restored = client.post(
        f"/api/runs/{run_id}/restore-snapshot",
        json={"snapshot_id": snapshot_id, "request_id": "api-restore-request", "expected_revision": store.read(run_id)["state_revision"]},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "restored_paused"
    assert store.read(run_id)["paused"] is True


def test_run_store_rejects_unsafe_or_duplicate_ids_and_serializes_events(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    workflow = default_workflow()
    with pytest.raises(ValueError, match="Invalid run_id"):
        store.create("../outside", workflow, {})

    store.create("concurrent-run", workflow, {"title": "并发事件"})
    with pytest.raises(FileExistsError):
        store.create("concurrent-run", workflow, {})
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(
            lambda index: store.append_event("concurrent-run", {"type": "test_event", "run_id": "concurrent-run", "index": index}),
            range(24),
        ))

    events = store.read("concurrent-run")["events"]
    assert len(events) == 24
    assert sorted(event["event_seq"] for event in events) == list(range(1, 25))


def test_failed_history_without_restorable_snapshot_stays_failed(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    workflow = default_workflow()
    run_id = "history-no-checkpoint"
    store.create(run_id, workflow, {"project_id": run_id})
    state = NovelRunState(
        run_id=run_id,
        project_id=run_id,
        workflow_id=workflow.id,
        run_has_started=True,
        runtime_phase="failed",
        errors=[{"error": "provider timeout"}],
        recovery_state={"needs_recovery": True, "last_failure": {"node_id": "info", "message": "provider timeout"}},
    )
    store.update_state(run_id, state)
    store.append_event(run_id, {"type": "run_failed", "run_id": run_id})

    summary = store.list_history()[0][0]
    assert summary["status"] == "failed"
    assert summary["recovery_required"] is False
    assert summary["latest_snapshot_id"] == ""


def test_history_rebuilds_stale_or_missing_meta_and_normalizes_times(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    workflow = default_workflow()
    run_id = "history-legacy-meta"
    store.create(run_id, workflow, {"project_id": "legacy-project", "title": "旧标题"})
    run_path = store.run_dir(run_id) / "run.json"
    data = json.loads(run_path.read_text(encoding="utf-8"))
    data["inputs"]["title"] = "run.json 权威标题"
    data["state_revision"] = int(data.get("state_revision") or 0) + 3
    data["created_at"] = "not-a-timestamp"
    data["updated_at"] = ""
    run_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    expected_mtime = datetime.fromtimestamp(run_path.stat().st_mtime, timezone.utc).isoformat()

    summary = store.list_history()[0][0]
    assert summary["title"] == "run.json 权威标题"
    assert summary["state_revision"] == data["state_revision"]
    assert summary["created_at"] == expected_mtime
    assert summary["updated_at"] == expected_mtime

    (store.run_dir(run_id) / "run_meta.json").unlink()
    data["inputs"]["title"] = "缺少 meta 时的标题"
    data["updated_at"] = None
    run_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    expected_mtime = datetime.fromtimestamp(run_path.stat().st_mtime, timezone.utc).isoformat()
    summary = store.list_history()[0][0]
    assert summary["title"] == "缺少 meta 时的标题"
    assert summary["updated_at"] == expected_mtime


def test_snapshot_restore_preserves_failure_streak(tmp_path: Path) -> None:
    store, run_id, snapshot_id = _checkpointed_store(tmp_path)
    state = NovelRunState.model_validate(store.read(run_id)["state"])
    for attempt in range(2):
        register_failure(
            state,
            node_id="outline",
            node_type="outline",
            code="provider_error",
            message=f"provider timeout {attempt + 1}",
        )
    state.runtime_phase = "failed"
    store.update_state(run_id, state)
    store.append_event(run_id, {"type": "run_failed", "run_id": run_id})

    store.restore_snapshot(
        run_id,
        snapshot_id,
        request_id="restore-streak",
        expected_revision=store.read(run_id)["state_revision"],
    )
    recovered = store.read(run_id)["state"]
    assert recovered["recovery_state"]["consecutive_failures"] == 2
