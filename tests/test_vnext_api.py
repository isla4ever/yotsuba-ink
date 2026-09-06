from __future__ import annotations

import json

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from tests.test_phase32_project_api import project_payload


def legacy_run_payload() -> dict[str, object]:
    return {
        "run_id": "phase27-api-retired",
        "project_id": "legacy-project",
        "workflow_id": "official-deepseek-balanced",
        "inputs": {
            "project_brief": {"genre": "悬疑"},
            "length_envelope": {"word_target_soft": 12_000},
        },
        "export_preferences": {"format": "zip"},
    }


def test_phase27_run_creation_is_retired_for_every_valid_old_request(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    api = TestClient(create_app())

    response = api.post("/api/runs", json=legacy_run_payload())

    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "phase27_run_creation_retired"
    assert not api.app.state.narrative_stores.runs.exists("phase27-api-retired")


def test_phase32_run_uses_the_authoritative_run_routes(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    api = TestClient(create_app())
    project = api.post(
        "/api/projects",
        json=project_payload(key="phase32-not-phase27-readable"),
    ).json()
    run_id = project["latest_run_id"]

    loaded = api.get(f"/api/runs/{run_id}")
    assert loaded.status_code == 200
    assert loaded.json()["definition"]["architecture_version"] == "phase32-routes-v1"
    assert api.get(f"/api/phase32/runs/{run_id}").status_code == 410


def test_obsolete_run_json_archive_contract_is_not_read(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    archive_dir = tmp_path / "runtime" / "novel_workflow" / "archive" / "old-run"
    archive_dir.mkdir(parents=True)
    (archive_dir / "run.json").write_text(
        json.dumps({"run_id": "old-run", "state": {"status": "failed"}}),
        encoding="utf-8",
    )
    api = TestClient(create_app())

    assert api.get("/api/archive/runs/old-run").status_code == 404
    assert api.get("/api/runs/old-run").status_code == 404
    assert api.post("/api/runs/old-run/start").status_code == 404
