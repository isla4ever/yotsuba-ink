from __future__ import annotations

import json

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.storage.project_schemas import ACCENT_HUE_SEQUENCE, next_accent_hue
from novel_workflow.workflows.templates import default_workflow
from novel_workflow.workflows.workflow_ids import DEFAULT_WORKFLOW_ID
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
            "length_envelope": {"word_target_soft": 12_000},
        },
        "export_preferences": {"format": "zip"},
    }


def test_project_create_copies_phase27_workflow_in_authoritative_order(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    idea = "旧港的记忆实验留下回声，一名记者发现自己的证词也被改写。"
    response = api.post("/api/projects", json={"idea": idea})
    assert response.status_code == 200
    project = response.json()
    assert project["title"] == "待定书名"
    assert project["summary"] == idea
    workflow = api.get(f"/api/workflows/{project['workflow_id']}").json()
    assert [node["id"] for node in workflow["nodes"]] == ["brief", "spine", "cast", "volumes", "detail", "text", "cover", "export"]
    assert [node.id for node in default_workflow().nodes] == ["brief", "spine", "cast", "volumes", "detail", "text", "cover", "export"]
    brief = next(node for node in workflow["nodes"] if node["id"] == "brief")
    concept = next(field for field in brief["input_schema"] if field["key"] == "core_concept")
    assert concept["default"] == idea


def test_run_creation_requires_the_project_owned_phase27_workflow(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"idea": "测试项目工作流所有权。"}).json()
    payload = run_payload(project["id"], DEFAULT_WORKFLOW_ID)
    response = api.post("/api/runs", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "project_workflow_mismatch"


def test_run_creation_derives_scale_profile_and_persists_graph_read_model(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"idea": "测试体量投影。"}).json()
    response = api.post("/api/runs", json=run_payload(project["id"], project["workflow_id"], "run-phase27"))
    assert response.status_code == 200
    stored = api.get("/api/runs/run-phase27").json()
    assert stored["definition"]["architecture_version"] == "phase27-vnext"
    assert stored["definition"]["workflow_id"] == project["workflow_id"]
    assert len(stored["definition"]["workflow_digest"]) == 64
    assert stored["definition"]["scale_profile"]["word_target_soft"] == 12_000
    assert "chapter_target_soft" not in stored["definition"]["scale_profile"]
    assert "chapter_min_reasonable" not in stored["definition"]["scale_profile"]
    assert "chapter_max_reasonable" not in stored["definition"]["scale_profile"]
    assert stored["read_model"]["active_stage_id"] == "brief"
    assert stored["read_model"]["thread_id"] == "run-phase27"


def test_project_summary_uses_brief_stage_pointer(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"idea": "测试作品聚合。"}).json()
    api.post("/api/runs", json=run_payload(project["id"], project["workflow_id"], "run-summary"))
    summary = api.get(f"/api/projects/{project['id']}/summary").json()
    assert summary["latest_run"]["run_id"] == "run-summary"
    assert summary["current_stage"]["id"] == "brief"


def test_retired_run_definition_is_excluded_from_current_history(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"idea": "旧运行不得拖垮当前作品列表。"}).json()
    created = api.post(
        "/api/runs",
        json=run_payload(project["id"], project["workflow_id"], "run-retired-scale"),
    )
    assert created.status_code == 200

    definition_path = (
        tmp_path
        / "runtime"
        / "novel_workflow"
        / "native_runtime"
        / "runs"
        / "run-retired-scale"
        / "definition.json"
    )
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    definition["scale_profile"]["chapter_min_reasonable"] = 4
    definition["scale_profile"]["chapter_max_reasonable"] = 11
    definition_path.write_text(
        json.dumps(definition, ensure_ascii=False),
        encoding="utf-8",
    )

    history = api.get("/api/runs/history")
    projects = api.get("/api/projects")

    assert history.status_code == 200
    assert history.json()["items"] == []
    retired = api.get("/api/runs/run-retired-scale")
    assert retired.status_code == 409
    assert retired.json()["detail"]["code"] == "run_contract_retired"
    assert projects.status_code == 200
    assert projects.json()[0]["id"] == project["id"]
    assert projects.json()[0]["title"] == "待定书名"
    assert projects.json()[0]["latest_run_id"] == ""


def test_project_create_does_not_rebind_to_an_unrelated_default_service(tmp_path, monkeypatch) -> None:
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
    api.post("/api/providers/default", json={"provider_id": "reader-text", "kind": "openai-compatible"})

    project = api.post("/api/projects", json={"idea": "确认不会被任意默认服务劫持。"}).json()

    workflow = api.get(f"/api/workflows/{project['workflow_id']}").json()
    text_stages = [node for node in workflow["nodes"] if node["id"] != "export"]
    assert {node["provider_profile_id"] for node in text_stages} == {"provider-deepseek-text"}
    assert workflow["nodes"][-1]["provider_profile_id"] == ""


def test_project_create_keeps_stage_bindings_that_are_already_connected(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json={"idea": "沿用模板冻结绑定。"}).json()
    workflow = api.get(f"/api/workflows/{project['workflow_id']}").json()
    text_stages = [node for node in workflow["nodes"] if node["id"] != "export"]
    assert {node["provider_profile_id"] for node in text_stages} == {"provider-deepseek-text"}


def test_project_create_rejects_blank_idea(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    assert api.post("/api/projects", json={"idea": "   "}).status_code == 422


def test_project_order_persists_and_requires_the_complete_project_set(tmp_path, monkeypatch) -> None:
    api = client(tmp_path, monkeypatch)
    first = api.post("/api/projects", json={"idea": "第一部作品。"}).json()
    second = api.post("/api/projects", json={"idea": "第二部作品。"}).json()

    response = api.put("/api/projects/order", json={"project_ids": [first["id"], second["id"]]})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [first["id"], second["id"]]
    assert [item["id"] for item in api.get("/api/projects").json()] == [first["id"], second["id"]]

    invalid = api.put("/api/projects/order", json={"project_ids": [first["id"]]})
    assert invalid.status_code == 422


def test_accent_hue_assignment_is_deterministic() -> None:
    assert next_accent_hue([]) == ACCENT_HUE_SEQUENCE[0]
    assert next_accent_hue(list(ACCENT_HUE_SEQUENCE)) == ACCENT_HUE_SEQUENCE[0]
