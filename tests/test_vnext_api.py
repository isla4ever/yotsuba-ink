from __future__ import annotations

import json
import hashlib

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from tests.phase27_api import (
    configure_phase27_providers,
)


def payload(project_id: str, workflow_id: str) -> dict[str, object]:
    return {
        "run_id": "api-run-1",
        "project_id": project_id,
        "workflow_id": workflow_id,
        "inputs": {
            "project_brief": {"genre": "悬疑"},
            "length_envelope": {"word_target_soft": 12_000, "chapter_target_soft": 2},
        },
        "export_preferences": {"format": "zip"},
    }


def test_run_api_uses_phase27_definition_and_rejects_old_input_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"title": "API"}).json()
    response = client.post("/api/runs", json=payload(project["id"], project["workflow_id"]))
    assert response.status_code == 200
    stored = client.get("/api/runs/api-run-1").json()
    assert stored["definition"]["architecture_version"] == "phase27-vnext"
    assert "book_scale_plan" not in json.dumps(stored, ensure_ascii=False)
    assert stored["read_model"]["active_stage_id"] == "brief"

    old_payload = payload(project["id"], project["workflow_id"])
    old_payload["run_id"] = "api-run-old-shape"
    old_payload["scale_profile"] = {
        "chapter_target_soft": 2,
        "chapter_min_reasonable": 1,
        "chapter_max_reasonable": 4,
    }
    old_payload["provider_bindings"] = {
        stage: {"provider_profile_id": "fake", "model": "fake-model"}
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }
    old_payload["cover_asset_binding"] = {
        "provider_profile_id": "fake-image",
        "model": "fake-image",
        "candidate_count": 1,
        "size": "256x384",
        "quality": "low",
    }
    assert client.post("/api/runs", json=old_payload).status_code == 422


def test_archived_run_is_read_only_at_api_boundary(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    archive_dir = tmp_path / "runtime" / "novel_workflow" / "archive" / "old-run"
    archive_dir.mkdir(parents=True)
    (archive_dir / "run.json").write_text(json.dumps({"run_id": "old-run", "state": {"status": "failed"}}), encoding="utf-8")
    client = TestClient(create_app())
    archived = client.get("/api/archive/runs/old-run")
    assert archived.status_code == 200
    assert archived.json()["capabilities"]["execute"] is False
    assert client.get("/api/runs/old-run").status_code == 404
    assert client.post("/api/runs/old-run/start").status_code == 404


def test_regeneration_requires_explicit_direction(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    response = client.post("/api/runs/missing/decisions/d-1", json={"action": "regenerate", "domain_revision": 0, "direction": "   "})
    assert response.status_code == 422


def test_context_manifest_api_is_run_scoped_and_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"title": "API"}).json()
    response = client.post("/api/runs", json=payload(project["id"], project["workflow_id"]))
    assert response.status_code == 200
    manifest = _context_manifest()
    record = client.app.state.narrative_stores.context_manifests.write(
        "api-run-1", attempt=1, manifest=manifest
    )

    loaded = client.get(f"/api/runs/api-run-1/context-manifests/{record.manifest_id}")

    assert loaded.status_code == 200
    assert loaded.json()["manifest"]["manifest_hash"] == manifest.manifest_hash
    assert client.get(
        "/api/runs/api-run-1/context-manifests/manifest-" + "0" * 64
    ).status_code == 404
    assert client.get(
        f"/api/runs/missing/context-manifests/{record.manifest_id}"
    ).status_code == 404


def test_sse_api_reconnects_from_the_next_domain_sequence(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"title": "SSE"}).json()
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200
    events = client.app.state.narrative_stores.events
    first = events.append(
        "api-run-1",
        event_id="api-run-1:node-started",
        type="node.started",
        stage_id="brief",
        node_id="brief.generate_candidate",
        status="running",
    )
    second = events.append(
        "api-run-1",
        event_id="api-run-1:decision-required",
        type="decision.required",
        stage_id="brief",
        node_id="brief.decision_policy",
        status="awaiting_decision",
        payload={"decision_id": "decision-brief-1"},
    )

    response = client.get(f"/api/runs/api-run-1/events?after={first.sequence}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert f"id: {first.sequence}\n" not in response.text
    assert f"id: {second.sequence}\n" in response.text
    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [json.loads(line)["sequence"] for line in data_lines] == [second.sequence]


def test_sse_replay_passes_a_resolved_interrupt_before_the_current_one(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"title": "SSE replay"}).json()
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200
    events = client.app.state.narrative_stores.events
    fixtures = [
        ("historical-required", "decision.required", "brief"),
        ("historical-resolved", "decision.resolved", "brief"),
        ("brief-committed", "artifact.committed", "brief"),
        ("spine-candidate", "artifact.candidate_ready", "spine"),
        ("current-required", "decision.required", "spine"),
    ]
    for event_id, event_type, stage_id in fixtures:
        events.append(
            "api-run-1",
            event_id=f"api-run-1:{event_id}",
            type=event_type,
            stage_id=stage_id,
            node_id=f"{stage_id}.decision_policy",
            status="awaiting_decision" if event_type == "decision.required" else "",
            payload={"decision_id": event_id}
            if event_type.startswith("decision.")
            else None,
        )

    response = client.get("/api/runs/api-run-1/events?after=0")

    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    replay = [json.loads(line) for line in data_lines]
    assert [event["sequence"] for event in replay] == [1, 2, 3, 4, 5]
    assert replay[-1]["stage_id"] == "spine"
    assert replay[-1]["type"] == "decision.required"


def _context_manifest() -> ContextManifest:
    text = "chapter script"
    body = {
        "task": "chapter-1",
        "required": ["detail.chapter"],
        "optional": [],
        "forbidden": ["full_canon"],
        "snippets": [{
            "ref": "detail.chapter",
            "purpose": "chapter_script",
            "text": text,
            "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }],
        "budget": {"input_chars": len(text), "output_tokens": 100},
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["manifest_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return ContextManifest.model_validate(body)
