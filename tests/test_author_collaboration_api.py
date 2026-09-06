from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.providers.phase32_contract import Phase32ProviderResponse
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)
from tests.test_phase32_driver import _FixtureGateway


ROUTE_CASES = (
    (SCREENPLAY_SAMPLE_ROUTE, "cast", "story_map"),
    (SHORT_NOVEL_ROUTE, "story_map", "book_architecture"),
    (LONG_NOVEL_ROUTE, "book_architecture", "story_map"),
)


class _ApiCollaborationGateway(_FixtureGateway):
    async def generate(self, request, *, binding):
        if request.provider_task_kind != "author_collaboration":
            return await super().generate(request, binding=binding)
        self.requests.append(request)
        if request.transport_task_name.endswith(".revise"):
            return Phase32ProviderResponse(
                payload={
                    "response": "我只修改了选中的人物目标。",
                    "replacement": "在公开听证前找到可独立核验的原始签名链。",
                    "rationale": "把抽象愿望改成可观察、可验证的行动。",
                },
                usage={"input_tokens": 120, "output_tokens": 48},
            )
        if request.transport_task_name.endswith(".plan"):
            return Phase32ProviderResponse(
                payload={
                    "response": "先确认目标，再检查下游引用。",
                    "plan": {
                        "goal": "增强当前单元的可验证性",
                        "findings": ["目标仍偏抽象"],
                        "steps": ["补充公开动作", "复核下游引用"],
                        "impacts": ["当前阶段 Artifact"],
                        "risks": ["不得改变稳定 ref"],
                        "questions": [],
                    },
                },
                usage={"input_tokens": 110, "output_tokens": 42},
            )
        return Phase32ProviderResponse(
            payload={"response": "当前判断必须以本线程冻结的 Phase 32 Artifact 为准。"},
            usage={"input_tokens": 100, "output_tokens": 32},
        )


def test_collaboration_settings_are_sanitized_and_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    _configure_text_provider(
        client,
        provider_id="collaboration-provider",
        model="deepseek-chat",
        name="作者协作服务",
    )

    response = client.get("/api/collaboration/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["capabilities"]
    assert all("api_key" not in item for item in payload["capabilities"])
    ready = next(
        item
        for item in payload["capabilities"]
        if item["provider_profile_id"] == "collaboration-provider"
    )
    assert ready["ready"] is True
    settings = payload["settings"]
    settings.update(
        default_provider_profile_id=ready["provider_profile_id"],
        default_model=ready["model"],
    )
    settings["context_policy"]["author_preferences"] = "偏好克制叙述与可验证动作。"

    saved = client.put("/api/collaboration/settings", json=settings)

    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["context_policy"]["author_preferences"] == (
        "偏好克制叙述与可验证动作。"
    )
    on_disk = tmp_path / "runtime" / "novel_workflow" / "collaboration_settings" / "settings.json"
    assert on_disk.exists()
    assert "api_key" not in on_disk.read_text(encoding="utf-8")


def test_continuity_acceptance_rejects_collaboration_api_before_provider_receipts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    prepared = client.app.state.phase32_creation_service.prepare_continuity_acceptance(
        CreationPreparationRequest.model_validate(
            {
                "selection": {
                    "intent": {
                        "creative_intent": "验证连续性验收基线不能进入作者协作旁路。",
                        "creation_language": "zh-CN",
                        "creation_kind": "novel",
                        "novel_length_class": "long_novel",
                        "requested_target": 150_000,
                    },
                    "mode": "existing",
                    "workflow_id": "official.long_novel",
                },
                "idempotency_key": "continuity-acceptance-collaboration-api",
            }
        )
    )
    gateway = _ApiCollaborationGateway({})
    client.app.state.phase32_provider_gateway = gateway
    run_id = prepared.definition.run_id

    rejected = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={"stage_id": "book_architecture"},
    )

    assert rejected.status_code == 403, rejected.text
    assert rejected.json()["detail"]["code"] == "author_collaboration_unavailable"
    assert client.app.state.phase32_collaboration.list_threads(run_id) == []
    assert client.app.state.phase32_provider_inputs.list(run_id) == []
    assert client.app.state.phase32_provider_operations.list(run_id) == []
    assert gateway.requests == []


@pytest.mark.parametrize(
    ("route", "legal_stage", "foreign_stage"),
    ROUTE_CASES,
    ids=("screenplay_sample", "short_novel", "long_novel"),
)
def test_phase32_routes_expose_only_declared_collaboration_stages(
    tmp_path: Path,
    monkeypatch,
    route: CreationRouteSpec,
    legal_stage: str,
    foreign_stage: str,
) -> None:
    client, run_id, _gateway = _client_with_run(tmp_path, monkeypatch, route)
    decision = _advance_to(client, run_id, legal_stage)

    listed = client.get(f"/api/runs/{run_id}/collaboration/threads")
    assert listed.status_code == 200
    assert listed.json() == {"run_id": run_id, "threads": []}

    created = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={"stage_id": legal_stage, "label": route.label},
    )
    assert created.status_code == 201, created.text
    thread = created.json()
    assert thread["architecture_version"] == "phase32-routes-v1"
    assert thread["creation_route_id"] == route.route_id
    assert thread["route_revision"] == route.revision
    assert thread["stage_id"] == legal_stage
    assert thread["scope"]["artifact_ref"] == decision["artifact_ref"]
    assert thread["provider_execution"]["provider_profile_id"] == "phase32-fixture-provider"

    for unavailable_stage in ("brief", "cover", "export", foreign_stage):
        rejected = client.post(
            f"/api/runs/{run_id}/collaboration/threads",
            json={"stage_id": unavailable_stage},
        )
        assert rejected.status_code == 403, rejected.text
        assert rejected.json()["detail"]["code"] == "author_collaboration_unavailable"


def test_source_and_unit_mismatch_are_rejected_by_phase32_api(tmp_path, monkeypatch) -> None:
    client, run_id, _gateway = _client_with_run(tmp_path, monkeypatch, SHORT_NOVEL_ROUTE)
    decision = _advance_to(client, run_id, "story_map")

    stale = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={
            "stage_id": "story_map",
            "source_ref": f"{decision['artifact_ref']}-not-current",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "collaboration_source_stale"

    missing_unit = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={
            "stage_id": "story_map",
            "source_ref": decision["artifact_ref"],
            "unit_ref": "missing-anchor",
        },
    )
    assert missing_unit.status_code == 409
    assert missing_unit.json()["detail"]["code"] == "context_invalid"


def test_author_draft_change_makes_thread_context_stale_over_http(tmp_path, monkeypatch) -> None:
    client, run_id, _gateway = _client_with_run(tmp_path, monkeypatch, SHORT_NOVEL_ROUTE)
    decision = _advance_to(client, run_id, "cast")
    current = _current(client, run_id, "cast")
    thread = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={"stage_id": "cast", "source_ref": current["artifact_ref"]},
    ).json()

    payload = dict(current["payload"])
    characters = [dict(item) for item in payload["characters"]]
    characters[0]["desire"] = "在听证前找到可核验的原始签名链。"
    payload["characters"] = characters
    saved = client.put(
        f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
        json={
            "domain_revision": decision["domain_revision"],
            "source_artifact_ref": current["artifact_ref"],
            "payload": payload,
        },
    )
    assert saved.status_code == 200, saved.text

    stale = client.post(
        f"/api/runs/{run_id}/collaboration/threads/{thread['thread_id']}/context-preview",
        json={"client_turn_id": "stale-1", "message": "人物目标是否具体？"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "collaboration_source_stale"


def test_turn_replay_is_idempotent_and_input_drift_conflicts_over_http(
    tmp_path,
    monkeypatch,
) -> None:
    client, run_id, gateway = _client_with_run(tmp_path, monkeypatch, SCREENPLAY_SAMPLE_ROUTE)
    _advance_to(client, run_id, "cast")
    thread = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={"stage_id": "cast"},
    ).json()
    preview_url = (
        f"/api/runs/{run_id}/collaboration/threads/{thread['thread_id']}/context-preview"
    )
    turn_url = f"/api/runs/{run_id}/collaboration/threads/{thread['thread_id']}/turns"
    base = {
        "client_turn_id": "browser-turn-1",
        "mode": "discuss",
        "message": "当前人物职责是否清晰？",
    }
    preview = client.post(preview_url, json=base)
    assert preview.status_code == 200, preview.text
    command = {**base, "preview_signature": preview.json()["receipt_hash"]}

    created = client.post(turn_url, json=command)
    replay = client.post(turn_url, json=command)

    assert created.status_code == 202, created.text
    assert created.json()["status"] == "completed"
    assert replay.status_code == 202, replay.text
    assert replay.json()["turn_id"] == created.json()["turn_id"]
    collaboration_requests = [
        item for item in gateway.requests if item.provider_task_kind == "author_collaboration"
    ]
    assert len(collaboration_requests) == 1

    changed = {**base, "message": "换一个问题。"}
    changed_preview = client.post(preview_url, json=changed)
    assert changed_preview.status_code == 200
    conflict = client.post(
        turn_url,
        json={**changed, "preview_signature": changed_preview.json()["receipt_hash"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "turn_replay_conflict"


def test_revise_patch_cannot_write_directly_to_phase32_artifact(tmp_path, monkeypatch) -> None:
    client, run_id, _gateway = _client_with_run(tmp_path, monkeypatch, SHORT_NOVEL_ROUTE)
    _advance_to(client, run_id, "cast")
    current = _current(client, run_id, "cast")
    character = current["payload"]["characters"][0]
    selected_text = str(character["desire"])
    unit_ref = str(character["subject_ref"])
    field_path = "characters.0.desire"
    thread_response = client.post(
        f"/api/runs/{run_id}/collaboration/threads",
        json={
            "stage_id": "cast",
            "source_ref": current["artifact_ref"],
            "unit_ref": unit_ref,
            "field_path": field_path,
            "label": character["display_name"],
        },
    )
    assert thread_response.status_code == 201, thread_response.text
    thread = thread_response.json()
    selection = {
        "anchor_id": "selection-cast-desire",
        "stage_id": "cast",
        "source_ref": current["artifact_ref"],
        "unit_ref": unit_ref,
        "field_path": field_path,
        "field_hash": _sha256(selected_text),
        "selection_start": 0,
        "selection_end": len(selected_text),
        "selected_text_hash": _sha256(selected_text),
        "selected_char_count": len(selected_text),
        "preview": selected_text,
        "selected_text": selected_text,
        "created_at": "2026-08-25T00:00:00+08:00",
    }
    base = {
        "client_turn_id": "revise-cast-1",
        "mode": "revise",
        "message": "把目标改得具体，但不要改变人物身份。",
        "selection": selection,
    }
    preview_url = (
        f"/api/runs/{run_id}/collaboration/threads/{thread['thread_id']}/context-preview"
    )
    preview = client.post(preview_url, json=base)
    assert preview.status_code == 200, preview.text
    completed = client.post(
        f"/api/runs/{run_id}/collaboration/threads/{thread['thread_id']}/turns",
        json={**base, "preview_signature": preview.json()["receipt_hash"]},
    )
    assert completed.status_code == 202, completed.text
    patch_id = completed.json()["patch_candidate_ref"]
    assert patch_id.startswith("p32-patch-")

    unavailable = client.post(f"/api/runs/{run_id}/collaboration/patches/{patch_id}/accept")
    assert unavailable.status_code == 409
    assert unavailable.json()["detail"]["code"] == "patch_writeback_unavailable"
    assert _current(client, run_id, "cast")["payload"] == current["payload"]

    rejected = client.post(f"/api/runs/{run_id}/collaboration/patches/{patch_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert _current(client, run_id, "cast")["payload"] == current["payload"]


def _client_with_run(
    tmp_path: Path,
    monkeypatch,
    route: CreationRouteSpec,
) -> tuple[TestClient, str, _ApiCollaborationGateway]:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    phase32_root = tmp_path / "runtime" / "novel_workflow" / "phase32_runtime"
    route_slug = route.route_id.replace("_", "-")
    policy = ReviewPolicy(
        policy_id=f"review.{route.route_id}.collaboration-api",
        revision="r1",
        route_id=route.route_id,
        checkpoint_policy="every_stage",
        warning_policy="pause_at_milestone",
        directed_redraft_limit_by_stage={},
        mandatory_decision_stages=tuple(
            stage.stage_id for stage in route.stages if stage.stage_id != "export"
        ),
    )
    fixture = create_phase32_run_fixture(
        phase32_root,
        route=route,
        run_id=f"collaboration-api-{route_slug}",
        project_id=f"collaboration-project-{route_slug}",
        creative_intent="验证 Phase 32 作者协作 HTTP 合同。",
        target=150_000 if route.route_id == "long_novel" else None,
        review_policy=policy,
    )
    gateway = _ApiCollaborationGateway({})
    client.app.state.phase32_provider_gateway = gateway
    return client, fixture.definition.run_id, gateway


def _advance_to(client: TestClient, run_id: str, stage_id: str) -> dict[str, object]:
    response = client.post(f"/api/runs/{run_id}/start")
    assert response.status_code == 200, response.text
    decision = response.json()["decision"]
    while decision is not None:
        if decision["stage_id"] == stage_id:
            return decision
        response = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        )
        assert response.status_code == 200, response.text
        decision = response.json()["decision"]
    raise AssertionError(f"Run completed before reaching {stage_id}")


def _current(client: TestClient, run_id: str, stage_id: str) -> dict[str, object]:
    response = client.get(f"/api/runs/{run_id}/stages/{stage_id}/artifacts/current")
    assert response.status_code == 200, response.text
    return response.json()


def _configure_text_provider(
    client: TestClient,
    *,
    provider_id: str,
    model: str,
    name: str,
) -> None:
    response = client.post(
        "/api/providers",
        json={
            "id": provider_id,
            "name": name,
            "kind": "openai-compatible",
            "template_id": "deepseek-text",
            "base_url": "https://provider.invalid/v1",
            "api_key_env": "",
            "default_model": model,
            "model_options": [model],
            "enabled": True,
        },
    )
    assert response.status_code == 200, response.text
    secret = client.post(
        f"/api/providers/{provider_id}/secret",
        json={"api_key": f"offline-secret-{provider_id}"},
    )
    assert secret.status_code == 200, secret.text


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
