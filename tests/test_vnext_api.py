from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.runtime.graph.execution_service import RunExecutionConflict
from novel_workflow.runtime.graph.provider_gateway import StageGenerationRequest
from novel_workflow.runtime.graph.runtime import filesystem_stores, open_sqlite_runtime
from novel_workflow.storage.narrative_run_repository import (
    CoverAssetBinding,
    ExportPreferences,
    ProviderBinding,
    RunReadModel,
)
from novel_workflow.workflows.book_scale_plan import build_book_scale_plan
from tests.fakes import fake_png_bytes


def _bindings() -> dict[str, dict[str, str]]:
    return {
        stage: {"provider_profile_id": "fake", "model": "fake-model"}
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }


def _run_contract_payload() -> dict[str, Any]:
    return {
        "cover_asset_binding": {
            "provider_profile_id": "fake-image",
            "model": "fake-image-model",
            "candidate_count": 3,
            "size": "256x384",
            "quality": "medium",
            "failure_policy": "fail_run",
        },
        "export_preferences": {"format": "zip", "author": "", "version_note": ""},
    }


def _book_plan(chapter_count: int) -> dict[str, Any]:
    return build_book_scale_plan(
        target_mode="total_chapters",
        target_value=chapter_count,
    ).model_dump(mode="json")


def _run_contract_args() -> dict[str, Any]:
    return {
        "cover_asset_binding": CoverAssetBinding.model_validate(
            _run_contract_payload()["cover_asset_binding"]
        ),
        "export_preferences": ExportPreferences.model_validate(
            _run_contract_payload()["export_preferences"]
        ),
    }


class _BranchCheckpointProvider:
    async def generate_stage(self, request: StageGenerationRequest) -> dict[str, Any]:
        if request.stage_id != "info":
            raise AssertionError("Branch checkpoint fixture must stop at the Info decision")
        return {
            "title": "雾港母带",
            "premise": "声音档案员追查一卷会改写公共记忆的母带。",
            "story_promise": {"genre": "悬疑", "audience": "成人", "tone": "克制"},
            "world_rules": ["公开广播会覆盖个人记忆"],
            "thematic_question": "共同记忆是否值得以个人真相为代价？",
            "ending_promise": "真相会被公开。",
            "voice": {
                "viewpoint": "第三人称限知",
                "tense": "过去时",
                "texture": "听觉细节",
                "avoid": [],
            },
            "cast_requirements": [],
        }


async def _seed_branch_checkpoints(root) -> tuple[str, str]:
    stores = filesystem_stores(root)
    bindings = {
        stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
        for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
    }
    stores.runs.create(
        run_id="api-branch-source",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings=bindings,
        **_run_contract_args(),
    )
    async with open_sqlite_runtime(root, _BranchCheckpointProvider()) as runtime:
        interrupted = await runtime.start("api-branch-source")
        history = [
            snapshot
            async for snapshot in runtime.graph.aget_state_history(
                {"configurable": {"thread_id": "api-branch-source"}}
            )
        ]
    non_interrupt = next(
        snapshot
        for snapshot in history
        if snapshot.values and not snapshot.interrupts
    )
    return (
        interrupted.checkpoint_id,
        str(non_interrupt.config["configurable"]["checkpoint_id"]),
    )


def _branch_client(tmp_path, monkeypatch) -> tuple[TestClient, str, str]:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "runtime" / "novel_workflow" / "native_runtime"
    interrupt_id, non_interrupt_id = asyncio.run(_seed_branch_checkpoints(root))
    return TestClient(create_app()), interrupt_id, non_interrupt_id


def test_vnext_run_api_uses_graph_read_model_and_never_legacy_inputs(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-1",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"genre": "悬疑"},
            "book_scale_plan": _book_plan(2),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert response.status_code == 200
    payload = client.get("/api/runs/api-run-1").json()
    assert payload["read_model"]["thread_id"] == "api-run-1"
    assert payload["read_model"]["status"] == "created"
    assert payload["definition"]["architecture_version"] == "phase26-vnext"
    assert "runtime_engine" not in json.dumps(payload, ensure_ascii=False)
    assert "legacy" not in json.dumps(payload, ensure_ascii=False).lower()


def test_vnext_run_api_rejects_an_incomplete_book_scale_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-incomplete-scale",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"genre": "悬疑"},
            "book_scale_plan": {"total_chapters": 2},
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )

    assert response.status_code == 422
    assert "book_scale_plan" in response.text


def test_archived_run_is_read_only_at_api_boundary(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    archive_dir = tmp_path / "runtime" / "novel_workflow" / "archive" / "old-run"
    archive_dir.mkdir(parents=True)
    (archive_dir / "run.json").write_text(
        json.dumps({"run_id": "old-run", "state": {"runtime_phase": "failed"}}),
        encoding="utf-8",
    )
    client = TestClient(create_app())

    response = client.get("/api/archive/runs/old-run")
    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "execute": False,
        "resume": False,
        "decide": False,
        "branch": False,
        "stream": False,
        "writeback": False,
        "provider": False,
    }
    assert client.get("/api/runs/old-run").status_code == 404
    assert client.post("/api/runs/old-run/start").status_code == 404
    assert client.get("/api/runs/old-run/events").status_code == 404
    assert client.get("/api/runs/old-run/state").status_code == 404
    assert client.post(
        "/api/runs/old-run/decisions/decision-1",
        json={"action": "accept", "domain_revision": 0},
    ).status_code == 404
    assert client.post(
        "/api/runs/old-run/branches",
        json={"target_run_id": "branch-from-archive", "checkpoint_id": "checkpoint-1"},
    ).status_code == 404
    assert client.get("/api/runs/old-run/artifacts/info").status_code == 404
    assert client.post("/api/archive/runs/old-run/start").status_code == 404


def test_regeneration_decision_requires_a_non_empty_direction(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/runs/missing-run/decisions/decision-1",
        json={"action": "regenerate", "domain_revision": 0, "direction": "   "},
    )

    assert response.status_code == 422
    assert "explicit direction" in response.text


def test_decision_endpoint_is_idempotent_and_rejects_conflicting_replays(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    stores = app.state.narrative_stores
    stores.runs.create(
        run_id="api-decision-replay",
        project_id="project-1",
        workflow_revision="phase26-vnext",
        quality_mode="balanced",
        inputs={"genre": "悬疑"},
        book_scale_plan=_book_plan(1),
        provider_bindings={
            stage: ProviderBinding(provider_profile_id="fake", model="fake-model")
            for stage in ("info", "characters", "summary", "outline", "detail", "text", "cover")
        },
        **_run_contract_args(),
    )
    decision_id = "api-decision-replay:info:info-candidate-1"
    stores.runs.project(
        "api-decision-replay",
        RunReadModel(
            run_id="api-decision-replay",
            project_id="project-1",
            thread_id="api-decision-replay",
            status="awaiting_decision",
            active_stage_id="info",
            stage_status={
                "info": "awaiting_decision",
                "characters": "locked",
                "summary": "locked",
                "outline": "locked",
                "detail": "locked",
                "text": "locked",
                "cover": "locked",
                "export": "locked",
            },
            pending_decisions=[
                {
                    "type": "stage_artifact_decision",
                    "decision_id": decision_id,
                    "node_id": "info.human_decision",
                    "domain_revision": 0,
                    "allowed_actions": ["accept", "regenerate", "cancel"],
                }
            ],
            updated_at="ignored",
        ),
    )

    class OneActiveExecution:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def dispatch_resume(self, run_id: str, decision: dict[str, Any]) -> None:
            if self.calls:
                raise RunExecutionConflict(run_id)
            self.calls.append(decision)

    execution = OneActiveExecution()
    app.state.narrative_execution = execution
    client = TestClient(app)
    request_payload = {"action": "accept", "domain_revision": 0}

    first = client.post(
        f"/api/runs/api-decision-replay/decisions/{decision_id}",
        json=request_payload,
    )
    duplicate = client.post(
        f"/api/runs/api-decision-replay/decisions/{decision_id}",
        json=request_payload,
    )
    conflict = client.post(
        f"/api/runs/api-decision-replay/decisions/{decision_id}",
        json={"action": "cancel", "domain_revision": 0},
    )

    assert first.status_code == 200, first.text
    assert duplicate.status_code == 200
    assert first.json()["status"] == duplicate.json()["status"] == "scheduled"
    assert len(execution.calls) == 1
    assert conflict.status_code == 409
    assert "different command data" in conflict.json()["detail"]
    assert stores.runs.read("api-decision-replay").status == "awaiting_decision"
    assert not any(event.type == "run.failed" for event in stores.events.read("api-decision-replay"))


def test_candidate_artifact_is_read_by_immutable_event_reference(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)
    create = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-candidate",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"genre": "悬疑"},
            "book_scale_plan": _book_plan(1),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert create.status_code == 200
    candidate = app.state.narrative_stores.artifacts.save_candidate(
        "api-run-candidate",
        "info",
        {
            "title": "雾港旧声",
            "premise": "修复师追查一盒会改写共同记忆的母带。",
            "story_promise": {"genre": "悬疑", "audience": "成年读者", "tone": "冷峻克制"},
            "world_rules": ["记忆只能被复制，不能凭空制造"],
            "thematic_question": "共同记忆是否比个人记忆更可靠？",
            "ending_promise": "真相公开，但失去的记忆无法完全恢复。",
            "voice": {"viewpoint": "第三人称有限", "tense": "过去时", "texture": "现场细节驱动", "avoid": []},
            "cast_requirements": [],
        },
        source="fake:test",
    )

    response = client.get(
        f"/api/runs/api-run-candidate/artifact-records/{candidate.artifact_id}"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "candidate"
    assert response.json()["payload"]["title"] == "雾港旧声"
    assert client.get(
        f"/api/runs/another-run/artifact-records/{candidate.artifact_id}"
    ).status_code == 404


def test_chapter_event_payload_reference_resolves_to_immutable_version(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)
    create = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-chapter",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"genre": "悬疑"},
            "book_scale_plan": _book_plan(1),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert create.status_code == 200
    chapter = app.state.narrative_stores.chapters.write(
        "api-run-chapter",
        {
            "chapter_id": "chapter-1",
            "version_id": "chapter-1-v1",
            "title": "第一章",
            "content": "港口广播在午夜改写了值班表。",
            "author_status": "candidate",
        },
    )
    event = app.state.narrative_stores.events.append(
        "api-run-chapter",
        event_id="api-run-chapter:chapter-1:candidate",
        type="artifact.candidate_ready",
        stage_id="text",
        chapter_id="chapter-1",
        payload_ref=chapter.version_id,
    )

    response = client.get(
        f"/api/runs/api-run-chapter/chapters/chapter-1/versions/{event.payload_ref}"
    )

    assert response.status_code == 200
    assert response.json()["signature"] == chapter.signature
    assert response.json()["artifact"]["content"] == "港口广播在午夜改写了值班表。"


def test_export_api_lists_and_downloads_the_vnext_delivery(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)
    create = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-export",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"title": "雾港母带"},
            "book_scale_plan": _book_plan(1),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert create.status_code == 200
    stores = app.state.narrative_stores
    chapter = stores.chapters.write(
        "api-run-export",
        {
            "chapter_id": "chapter-1",
            "version_id": "chapter-1-v1-accepted",
            "title": "第一章",
            "content": "港口广播在午夜改写了值班表。",
            "author_status": "accepted",
        },
    )
    artifact = stores.artifacts.commit(
        "api-run-export",
        "export",
        {
            "format": "md",
            "chapter_version_ids": [chapter.version_id],
            "cover_asset_id": "",
            "metadata": {"title": "雾港母带", "author": "四叶", "version_note": "终稿"},
        },
        source="decision:test-export",
    )
    record = stores.exports.materialize(
        "api-run-export",
        artifact,
        [chapter.artifact],
        cover_asset=None,
    )

    listed = client.get("/api/runs/api-run-export/exports")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["export_id"] == record.export_id
    assert listed.json()["capabilities"] == {"download": True}

    downloaded = client.get(f"/api/runs/api-run-export/exports/{record.export_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["x-export-sha256"] == record.sha256
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]
    assert downloaded.content.decode("utf-8").startswith("# 雾港母带")


def test_cover_asset_api_lists_only_the_latest_attempt_and_serves_verified_bytes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)
    create = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-cover-assets",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"title": "雾港母带"},
            "book_scale_plan": _book_plan(1),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert create.status_code == 200
    stores = app.state.narrative_stores
    stores.cover_assets.save(
        "api-run-cover-assets",
        operation_key="api-run-cover-assets:cover:image:1:candidate:1",
        candidate_index=1,
        generation_attempt=1,
        image=GeneratedImage(content=fake_png_bytes(256, 384), mime_type="image/png"),
        expected_ratio=2 / 3,
    )
    latest = stores.cover_assets.save(
        "api-run-cover-assets",
        operation_key="api-run-cover-assets:cover:image:2:candidate:1",
        candidate_index=1,
        generation_attempt=2,
        image=GeneratedImage(content=fake_png_bytes(258, 387), mime_type="image/png"),
        expected_ratio=2 / 3,
    )

    listed = client.get("/api/runs/api-run-cover-assets/cover-assets")
    assert listed.status_code == 200
    assert listed.json()["generation_attempt"] == 2
    assert [item["asset_id"] for item in listed.json()["items"]] == [latest.asset_id]
    content = client.get(
        f"/api/runs/api-run-cover-assets/cover-assets/{latest.asset_id}"
    )
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.content == fake_png_bytes(258, 387)


def test_cover_decision_rejects_a_brief_changed_after_assets_were_generated(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/runs",
        json={
            "run_id": "api-run-cover-binding",
            "project_id": "project-1",
            "quality_mode": "balanced",
            "inputs": {"title": "雾港母带"},
            "book_scale_plan": _book_plan(1),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert response.status_code == 200
    stores = app.state.narrative_stores
    source = stores.artifacts.save_candidate(
        "api-run-cover-binding",
        "cover",
        {
            "brief": {
                "concept": "雾港里的记忆缺口",
                "image_prompt": "旧广播塔、雾与人物剪影",
                "palette": ["#111827", "#d4c8b8"],
                "negative_constraints": ["不渲染文字"],
            },
            "selected_asset_id": "",
        },
        source="fake:test",
    )
    asset = stores.cover_assets.save(
        "api-run-cover-binding",
        operation_key="api-run-cover-binding:cover:image:1:candidate:1",
        candidate_index=1,
        generation_attempt=1,
        image=GeneratedImage(content=fake_png_bytes(256, 384), mime_type="image/png"),
        expected_ratio=2 / 3,
    )
    decision_id = "api-run-cover-binding:cover:decision"
    stores.runs.project(
        "api-run-cover-binding",
        RunReadModel(
            run_id="api-run-cover-binding",
            project_id="project-1",
            thread_id="api-run-cover-binding",
            status="awaiting_decision",
            active_stage_id="cover",
            stage_status={
                "info": "completed",
                "characters": "completed",
                "summary": "completed",
                "outline": "completed",
                "detail": "completed",
                "text": "completed",
                "cover": "awaiting_decision",
                "export": "locked",
            },
            pending_decisions=[{
                "type": "stage_artifact_decision",
                "decision_id": decision_id,
                "node_id": "cover.human_decision",
                "artifact_ref": source.artifact_id,
                "domain_revision": 0,
                "allowed_actions": ["accept", "regenerate", "cancel"],
            }],
            updated_at="ignored",
        ),
    )

    rejected = client.post(
        f"/api/runs/api-run-cover-binding/decisions/{decision_id}",
        json={
            "action": "accept",
            "domain_revision": 0,
            "artifact": {
                "brief": {
                    "concept": "被改写的新概念",
                    "image_prompt": "另一幅尚未生成的画面",
                    "palette": ["#ffffff"],
                    "negative_constraints": [],
                },
                "selected_asset_id": asset.asset_id,
            },
        },
    )

    assert rejected.status_code == 422
    assert "brief changes require regeneration" in rejected.text
    assert stores.artifacts.latest(
        "api-run-cover-binding", "cover", status="candidate"
    ).artifact_id == source.artifact_id


def test_checkpoint_branch_api_creates_a_new_run_from_an_interrupt(tmp_path, monkeypatch) -> None:
    client, checkpoint_id, _ = _branch_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/runs/api-branch-source/branches",
        json={"target_run_id": "api-branch-target", "checkpoint_id": checkpoint_id},
    )

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "api-branch-target",
        "thread_id": "api-branch-target",
        "status": "awaiting_decision",
        "source_run_id": "api-branch-source",
        "source_checkpoint_id": checkpoint_id,
    }
    branch = client.get("/api/runs/api-branch-target").json()
    assert branch["definition"]["branch_origin"] == {
        "source_run_id": "api-branch-source",
        "source_checkpoint_id": checkpoint_id,
    }
    stream = client.get("/api/runs/api-branch-target/events?after=0")
    assert stream.status_code == 200
    assert '"type": "decision.required"' in stream.text
    assert '"run_id": "api-branch-target"' in stream.text


def test_checkpoint_branch_api_rejects_an_unknown_checkpoint(tmp_path, monkeypatch) -> None:
    client, _, _ = _branch_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/runs/api-branch-source/branches",
        json={"target_run_id": "api-branch-unknown", "checkpoint_id": "missing-checkpoint"},
    )

    assert response.status_code == 422
    assert "checkpoint" in response.json()["detail"].lower()
    assert client.get("/api/runs/api-branch-unknown").status_code == 404


def test_checkpoint_branch_api_rejects_a_checkpoint_without_interrupt(tmp_path, monkeypatch) -> None:
    client, _, checkpoint_id = _branch_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/runs/api-branch-source/branches",
        json={"target_run_id": "api-branch-non-interrupt", "checkpoint_id": checkpoint_id},
    )

    assert response.status_code == 422
    assert "active decision" in response.json()["detail"]
    assert client.get("/api/runs/api-branch-non-interrupt").status_code == 404


def test_checkpoint_branch_api_rejects_an_existing_target(tmp_path, monkeypatch) -> None:
    client, checkpoint_id, _ = _branch_client(tmp_path, monkeypatch)
    created = client.post(
        "/api/runs",
        json={
            "run_id": "api-branch-conflict",
            "project_id": "project-1",
            "inputs": {"genre": "悬疑"},
            "book_scale_plan": _book_plan(1),
            "provider_bindings": _bindings(),
            **_run_contract_payload(),
        },
    )
    assert created.status_code == 200

    response = client.post(
        "/api/runs/api-branch-source/branches",
        json={"target_run_id": "api-branch-conflict", "checkpoint_id": checkpoint_id},
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
