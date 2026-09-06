"""Retired Phase 27 HTTP execution must stay inert after Project cutover."""

from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from tests.fakes import FakeNarrativeProvider
from tests.test_phase32_project_api import project_payload


def test_retired_full_chain_api_cannot_dispatch_the_offline_provider(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    provider = FakeNarrativeProvider()
    app.state.narrative_execution.provider_factory = lambda: provider

    with TestClient(app) as client:
        project = client.post(
            "/api/projects",
            json=project_payload(key="retired-full-chain-boundary"),
        ).json()
        created = client.post(
            "/api/runs",
            json={
                "run_id": "offline-chain-run-retired",
                "project_id": project["id"],
                "workflow_id": project["workflow_id"],
                "inputs": {
                    "project_brief": {"genre": "悬疑"},
                    "length_envelope": {"word_target_soft": 4_000},
                },
                "export_preferences": {"format": "zip"},
            },
        )

        assert created.status_code == 410
        assert created.json()["detail"]["code"] == "phase27_run_creation_retired"
        assert client.post("/api/runs/offline-chain-run-retired/start").status_code == 404
        assert provider.stage_requests == []
        assert provider.proposal_requests == []
        assert provider.chapter_requests == []
        assert provider.cover_requests == []
