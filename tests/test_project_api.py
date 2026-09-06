from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from tests.test_phase32_project_api import project_payload


def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app())


def test_legacy_project_shape_is_rejected_without_writing_either_catalog(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)

    response = api.post("/api/projects", json={"idea": "旧 ProjectCreateRequest 不再可写。"})

    assert response.status_code == 422
    assert api.get("/api/projects").json() == []
    assert api.app.state.project_store.list() == []


def test_phase32_project_metadata_requires_artifact_or_archive_actions(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    project = api.post(
        "/api/projects",
        json=project_payload(key="project-mutation-boundary"),
    ).json()

    patched = api.patch(
        f"/api/projects/{project['id']}",
        json={"title": "客户端不得直接覆盖标题"},
    )
    deleted = api.delete(f"/api/projects/{project['id']}")

    assert patched.status_code == 405
    assert patched.json()["detail"]["code"] == "phase32_project_mutation_not_supported"
    assert deleted.status_code == 405
    assert deleted.json()["detail"]["code"] == "phase32_project_delete_requires_archive"
    assert api.get(f"/api/projects/{project['id']}").json()["title"] == "待定标题"


def test_phase32_project_endpoint_does_not_materialize_a_phase27_workflow_copy(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    before = {item["id"] for item in api.app.state.workflow_store.list()}

    project = api.post(
        "/api/projects",
        json=project_payload(key="project-no-phase27-copy"),
    ).json()
    after = {item["id"] for item in api.app.state.workflow_store.list()}

    assert project["workflow_id"] == "official.short_novel"
    assert after == before
    assert not any(workflow_id.startswith("wf-proj-") for workflow_id in after)
