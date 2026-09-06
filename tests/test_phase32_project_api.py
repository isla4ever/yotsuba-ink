from __future__ import annotations

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32RunExecutionService,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.atomic_json import atomic_write_json, read_json
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from tests.test_phase32_driver import _FixtureGateway


def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app())


def project_payload(
    *,
    key: str,
    idea: str = "一名夜班急救调度员接到来自未来的报警电话，并发现每次干预都在改写家人的旧案。",
) -> dict[str, object]:
    return {
        "idempotency_key": key,
        "selection": {
            "intent": {
                "creative_intent": idea,
                "creation_language": "zh-CN",
                "creation_kind": "novel",
                "novel_length_class": "short_novel",
                "requested_target": 20_000,
            },
            "mode": "existing",
            "workflow_id": "official.short_novel",
        },
    }


def screenplay_project_payload(*, key: str) -> dict[str, object]:
    return {
        "idempotency_key": key,
        "selection": {
            "intent": {
                "creative_intent": "一名档案记者必须在公开听证前证明签名页被替换。",
                "creation_language": "zh-CN",
                "creation_kind": "screenplay",
                "novel_length_class": None,
                "requested_target": 12,
            },
            "mode": "existing",
            "workflow_id": "official.screenplay_sample",
        },
    }


def test_project_create_registers_one_native_phase32_run_and_projection(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)

    response = api.post("/api/projects", json=project_payload(key="project-create-1"))

    assert response.status_code == 200
    project = response.json()
    assert project["architecture_version"] == "phase32-routes-v1"
    assert project["title"] == "待定标题"
    assert project["creation_route_id"] == "short_novel"
    assert project["active_stage"] == {
        "stage_id": "brief",
        "label": "小说立项",
        "ordinal": 0,
        "total": 7,
    }
    assert project["target"] == 20_000
    assert project["target_unit"] == "characters"
    assert [stage["stage_id"] for stage in project["stage_manifest"]] == [
        "brief",
        "story_map",
        "cast",
        "section_plan",
        "text",
        "cover",
        "export",
    ]

    run = api.get(f"/api/runs/{project['latest_run_id']}")
    assert run.status_code == 200
    assert run.json()["read_model"]["project_id"] == project["id"]
    listed = api.get("/api/runs").json()
    assert [item["run_id"] for item in listed["items"]] == [project["latest_run_id"]]
    assert api.get("/api/projects").json() == [project]
    assert api.get(f"/api/projects/{project['id']}").json() == project


def test_project_create_rejects_retired_official_workflow_identity(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    payload = project_payload(key="project-reject-retired-workflow")
    payload["selection"]["workflow_id"] = "official-deepseek-balanced"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "phase32_workflow_unavailable",
        "message": "Selected workflow is unavailable or missing",
    }
    assert api.get("/api/projects").json() == []


def test_project_create_rejects_an_unreleased_custom_workflow_identity(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    payload = project_payload(key="project-reject-custom-workflow")
    payload["selection"]["workflow_id"] = "custom.short-investigation"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "phase32_workflow_unavailable",
        "message": "Selected workflow is unavailable or missing",
    }
    assert api.get("/api/projects").json() == []


def test_project_title_switches_from_pending_to_committed_brief(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    gateway = _FixtureGateway({})
    phase32_root = tmp_path / "runtime" / "novel_workflow" / "phase32_runtime"
    api.app.state.phase32_execution_service = Phase32RunExecutionService(
        api.app.state.phase32_run_repository,
        checkpoint_root=phase32_root / "checkpoints",
        decisions=api.app.state.phase32_decisions,
        artifact_editing=api.app.state.phase32_artifact_editing,
        driver_factory=lambda _definition: Phase32RouteDriver(
            api.app.state.phase32_artifact_store,
            gateway,
            provider_operations=api.app.state.phase32_provider_operations,
            provider_inputs=api.app.state.phase32_provider_inputs,
            exports=api.app.state.phase32_exports,
        ),
    )
    project = api.post(
        "/api/projects",
        json=screenplay_project_payload(key="project-title-from-brief"),
    ).json()
    assert project["title"] == "待定标题"

    started = api.post(f"/api/runs/{project['latest_run_id']}/start").json()
    decision = started["decision"]
    assert decision["stage_id"] == "brief"
    accepted = api.post(
        f"/api/runs/{project['latest_run_id']}/decisions",
        json={
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
        },
    )
    assert accepted.status_code == 200
    assert api.get(f"/api/projects/{project['id']}").json()["title"] == "失序档案"


def test_project_list_survives_a_quarantined_historical_brief(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    gateway = _FixtureGateway({})
    phase32_root = tmp_path / "runtime" / "novel_workflow" / "phase32_runtime"
    api.app.state.phase32_execution_service = Phase32RunExecutionService(
        api.app.state.phase32_run_repository,
        checkpoint_root=phase32_root / "checkpoints",
        decisions=api.app.state.phase32_decisions,
        artifact_editing=api.app.state.phase32_artifact_editing,
        driver_factory=lambda _definition: Phase32RouteDriver(
            api.app.state.phase32_artifact_store,
            gateway,
            provider_operations=api.app.state.phase32_provider_operations,
            provider_inputs=api.app.state.phase32_provider_inputs,
            exports=api.app.state.phase32_exports,
        ),
    )
    project = api.post(
        "/api/projects",
        json=screenplay_project_payload(key="project-quarantined-brief"),
    ).json()
    started = api.post(f"/api/runs/{project['latest_run_id']}/start").json()
    accepted = api.post(
        f"/api/runs/{project['latest_run_id']}/decisions",
        json={
            "decision_id": started["decision"]["decision_id"],
            "action": "accept",
            "domain_revision": started["decision"]["domain_revision"],
        },
    ).json()
    artifact_ref = accepted["run"]["read_model"]["artifact_refs"]["brief"][
        "artifact_ref"
    ]
    artifact_path = (
        phase32_root / "artifacts" / project["latest_run_id"] / f"{artifact_ref}.json"
    )
    artifact_record = read_json(artifact_path)
    artifact_record["payload"].pop("title")
    artifact_record["payload_digest"] = canonical_digest(artifact_record["payload"])
    atomic_write_json(artifact_path, artifact_record)

    listed = api.get("/api/projects")

    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "待定标题"


def test_project_create_is_idempotent_and_rejects_conflicting_reuse(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    payload = project_payload(key="project-idempotent")

    first = api.post("/api/projects", json=payload)
    second = api.post("/api/projects", json=payload)
    conflict = api.post(
        "/api/projects",
        json=project_payload(key="project-idempotent", idea="另一部完全不同的作品意图。"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "phase32_creation_conflict"
    assert len(api.get("/api/projects").json()) == 1


def test_project_order_uses_only_registered_phase32_projects(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)
    first = api.post("/api/projects", json=project_payload(key="project-order-a")).json()
    second = api.post("/api/projects", json=project_payload(key="project-order-b")).json()

    ordered = api.put(
        "/api/projects/order",
        json={"project_ids": [first["id"], second["id"]]},
    )

    assert ordered.status_code == 200
    assert [item["id"] for item in ordered.json()] == [first["id"], second["id"]]
    assert [item["id"] for item in api.get("/api/projects").json()] == [
        first["id"],
        second["id"],
    ]
    assert api.put(
        "/api/projects/order",
        json={"project_ids": [first["id"]]},
    ).status_code == 422


def test_retired_project_and_run_writers_are_explicitly_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    api = client(tmp_path, monkeypatch)

    old_project = api.post("/api/projects", json={"idea": "旧项目写入口。"})
    old_prepare = api.post(
        "/api/creation-wizard/prepare",
        json=project_payload(key="retired-prepare"),
    )
    old_run = api.post(
        "/api/runs",
        json={
            "run_id": "phase27-retired",
            "project_id": "legacy-project",
            "workflow_id": "official.short_novel",
            "inputs": {},
            "export_preferences": {
                "format": "zip",
                "author": "",
                "version_note": "",
                "include_cover_image": False,
            },
        },
    )

    assert old_project.status_code == 422
    assert old_prepare.status_code == 410
    assert old_prepare.json()["detail"]["code"] == "phase32_project_creation_required"
    assert old_run.status_code == 410
    assert old_run.json()["detail"]["code"] == "phase27_run_creation_retired"
    assert api.get("/api/phase32/runs").status_code == 410
    assert api.get("/api/phase32/runs/retired").status_code == 410
    assert api.get("/api/projects").json() == []
