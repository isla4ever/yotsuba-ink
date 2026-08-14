from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.api.bootstrap import seed_defaults
from novel_workflow.workflows.templates import default_workflow


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app())


def test_get_workflow_by_id_keeps_default_route(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    default_id = default_workflow().id

    by_id = client.get(f"/api/workflows/{default_id}")
    assert by_id.status_code == 200
    assert by_id.json()["id"] == default_id
    assert by_id.json()["is_template"] is False

    by_alias = client.get("/api/workflows/default")
    assert by_alias.status_code == 200
    assert by_alias.json()["id"] == default_id

    assert client.get("/api/workflows/missing-workflow").status_code == 404


def test_workflow_without_required_phase27_fields_is_not_executable(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    legacy = default_workflow().model_dump()
    legacy["id"] = "wf-legacy-json"
    legacy.pop("is_template", None)
    client.app.state.workflow_store.write("wf-legacy-json", legacy)

    response = client.get("/api/workflows/wf-legacy-json")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "workflow_contract_retired"
    assert all(item["id"] != "wf-legacy-json" for item in client.get("/api/workflows").json())
    assert client.post("/api/workflows/wf-legacy-json/duplicate", json={}).status_code == 409
    project = client.post(
        "/api/projects",
        json={"title": "旧合同不得复制", "template_workflow_id": "wf-legacy-json"},
    )
    assert project.status_code == 422
    assert project.json()["detail"]["code"] == "workflow_contract_retired"


@pytest.mark.parametrize(
    "fixture_name",
    ("wf-proj-850f449dd8.json", "wf-proj-ad5c056eef.json"),
)
def test_real_retired_workflow_files_are_inert_production_data(
    tmp_path,
    monkeypatch,
    fixture_name,
):
    client = _client(tmp_path, monkeypatch)
    source = REPOSITORY_ROOT / "runtime" / "novel_workflow" / "workflows" / fixture_name
    legacy = json.loads(source.read_text(encoding="utf-8"))
    workflow_id = legacy["id"]
    client.app.state.workflow_store.write(workflow_id, legacy)

    assert workflow_id not in {item["id"] for item in client.get("/api/workflows").json()}
    loaded = client.get(f"/api/workflows/{workflow_id}")
    assert loaded.status_code == 409
    assert loaded.json()["detail"]["code"] == "workflow_contract_retired"
    assert client.post(f"/api/workflows/{workflow_id}/duplicate", json={}).status_code == 409

    client.app.state.project_store.store.write(
        "proj-retired",
        {
            "id": "proj-retired",
            "title": "旧工作流只读证据",
            "workflow_id": workflow_id,
        },
    )
    run = client.post(
        "/api/runs",
        json={
            "run_id": f"run-{workflow_id}",
            "project_id": "proj-retired",
            "workflow_id": workflow_id,
            "inputs": {},
            "export_preferences": {"format": "zip"},
        },
    )
    assert run.status_code == 422
    assert run.json()["detail"]["code"] == "workflow_contract_retired"
    assert client.post(f"/api/runs/run-{workflow_id}/start").status_code == 404


def test_duplicate_workflow_copies_and_marks_template(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    default_id = default_workflow().id

    auto = client.post(f"/api/workflows/{default_id}/duplicate", json={"name": "我的模板", "is_template": True})
    assert auto.status_code == 200
    copy = auto.json()
    assert copy["id"].startswith("wf-copy-")
    assert copy["name"] == "我的模板"
    assert copy["is_template"] is True
    assert len(copy["nodes"]) == len(default_workflow().nodes)
    assert any(item["id"] == copy["id"] for item in client.get("/api/workflows").json())

    explicit = client.post(f"/api/workflows/{default_id}/duplicate", json={"new_id": "wf-my-copy"})
    assert explicit.status_code == 200
    assert explicit.json()["id"] == "wf-my-copy"
    assert explicit.json()["name"] == default_workflow().name
    assert explicit.json()["is_template"] is False

    conflict = client.post(f"/api/workflows/{default_id}/duplicate", json={"new_id": "wf-my-copy"})
    assert conflict.status_code == 409
    assert client.post("/api/workflows/missing-workflow/duplicate", json={}).status_code == 404


def test_delete_workflow_protects_default_and_project_references(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    default_id = default_workflow().id

    assert client.delete(f"/api/workflows/{default_id}").status_code == 409

    project = client.post("/api/projects", json={"title": "引用中的作品"}).json()
    referenced = client.delete(f"/api/workflows/{project['workflow_id']}")
    assert referenced.status_code == 409
    assert "引用中的作品" in referenced.json()["detail"]

    copy = client.post(f"/api/workflows/{default_id}/duplicate", json={"new_id": "wf-deletable"}).json()
    assert client.delete(f"/api/workflows/{copy['id']}").status_code == 200
    assert client.get(f"/api/workflows/{copy['id']}").status_code == 404
    assert client.delete("/api/workflows/missing-workflow").status_code == 404


def test_seed_defaults_only_touches_default_workflow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    app = client.app
    default_id = default_workflow().id

    template = client.post(f"/api/workflows/{default_id}/duplicate", json={"new_id": "wf-user-template", "name": "用户模板", "is_template": True}).json()
    project = client.post("/api/projects", json={"title": "被保护的作品"}).json()

    tampered_template = {**app.state.workflow_store.read("wf-user-template"), "version": "0.0.1-user"}
    app.state.workflow_store.write("wf-user-template", tampered_template)
    tampered_project_wf = {**app.state.workflow_store.read(project["workflow_id"]), "version": "0.0.1-project"}
    app.state.workflow_store.write(project["workflow_id"], tampered_project_wf)
    stale_default = {**app.state.workflow_store.read(default_id), "version": "0.0.0-stale", "name": "被篡改的默认工作流"}
    app.state.workflow_store.write(default_id, stale_default)

    seed_defaults(app)

    reseeded = app.state.workflow_store.read(default_id)
    assert reseeded["version"] == default_workflow().version
    assert reseeded["name"] == default_workflow().name
    assert app.state.workflow_store.read("wf-user-template")["version"] == "0.0.1-user"
    assert app.state.workflow_store.read("wf-user-template")["name"] == "用户模板"
    assert app.state.workflow_store.read(project["workflow_id"])["version"] == "0.0.1-project"
    assert template["is_template"] is True


def test_seed_defaults_restores_content_tamper_even_when_version_matches(tmp_path, monkeypatch):
    """Phase 12 Wave 3A: 'new version + old content' pollution must self-heal.

    A stale backend process once rewrote the on-disk default with the current
    version string but outdated stage content; the old version-only comparison
    skipped the repair. The digest comparison must restore the template.
    """
    client = _client(tmp_path, monkeypatch)
    app = client.app
    default_id = default_workflow().id

    polluted = app.state.workflow_store.read(default_id)
    assert polluted["version"] == default_workflow().version
    for node in polluted["nodes"]:
        if node["id"] == "brief":
            for field in node["input_schema"]:
                if field["key"] == "core_concept":
                    field["hint"] = ""
                    field["default"] = "旧内容污染"
    app.state.workflow_store.write(default_id, polluted)

    seed_defaults(app)

    healed = app.state.workflow_store.read(default_id)
    brief = next(node for node in healed["nodes"] if node["id"] == "brief")
    core_concept = next(field for field in brief["input_schema"] if field["key"] == "core_concept")
    assert core_concept["default"] != "旧内容污染"
    assert core_concept["hint"]
    assert healed == default_workflow().model_dump()


def test_seed_defaults_is_idempotent_and_scoped_to_default_id(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    app = client.app
    default_id = default_workflow().id
    user_copy = client.post(f"/api/workflows/{default_id}/duplicate", json={"new_id": "wf-user-edit"}).json()
    assert user_copy["id"] == "wf-user-edit"

    writes: list[str] = []
    original_write = app.state.workflow_store.write

    def counting_write(workflow_id, payload):
        writes.append(workflow_id)
        return original_write(workflow_id, payload)

    monkeypatch.setattr(app.state.workflow_store, "write", counting_write)
    seed_defaults(app)

    # The pristine on-disk default matches the code template digest: no write.
    # User copies (identical content, different id) are never candidates.
    assert default_id not in writes
    assert "wf-user-edit" not in writes


def test_disk_runtime_workflow_matches_phase27_authority() -> None:
    workflow = default_workflow().model_dump(mode="json")
    disk = json.loads(
        (REPOSITORY_ROOT / "runtime/novel_workflow/workflows/default-novel-workflow.json").read_text()
    )
    stage_order = ["brief", "spine", "cast", "volumes", "detail", "text", "cover", "export"]
    labels = {
        "brief": "创作立项定稿",
        "spine": "故事脊柱",
        "cast": "人物圣经",
        "volumes": "分卷架构",
        "detail": "章节施工图",
        "text": "正文生成",
        "cover": "AI 封面",
        "export": "导出产物",
    }

    assert [node["id"] for node in workflow["nodes"]] == stage_order
    assert [node["id"] for node in disk["nodes"]] == stage_order
    assert {node["id"]: node["label"] for node in workflow["nodes"]} == labels
    assert {node["id"]: node["label"] for node in disk["nodes"]} == labels
    assert disk["canvas_layout"] == workflow["canvas_layout"]
    python_detail = next(item for item in workflow["prompt_templates"] if item["id"] == "prompt-detail")
    disk_detail = next(item for item in disk["prompt_templates"] if item["id"] == "prompt-detail")
    assert disk_detail["variables"] == python_detail["variables"]
    assert {"volume_spine_turns", "scale_projection"} <= set(disk_detail["variables"])
    brief_keys = [
        field["key"]
        for field in next(node for node in disk["nodes"] if node["id"] == "brief")["input_schema"]
    ]
    assert "chapter_target_soft" in brief_keys
    assert "chapter_min_reasonable" not in brief_keys
    assert "chapter_max_reasonable" not in brief_keys
