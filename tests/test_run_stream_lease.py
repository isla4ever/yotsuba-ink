from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.templates import default_workflow


def test_run_stream_lease_is_exclusive_across_store_instances(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    first = RunStore(root)
    second = RunStore(root)
    run_id = "stream-lease-run"
    first.create(run_id, default_workflow(), {})

    assert first.claim_stream(run_id, "lease-a") is True
    assert second.claim_stream(run_id, "lease-b") is False
    assert first.release_stream(run_id, "lease-b") is False
    assert first.release_stream(run_id, "lease-a") is True
    assert second.claim_stream(run_id, "lease-b") is True
    assert second.release_stream(run_id, "lease-b") is True


def test_events_route_rejects_a_second_active_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import novel_workflow.api.routes.runs as run_routes

    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "duplicate-stream-run"
    app.state.run_store.create(run_id, default_workflow(), {})
    assert app.state.run_store.claim_stream(run_id, "existing-lease") is True
    monkeypatch.setattr(run_routes, "_ensure_live_execution", lambda inputs: None)
    monkeypatch.setattr(run_routes, "_ensure_provider_readiness", lambda request, workflow: None)
    monkeypatch.setattr(run_routes, "rag_blocking_issue", lambda app, inputs: "")
    monkeypatch.setattr(run_routes, "enrich_reference_summary", lambda app, inputs: None)

    response = TestClient(app).post(f"/api/runs/{run_id}/events")

    assert response.status_code == 409
    assert "已有执行流" in response.json()["detail"]
    assert app.state.run_store.release_stream(run_id, "existing-lease") is True
