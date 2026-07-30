from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.api.bootstrap import seed_defaults
from novel_workflow.workflows.templates import default_workflow


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


def test_workflow_without_is_template_field_stays_compatible(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    legacy = default_workflow().model_dump()
    legacy["id"] = "wf-legacy-json"
    legacy.pop("is_template", None)
    client.app.state.workflow_store.write("wf-legacy-json", legacy)

    response = client.get("/api/workflows/wf-legacy-json")
    assert response.status_code == 200
    assert response.json()["is_template"] is False


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
        if node["id"] == "info":
            for field in node["input_schema"]:
                if field["key"] == "core_concept":
                    field["hint"] = ""
                    field["default"] = "旧内容污染"
    app.state.workflow_store.write(default_id, polluted)

    seed_defaults(app)

    healed = app.state.workflow_store.read(default_id)
    info = next(node for node in healed["nodes"] if node["id"] == "info")
    core_concept = next(field for field in info["input_schema"] if field["key"] == "core_concept")
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
