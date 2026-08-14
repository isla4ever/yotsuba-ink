from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.storage.project_schemas import ACCENT_HUE_SEQUENCE, next_accent_hue
from novel_workflow.workflows.templates import default_workflow
from tests.phase27_api import (
    configure_phase27_providers,
)


def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    api = TestClient(create_app())
    configure_phase27_providers(api)
    return api


def run_payload(project_id: str, workflow_id: str, run_id: str = "run-1") -> dict[str, object]:
    return {
        "run_id": run_id,
        "project_id": project_id,
        "workflow_id": workflow_id,
        "inputs": {
            "project_brief": {"genre": "悬疑"},
            "length_envelope": {"word_target_soft": 12_000, "chapter_target_soft": 2},
        },
        "export_preferences": {"format": "zip"},
    }


def test_project_create_copies_phase27_workflow_in_authoritative_order(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    response = api.post("/api/projects", json={"title": "雾港旧声"})
    assert response.status_code == 200
    project = response.json()
    workflow = api.get(f"/api/workflows/{project['workflow_id']}").json()
    assert [node["id"] for node in workflow["nodes"]] == ["brief", "spine", "cast", "volumes", "detail", "text", "cover", "export"]
    assert [node.id for node in default_workflow().nodes] == ["brief", "spine", "cast", "volumes", "detail", "text", "cover", "export"]


def test_run_creation_requires_the_project_owned_phase27_workflow(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"title": "显式绑定"}).json()
    payload = run_payload(project["id"], "default-novel-workflow")
    response = api.post("/api/runs", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "project_workflow_mismatch"


def test_run_creation_derives_scale_profile_and_persists_graph_read_model(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"title": "新作"}).json()
    response = api.post("/api/runs", json=run_payload(project["id"], project["workflow_id"], "run-phase27"))
    assert response.status_code == 200
    stored = api.get("/api/runs/run-phase27").json()
    assert stored["definition"]["architecture_version"] == "phase27-vnext"
    assert stored["definition"]["workflow_id"] == project["workflow_id"]
    assert len(stored["definition"]["workflow_digest"]) == 64
    assert stored["definition"]["scale_profile"]["chapter_target_soft"] == 2
    assert stored["definition"]["scale_profile"]["chapter_min_reasonable"] == 1
    assert stored["definition"]["scale_profile"]["chapter_max_reasonable"] == 3
    assert stored["read_model"]["active_stage_id"] == "brief"
    assert stored["read_model"]["thread_id"] == "run-phase27"


def test_project_summary_uses_brief_stage_pointer(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"title": "聚合作品"}).json()
    api.post("/api/runs", json=run_payload(project["id"], project["workflow_id"], "run-summary"))
    summary = api.get(f"/api/projects/{project['id']}/summary").json()
    assert summary["latest_run"]["run_id"] == "run-summary"
    assert summary["current_stage"]["id"] == "brief"


def test_project_create_binds_stages_to_the_connected_service(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    api = TestClient(create_app())
    api.post("/api/providers", json={
        "id": "reader-text",
        "name": "读者自己连的文本服务",
        "kind": "openai-compatible",
        "template_id": "deepseek-text",
        "base_url": "https://provider.invalid/v1",
        "api_key_env": "READER_TEXT_API_KEY",
        "default_model": "deepseek-v4-pro",
        "model_options": ["deepseek-v4-pro"],
        "enabled": True,
    })
    api.post("/api/providers/reader-text/secret", json={"api_key": "offline-test-secret"})
    api.post("/api/providers/reader-text/default", json={"kind": "openai-compatible"})

    project = api.post("/api/projects", json={"title": "新书"}).json()

    workflow = api.get(f"/api/workflows/{project['workflow_id']}").json()
    assert {node["provider_profile_id"] for node in workflow["nodes"]} == {"reader-text"}
    assert {node["model_settings"]["model"] for node in workflow["nodes"]} == {"deepseek-v4-pro"}


def test_project_create_keeps_stage_bindings_that_are_already_connected(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"title": "沿用绑定"}).json()
    workflow = api.get(f"/api/workflows/{project['workflow_id']}").json()
    text_stages = [node for node in workflow["nodes"] if node["id"] != "export"]
    assert {node["provider_profile_id"] for node in text_stages} == {"phase27-deepseek"}


def test_accent_hue_assignment_is_deterministic() -> None:
    assert next_accent_hue([]) == ACCENT_HUE_SEQUENCE[0]
    assert next_accent_hue(list(ACCENT_HUE_SEQUENCE)) == ACCENT_HUE_SEQUENCE[0]
