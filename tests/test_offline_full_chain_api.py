"""Offline full-chain validation driven through the HTTP API boundary.

Existing suites prove the graph runtime (direct NarrativeRuntime calls) and the
API routes (synthetic events) separately. This test closes the remaining gap:
one Run travels brief -> export through the real FastAPI routes, the execution
service, the sqlite-checkpointed graph, filesystem stores and SSE replay, with
only the Provider gateway replaced by the offline fake.
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.output_contracts.artifacts_vnext import STAGE_ORDER
from tests.fakes import FakeNarrativeProvider
from tests.phase27_api import configure_phase27_providers

RUN_ID = "offline-chain-run-1"


def _wait_for_new_pause(
    client: TestClient,
    run_id: str,
    *,
    resolved: set[str],
    timeout: float = 30.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/api/runs/{run_id}/state").json()
        if state["status"] in {"completed", "failed", "cancelled"}:
            return state
        if state["status"] == "awaiting_decision":
            pending = state.get("pending_decisions") or []
            if pending and pending[0]["decision_id"] not in resolved:
                return state
        time.sleep(0.05)
    raise AssertionError(f"Run {run_id} did not reach a new pause within {timeout}s")


def _post_decision_when_idle(
    client: TestClient,
    run_id: str,
    decision_id: str,
    command: dict[str, Any],
    *,
    timeout: float = 10.0,
):
    """The read model can show the pause a beat before the dispatch task exits,
    so a decision POST may briefly race the execution lock (409)."""
    deadline = time.monotonic() + timeout
    while True:
        response = client.post(f"/api/runs/{run_id}/decisions/{decision_id}", json=command)
        if response.status_code != 409 or time.monotonic() >= deadline:
            return response
        time.sleep(0.05)


def test_offline_full_chain_completes_through_the_api(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    provider = FakeNarrativeProvider()
    app.state.narrative_execution.provider_factory = lambda: provider

    with TestClient(app) as client:
        configure_phase27_providers(client)
        project = client.post("/api/projects", json={"title": "离线链路验证"}).json()
        created = client.post(
            "/api/runs",
            json={
                "run_id": RUN_ID,
                "project_id": project["id"],
                "workflow_id": project["workflow_id"],
                "inputs": {
                    "project_brief": {"genre": "悬疑"},
                    "length_envelope": {"word_target_soft": 12_000, "chapter_target_soft": 2},
                },
                "export_preferences": {"format": "zip"},
            },
        )
        assert created.status_code == 200, created.text
        assert client.post(f"/api/runs/{RUN_ID}/start").json()["status"] == "scheduled"

        resolved: set[str] = set()
        decision_types: list[str] = []
        state: dict[str, Any] = {}
        for _ in range(32):
            state = _wait_for_new_pause(client, RUN_ID, resolved=resolved)
            if state["status"] != "awaiting_decision":
                break
            decision = dict(state["pending_decisions"][0])
            decision_types.append(str(decision["type"]))
            command: dict[str, Any] = {
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            }
            if str(decision.get("node_id", "")).startswith("cover."):
                # Cover acceptance is a real author choice: one immutable
                # candidate asset must be selected before commit.
                candidate = client.get(
                    f"/api/runs/{RUN_ID}/artifact-records/{decision['artifact_ref']}"
                ).json()["payload"]
                assets = client.get(f"/api/runs/{RUN_ID}/cover-assets").json()["items"]
                command["artifact"] = {**candidate, "selected_asset_id": assets[0]["asset_id"]}
            response = _post_decision_when_idle(
                client, RUN_ID, str(decision["decision_id"]), command
            )
            assert response.status_code == 200, response.text
            resolved.add(str(decision["decision_id"]))

        assert state["status"] == "completed", state.get("failure")
        # Balanced mode pauses once per stage artifact and once per chapter.
        assert decision_types.count("chapter_author_decision") == 2
        assert set(decision_types) == {"stage_artifact_decision", "chapter_author_decision"}

        # Provider calls stay exactly-once across separate API resume dispatches.
        assert [request.stage_id for request in provider.stage_requests] == [
            "brief", "spine", "cast", "volumes", "detail", "cover",
        ]
        assert [request.chapter_id for request in provider.chapter_requests] == [
            "chapter-1", "chapter-2",
        ]

        # Chapter prose is owned by the ChapterStore, not the ArtifactStore.
        for stage_id in STAGE_ORDER:
            record = client.get(f"/api/runs/{RUN_ID}/artifacts/{stage_id}")
            if stage_id == "text":
                assert record.status_code == 404
                continue
            assert record.status_code == 200, f"{stage_id}: {record.text}"
            assert record.json()["status"] == "committed", stage_id

        chapters = client.get(f"/api/runs/{RUN_ID}/chapters").json()["chapters"]
        accepted = [item for item in chapters if item["artifact"]["author_status"] == "accepted"]
        assert [item["artifact"]["chapter_id"] for item in accepted] == ["chapter-1", "chapter-2"]

        # The default workflow freezes three independent cover candidates.
        assets = client.get(f"/api/runs/{RUN_ID}/cover-assets").json()["items"]
        assert len(assets) == 3
        assert [request.candidate_index for request in provider.cover_requests] == [1, 2, 3]
        selected_asset_id = client.get(f"/api/runs/{RUN_ID}/artifacts/cover").json()["payload"]["selected_asset_id"]
        assert selected_asset_id in {item["asset_id"] for item in assets}
        asset_body = client.get(assets[0]["content_url"])
        assert asset_body.status_code == 200
        assert asset_body.content.startswith(b"\x89PNG")

        exports = client.get(f"/api/runs/{RUN_ID}/exports").json()["items"]
        assert len(exports) == 1
        download = client.get(f"/api/runs/{RUN_ID}/exports/{exports[0]['export_id']}")
        assert download.status_code == 200
        assert download.content.startswith(b"PK")
        assert download.headers["X-Export-Sha256"] == exports[0]["sha256"]

        replay = client.get(f"/api/runs/{RUN_ID}/events?after=0")
        events = [
            json.loads(line.removeprefix("data: "))
            for line in replay.text.splitlines()
            if line.startswith("data: ")
        ]
        sequences = [event["sequence"] for event in events]
        assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
        committed_stages = {
            event["stage_id"] for event in events if event["type"] == "artifact.committed"
        }
        assert committed_stages.issuperset(set(STAGE_ORDER) - {"text"})
        # The final checkpoint persists after run.completed is announced.
        types = [event["type"] for event in events]
        assert "run.completed" in types
        assert all(item == "checkpoint.saved" for item in types[types.index("run.completed") + 1 :])

        history = client.get("/api/runs/history").json()["items"]
        assert any(item["run_id"] == RUN_ID and item["status"] == "completed" for item in history)
