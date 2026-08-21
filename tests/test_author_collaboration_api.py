from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.storage.narrative_run_repository import ExportPreferences, ProviderBinding
from novel_workflow.workflows.hierarchical_scale import plan_hierarchical_narrative_scale
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile
from tests.phase27_api import configure_phase27_providers
from tests.phase27_bindings import cover_asset_binding, provider_binding


def test_collaboration_settings_are_sanitized_and_persisted(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)

    response = client.get("/api/collaboration/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["capabilities"]
    assert all("api_key" not in item for item in payload["capabilities"])
    ready = next(item for item in payload["capabilities"] if item["ready"])
    settings = payload["settings"]
    settings["default_provider_profile_id"] = ready["provider_profile_id"]
    settings["default_model"] = ready["model"]
    settings["context_policy"]["author_preferences"] = "偏好克制叙述与可验证动作。"

    saved = client.put("/api/collaboration/settings", json=settings)

    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["context_policy"]["author_preferences"] == "偏好克制叙述与可验证动作。"
    on_disk = tmp_path / "runtime" / "novel_workflow" / "collaboration_settings" / "settings.json"
    assert on_disk.exists()
    assert "api_key" not in on_disk.read_text(encoding="utf-8")


def test_non_deep_run_is_rejected_by_collaboration_api(tmp_path, monkeypatch) -> None:
    client = _client_with_run(tmp_path, monkeypatch, quality_mode="balanced")

    response = client.get("/api/runs/run-collab-api/collaboration/threads")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "author_collaboration_unavailable"


def test_context_signature_replay_cancel_archive_and_delete_are_explicit(tmp_path, monkeypatch) -> None:
    client = _client_with_run(tmp_path, monkeypatch, quality_mode="deep")
    execution = client.app.state.narrative_execution
    execution.dispatch_collaboration_turn = MagicMock()
    execution.is_collaboration_running = MagicMock(return_value=False)
    execution.cancel_collaboration_turn = MagicMock(return_value=False)

    thread_response = client.post(
        "/api/runs/run-collab-api/collaboration/threads",
        json={"stage_id": "spine", "unit_ref": "turn-1", "label": "转折一"},
    )
    assert thread_response.status_code == 201, thread_response.text
    thread = thread_response.json()
    assert thread["provider_binding"]["provider_profile_id"] == "fake"
    assert thread["provider_binding"]["model"] == "fake-model"
    base = {
        "client_turn_id": "browser-turn-1",
        "mode": "discuss",
        "message": "这个转折的代价够具体吗？",
    }
    preview_url = f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}/context-preview"
    turn_url = f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}/turns"
    preview = client.post(preview_url, json=base)
    assert preview.status_code == 200, preview.text

    stale = client.post(turn_url, json={**base, "preview_signature": "0" * 64})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "context_reconfirmation_required"

    created = client.post(
        turn_url,
        json={**base, "preview_signature": preview.json()["receipt_hash"]},
    )
    assert created.status_code == 202, created.text
    replay = client.post(
        turn_url,
        json={**base, "preview_signature": preview.json()["receipt_hash"]},
    )
    assert replay.status_code == 202
    assert replay.json()["turn_id"] == created.json()["turn_id"]

    changed = {**base, "message": "换一个问题。"}
    changed_preview = client.post(preview_url, json=changed).json()
    conflict = client.post(
        turn_url,
        json={**changed, "preview_signature": changed_preview["receipt_hash"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "turn_replay_conflict"

    busy_archive = client.patch(
        f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}",
        json={"status": "archived"},
    )
    assert busy_archive.status_code == 409
    assert busy_archive.json()["detail"]["code"] == "collaboration_thread_busy"
    busy_delete = client.delete(
        f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}"
    )
    assert busy_delete.status_code == 409
    assert busy_delete.json()["detail"]["code"] == "collaboration_thread_busy"

    cancelled = client.post(
        f"{turn_url}/{created.json()['turn_id']}/cancel",
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    events = client.app.state.narrative_stores.collaboration.read_events(
        "run-collab-api",
        thread["thread_id"],
        after=0,
    )
    cancel_event = next(item for item in events if item.type == "turn.cancelled")
    assert client.app.state.narrative_stores.collaboration.read_events(
        "run-collab-api",
        thread["thread_id"],
        after=cancel_event.sequence - 1,
    )[0].sequence == cancel_event.sequence

    archived = client.patch(
        f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    deleted = client.delete(
        f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}"
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert client.get("/api/runs/run-collab-api/collaboration/threads").json()["threads"] == []


def test_context_policy_change_requires_a_fresh_confirmation(tmp_path, monkeypatch) -> None:
    client = _client_with_run(tmp_path, monkeypatch, quality_mode="deep")
    execution = client.app.state.narrative_execution
    execution.dispatch_collaboration_turn = MagicMock()
    thread = client.post(
        "/api/runs/run-collab-api/collaboration/threads",
        json={"stage_id": "spine", "unit_ref": "turn-1", "label": "转折一"},
    ).json()
    settings = client.get("/api/collaboration/settings").json()["settings"]
    base = {
        "client_turn_id": "browser-policy-turn-1",
        "mode": "discuss",
        "message": "这个转折是否需要更多人物上下文？",
        "context_policy": settings["context_policy"],
    }
    preview_url = f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}/context-preview"
    turn_url = f"/api/runs/run-collab-api/collaboration/threads/{thread['thread_id']}/turns"
    preview = client.post(preview_url, json=base)
    assert preview.status_code == 200, preview.text

    changed_policy = {
        **settings["context_policy"],
        "include_canon_wiki": not settings["context_policy"]["include_canon_wiki"],
    }
    stale = client.post(
        turn_url,
        json={
            **base,
            "context_policy": changed_policy,
            "preview_signature": preview.json()["receipt_hash"],
        },
    )

    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "context_reconfirmation_required"
    assert execution.dispatch_collaboration_turn.call_count == 0


def test_saved_provider_default_is_frozen_only_into_new_threads(tmp_path, monkeypatch) -> None:
    client = _client_with_run(tmp_path, monkeypatch, quality_mode="deep")
    _configure_text_provider(
        client,
        provider_id="collaboration-provider-a",
        model="deepseek-chat",
        name="协作服务 A",
    )
    _configure_text_provider(
        client,
        provider_id="collaboration-provider-b",
        model="deepseek-reasoner",
        name="协作服务 B",
    )

    settings = client.get("/api/collaboration/settings").json()["settings"]
    settings.update(
        default_provider_profile_id="collaboration-provider-a",
        default_model="deepseek-chat",
    )
    assert client.put("/api/collaboration/settings", json=settings).status_code == 200
    first = client.post(
        "/api/runs/run-collab-api/collaboration/threads",
        json={"stage_id": "spine", "unit_ref": "turn-1", "label": "A 模型线程"},
    ).json()

    settings.update(
        default_provider_profile_id="collaboration-provider-b",
        default_model="deepseek-reasoner",
    )
    assert client.put("/api/collaboration/settings", json=settings).status_code == 200
    second = client.post(
        "/api/runs/run-collab-api/collaboration/threads",
        json={"stage_id": "spine", "unit_ref": "turn-2", "label": "B 模型线程"},
    ).json()
    first_after_change = client.get(
        f"/api/runs/run-collab-api/collaboration/threads/{first['thread_id']}"
    ).json()["thread"]

    assert first["provider_binding"]["provider_profile_id"] == "collaboration-provider-a"
    assert first["provider_binding"]["model"] == "deepseek-chat"
    assert first["provider_binding"]["prompt_template_id"] == "author-collaboration-v1"
    assert second["provider_binding"]["provider_profile_id"] == "collaboration-provider-b"
    assert second["provider_binding"]["model"] == "deepseek-reasoner"
    assert first_after_change["provider_binding"] == first["provider_binding"]


def test_saved_provider_default_rejects_new_threads_when_it_becomes_unready(
    tmp_path,
    monkeypatch,
) -> None:
    client = _client_with_run(tmp_path, monkeypatch, quality_mode="deep")
    provider_id = "collaboration-provider-stale"
    model = "deepseek-chat"
    _configure_text_provider(
        client,
        provider_id=provider_id,
        model=model,
        name="协作服务（待失效）",
    )
    settings = client.get("/api/collaboration/settings").json()["settings"]
    settings.update(
        default_provider_profile_id=provider_id,
        default_model=model,
    )
    assert client.put("/api/collaboration/settings", json=settings).status_code == 200

    existing = client.post(
        "/api/runs/run-collab-api/collaboration/threads",
        json={"stage_id": "spine", "unit_ref": "turn-1", "label": "冻结线程"},
    )
    assert existing.status_code == 201, existing.text

    removed = client.delete(f"/api/providers/{provider_id}/secret")
    assert removed.status_code == 200, removed.text
    rejected = client.post(
        "/api/runs/run-collab-api/collaboration/threads",
        json={"stage_id": "spine", "unit_ref": "turn-2", "label": "不得回退"},
    )

    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "collaboration_settings_invalid"
    assert "no longer ready" in rejected.json()["detail"]["message"]
    frozen = client.get(
        "/api/runs/run-collab-api/collaboration/threads/"
        f"{existing.json()['thread_id']}"
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["thread"]["provider_binding"]["provider_profile_id"] == provider_id
    assert frozen.json()["thread"]["provider_binding"]["model"] == model


def _client_with_run(tmp_path, monkeypatch, *, quality_mode: str) -> TestClient:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    stores = client.app.state.narrative_stores
    scale = NarrativeScaleProfile(word_target_soft=4_000)
    stores.runs.create(
        run_id="run-collab-api",
        project_id="project-1",
        workflow_id="workflow-deep",
        workflow_revision="phase31",
        workflow_digest="a" * 64,
        quality_mode=quality_mode,
        inputs={"genre": "悬疑"},
        scale_profile=scale,
        hierarchical_scale_plan=plan_hierarchical_narrative_scale(
            scale,
            quality_mode=quality_mode,
        ),
        provider_bindings=_bindings(),
        cover_asset_binding=cover_asset_binding(),
        export_preferences=ExportPreferences(format="zip"),
    )
    stores.artifacts.save_candidate(
        "run-collab-api",
        "spine",
        _spine(),
        source="phase31-api-test",
    )
    return client


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


def _bindings() -> dict[str, ProviderBinding]:
    return {
        stage: provider_binding(stage)
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }


def _spine() -> dict[str, object]:
    return {
        "turns": [
            {
                "id": "turn-1",
                "cause": "旧档案母带出现一段未登记的人声",
                "change": "主角确认有人主动删除事故证言",
                "progress_type": "information",
                "milestones": ["inciting", "commitment"],
            },
            {
                "id": "turn-2",
                "cause": "删除签名指向主角信任的修复导师",
                "change": "主角必须在保护导师和公开证据之间选择",
                "progress_type": "relationship",
                "milestones": ["midpoint_reversal", "crisis", "climax"],
            },
            {
                "id": "turn-3",
                "cause": "公开听证要求主角提交自己的违规修复记录",
                "change": "事故真相公开，主角承担职业资格被撤销的后果",
                "progress_type": "external",
                "milestones": ["aftermath"],
            },
        ],
        "ending": "主角公开母带和自己的违规记录，让事故责任得到确认。",
        "open_questions": ["导师为何在最后时刻保留母带副本？"],
        "progress_types": ["information", "relationship", "external"],
    }
