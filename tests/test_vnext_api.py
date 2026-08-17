from __future__ import annotations

import json
import hashlib
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from novel_workflow.workflows.templates import DEEPSEEK_FLASH_MODEL, DEEPSEEK_PRO_MODEL
from tests.phase27_api import (
    configure_phase27_providers,
)
from tests.fakes import fake_brief_payload


def payload(project_id: str, workflow_id: str) -> dict[str, object]:
    return {
        "run_id": "api-run-1",
        "project_id": project_id,
        "workflow_id": workflow_id,
        "inputs": {
            "project_brief": {"genre": "悬疑"},
            "length_envelope": {"word_target_soft": 12_000},
        },
        "export_preferences": {"format": "zip"},
    }


def cast_payload() -> dict[str, object]:
    return {
        "subjects": [
            {
                "id": "subject-lin",
                "name": "林澈",
                "kind": "protagonist",
                "function": "追查潮汐档案",
                "background": "旧港公共档案修复师，长期负责事故录音的校准与归档。",
                "conflict_history": "她在首次修复时见过被替换的母带索引，却因家人牵连保持沉默。",
                "present_stakes": "若证据链失败，她会失去修复资格并承担隐瞒责任。",
                "temperament": "受压时先核对记录，再逼迫相关者明确选择。",
                "speech_style": "短句，少用判断词，习惯先复述记录原文。",
                "drive": "证明证词被系统篡改",
                "change": "从独自取证转向承担公开后果",
                "debut": "chapter:1",
                "limits": ["不能凭猜测定罪"],
                "demand_refs": ["demand-investigator"],
            },
            {
                "id": "subject-ze",
                "name": "林泽",
                "kind": "major",
                "function": "提供家庭共谋的反向证词",
                "background": "旧港事故幸存者，离开港区后一直保管家庭往来录音。",
                "conflict_history": "他曾协助母亲隐瞒母带去向，与主角的调查直接冲突。",
                "present_stakes": "若公开证词，他会失去家人的信任并承担共谋责任。",
                "temperament": "受压时先回避细节，确认退路消失后才一次说清事实。",
                "speech_style": "长句后突然停顿，避免使用确定语气。",
                "drive": "保护母亲免于再次受审",
                "change": "在结局前主动投案",
                "debut": "chapter:30-34",
                "limits": ["不得提前解除证词冲突"],
                "demand_refs": ["demand-counter-witness"],
            },
        ],
        "relations": [
            {
                "a": "subject-lin",
                "b": "subject-ze",
                "type": "互相隐瞒的姐弟",
                "pressure": "潮汐倒计时迫使两人分别担责",
            }
        ],
    }


def test_run_api_uses_phase27_definition_and_rejects_old_input_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "API 合同验证。"}).json()
    response = client.post("/api/runs", json=payload(project["id"], project["workflow_id"]))
    assert response.status_code == 200
    stored = client.get("/api/runs/api-run-1").json()
    assert stored["definition"]["architecture_version"] == "phase27-vnext"
    assert "book_scale_plan" not in json.dumps(stored, ensure_ascii=False)
    assert stored["read_model"]["active_stage_id"] == "brief"

    old_payload = payload(project["id"], project["workflow_id"])
    old_payload["run_id"] = "api-run-old-shape"
    old_payload["scale_profile"] = {
        "chapter_min_reasonable": 1,
        "chapter_max_reasonable": 4,
    }
    old_payload["provider_bindings"] = {
        stage: {"provider_profile_id": "fake", "model": "fake-model"}
        for stage in ("brief", "spine", "cast", "volumes", "detail", "text", "cover")
    }
    old_payload["cover_asset_binding"] = {
        "provider_profile_id": "fake-image",
        "model": "fake-image",
        "candidate_count": 1,
        "size": "256x384",
        "quality": "low",
    }
    assert client.post("/api/runs", json=old_payload).status_code == 422


def test_branch_route_freezes_requested_binding_from_current_project_workflow(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "正文模型分支验证。"}).json()
    workflow = client.app.state.workflow_store.read(project["workflow_id"])
    text_node = next(node for node in workflow["nodes"] if node["id"] == "text")
    text_node["model_settings"]["model"] = DEEPSEEK_FLASH_MODEL
    client.app.state.workflow_store.write(project["workflow_id"], workflow)
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200

    workflow["version"] = "29.2.0-scene-text"
    text_node["model_settings"]["model"] = DEEPSEEK_PRO_MODEL
    client.app.state.workflow_store.write(project["workflow_id"], workflow)
    target = client.app.state.narrative_stores.runs.read("api-run-1").model_copy(
        update={
            "run_id": "api-run-prose-branch",
            "thread_id": "api-run-prose-branch",
            "status": "awaiting_decision",
        }
    )
    create_branch = AsyncMock(return_value=target)
    monkeypatch.setattr(
        client.app.state.narrative_execution,
        "create_branch",
        create_branch,
    )

    response = client.post(
        "/api/runs/api-run-1/branches",
        json={
            "target_run_id": "api-run-prose-branch",
            "checkpoint_id": "checkpoint-detail",
            "binding_override_stages": ["text"],
        },
    )

    assert response.status_code == 200, response.text
    call = create_branch.await_args.kwargs
    assert set(call["provider_binding_overrides"]) == {"text"}
    assert call["provider_binding_overrides"]["text"].model == DEEPSEEK_PRO_MODEL
    assert call["cover_asset_binding_override"] is None
    assert call["binding_override"].source_workflow_id == project["workflow_id"]
    assert call["binding_override"].source_workflow_revision == "29.2.0-scene-text"
    assert call["binding_override"].stages == ["text"]

    invalid = client.post(
        "/api/runs/api-run-1/branches",
        json={
            "checkpoint_id": "checkpoint-detail",
            "binding_override_stages": ["export"],
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "stage_binding_override_invalid"


def test_archived_run_is_read_only_at_api_boundary(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    archive_dir = tmp_path / "runtime" / "novel_workflow" / "archive" / "old-run"
    archive_dir.mkdir(parents=True)
    (archive_dir / "run.json").write_text(json.dumps({"run_id": "old-run", "state": {"status": "failed"}}), encoding="utf-8")
    client = TestClient(create_app())
    archived = client.get("/api/archive/runs/old-run")
    assert archived.status_code == 200
    assert archived.json()["capabilities"]["execute"] is False
    assert client.get("/api/runs/old-run").status_code == 404
    assert client.post("/api/runs/old-run/start").status_code == 404


def test_regeneration_direction_follows_the_pending_decision_kind(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "决策语义验证。"}).json()
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200
    stores = client.app.state.narrative_stores
    current = stores.runs.read("api-run-1")

    def project_pending(decision_type: str) -> None:
        pending = {
            "type": decision_type,
            "decision_id": "decision-1",
            "thread_id": "api-run-1",
            "node_id": (
                "brief.failure_decision"
                if decision_type == "stage_failure_decision"
                else "brief.human_decision"
            ),
            "artifact_ref": "",
            "domain_revision": 0,
            "allowed_actions": ["regenerate", "cancel"],
        }
        stores.runs.project(
            "api-run-1",
            current.model_copy(
                update={
                    "status": "awaiting_decision",
                    "stage_status": {**current.stage_status, "brief": "awaiting_decision"},
                    "pending_decisions": [pending],
                }
            ),
        )

    endpoint = "/api/runs/api-run-1/decisions/decision-1"
    project_pending("stage_artifact_decision")
    missing_direction = client.post(
        endpoint,
        json={"action": "regenerate", "domain_revision": 0},
    )
    assert missing_direction.status_code == 422
    assert "explicit revision direction" in missing_direction.text

    project_pending("stage_failure_decision")
    creative_retry = client.post(
        endpoint,
        json={
            "action": "regenerate",
            "domain_revision": 0,
            "direction": "改变人物关系",
        },
    )
    assert creative_retry.status_code == 422
    assert "reuse the frozen input" in creative_retry.text

    dispatch_resume = MagicMock()
    monkeypatch.setattr(
        client.app.state.narrative_execution,
        "dispatch_resume",
        dispatch_resume,
    )
    retry = client.post(
        endpoint,
        json={"action": "regenerate", "domain_revision": 0},
    )
    assert retry.status_code == 200, retry.text
    command = dispatch_resume.call_args.args[1]
    assert command["action"] == "regenerate"
    assert "direction" not in command


def test_stage_draft_is_decision_bound_and_does_not_advance_the_run(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "阶段草稿验证。"}).json()
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200
    stores = client.app.state.narrative_stores
    candidate = stores.artifacts.save_candidate(
        "api-run-1",
        "brief",
        fake_brief_payload(),
        source="provider:test-stage-draft",
    )
    decision_id = f"api-run-1:brief:{candidate.artifact_id}"
    endpoint = f"/api/runs/api-run-1/stage-drafts/{decision_id}"
    # The immutable candidate event can reach the browser before the read model
    # projects its pending decision. An absent optional sidecar is still empty,
    # while a saved sidecar remains decision-bound below.
    early_empty = client.get(endpoint)
    assert early_empty.status_code == 200
    assert early_empty.json() is None
    current = stores.runs.read("api-run-1")
    pending = {
        "type": "stage_artifact_decision",
        "decision_id": decision_id,
        "thread_id": "api-run-1",
        "node_id": "brief.human_decision",
        "artifact_ref": candidate.artifact_id,
        "domain_revision": 0,
        "allowed_actions": ["accept", "regenerate", "cancel"],
    }
    stores.runs.project(
        "api-run-1",
        current.model_copy(
            update={
                "status": "awaiting_decision",
                "stage_status": {**current.stage_status, "brief": "awaiting_decision"},
                "pending_decisions": [pending],
            }
        ),
    )
    before = client.get("/api/runs/api-run-1/state").json()
    empty = client.get(endpoint)
    assert empty.status_code == 200
    assert empty.json() is None
    first_payload = {**fake_brief_payload(), "title": "盐潮旧证"}
    saved = client.put(
        endpoint,
        json={
            "domain_revision": 0,
            "source_artifact_id": candidate.artifact_id,
            "artifact": first_payload,
        },
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()["payload"]["title"] == "盐潮旧证"
    assert client.get(endpoint).json() == saved.json()
    assert client.get("/api/runs/api-run-1/state").json() == before
    assert [item.status for item in stores.artifacts.list("api-run-1")] == [
        "candidate"
    ]
    assert len(stores.stage_drafts.list("api-run-1")) == 1

    second_payload = {**first_payload, "title": "盐潮证词"}
    second = client.put(
        endpoint,
        json={
            "domain_revision": 0,
            "source_artifact_id": candidate.artifact_id,
            "artifact": second_payload,
        },
    )
    assert second.status_code == 200
    assert second.json()["draft_id"] != saved.json()["draft_id"]
    assert client.get(endpoint).json()["payload"]["title"] == "盐潮证词"
    assert len(stores.stage_drafts.list("api-run-1")) == 2

    changed_scale = client.put(
        endpoint,
        json={
            "domain_revision": 0,
            "source_artifact_id": candidate.artifact_id,
            "artifact": {
                **second_payload,
                "length_envelope": {
                    "word_target_soft": 100_000,
                },
            },
        },
    )
    assert changed_scale.status_code == 422
    assert "length envelope is frozen" in changed_scale.text

    stale = client.put(
        endpoint,
        json={
            "domain_revision": 1,
            "source_artifact_id": candidate.artifact_id,
            "artifact": second_payload,
        },
    )
    assert stale.status_code == 409

    stores.runs.project(
        "api-run-1",
        stores.runs.read("api-run-1").model_copy(
            update={"pending_decisions": []}
        ),
    )
    assert client.get(endpoint).status_code == 409


def test_cast_draft_uses_the_same_frozen_registry_and_scale_as_graph_commit(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "人物编排边界验证。"}).json()
    run_payload = payload(project["id"], project["workflow_id"])
    run_payload["inputs"] = {
        "project_brief": {"genre": "悬疑"},
        "length_envelope": {
            "word_target_soft": 100_000,
        },
    }
    assert client.post("/api/runs", json=run_payload).status_code == 200

    stores = client.app.state.narrative_stores
    candidate = stores.artifacts.save_candidate(
        "api-run-1",
        "cast",
        cast_payload(),
        source="provider:test-cast-draft",
    )
    decision_id = f"api-run-1:cast:{candidate.artifact_id}"
    current = stores.runs.read("api-run-1")
    stores.runs.project(
        "api-run-1",
        current.model_copy(
            update={
                "active_stage_id": "cast",
                "status": "awaiting_decision",
                "stage_status": {**current.stage_status, "cast": "awaiting_decision"},
                "pending_decisions": [
                    {
                        "type": "stage_artifact_decision",
                        "decision_id": decision_id,
                        "thread_id": "api-run-1",
                        "node_id": "cast.human_decision",
                        "artifact_ref": candidate.artifact_id,
                        "domain_revision": 0,
                        "allowed_actions": ["accept", "regenerate", "cancel"],
                    }
                ],
            }
        ),
    )
    endpoint = f"/api/runs/api-run-1/stage-drafts/{decision_id}"

    def save_draft(artifact: dict[str, object]):
        return client.put(
            endpoint,
            json={
                "domain_revision": 0,
                "source_artifact_id": candidate.artifact_id,
                "artifact": artifact,
            },
        )

    unknown_demand = cast_payload()
    unknown_demand["subjects"].append(  # type: ignore[union-attr]
        {
            "id": "subject-father",
            "name": "林父",
                "kind": "historical_record",
                "function": "留下旧案记录",
                "background": "旧港事故记录员，生前负责保管原始证词与录音副本。",
                "conflict_history": "他留下的记录会改变现有潮汐事故责任判断。",
                "present_stakes": "若记录失效，事故责任将永久无法追认。",
                "temperament": "生前谨慎，坚持所有修改留下可核对痕迹。",
                "speech_style": "录音中用词准确，句子短，避免情绪判断。",
                "drive": "保存原始证词",
            "change": "以缺席证据改变当下判断",
            "debut": "chapter:1",
            "limits": ["不得产生当下行动"],
            "demand_refs": ["demand-father-historical"],
        }
    )
    rejected_demand = save_draft(unknown_demand)
    assert rejected_demand.status_code == 422
    assert "unknown role demands" in rejected_demand.text

    added_subject = cast_payload()
    added_subject["subjects"].append(  # type: ignore[union-attr]
        {
            "id": "subject-extra",
            "name": "额外证人",
            "kind": "functional",
            "function": "递交复印件",
            "background": "旧港档案室临时保管员，负责过事故材料的复印与交接。",
            "conflict_history": "他曾接触被替换的母带复印件，但没有保留交接回执。",
            "present_stakes": "若公开经历，他会失去岗位并承担违规交接责任。",
            "temperament": "受压时先推卸程序责任，证据齐全后才承认自己的动作。",
            "speech_style": "用词程序化，常用被动句并回避直接判断。",
            "drive": "完成证据交接",
            "change": "离开调查",
            "debut": "chapter:2",
            "limits": ["不得承担新的因果职责"],
            "demand_refs": ["demand-investigator"],
        }
    )
    rejected_addition = save_draft(added_subject)
    assert rejected_addition.status_code == 422
    assert "registry must match" in rejected_addition.text

    removed_subject = cast_payload()
    removed_subject["subjects"] = removed_subject["subjects"][:1]  # type: ignore[index]
    removed_subject["subjects"][0]["demand_refs"] = [  # type: ignore[index]
        "demand-investigator",
        "demand-counter-witness",
    ]
    removed_subject["relations"] = []
    rejected_removal = save_draft(removed_subject)
    assert rejected_removal.status_code == 422
    assert "registry must match" in rejected_removal.text

    late_debut = cast_payload()
    late_debut["subjects"][1]["debut"] = "chapter:35"  # type: ignore[index]
    rejected_debut = save_draft(late_debut)
    assert rejected_debut.status_code == 422
    assert "debut windows exceed" in rejected_debut.text

    valid_edit = cast_payload()
    valid_edit["subjects"][0]["name"] = "林澈（现用名）"  # type: ignore[index]
    assert save_draft(valid_edit).status_code == 200

    rejected_accept = client.post(
        f"/api/runs/api-run-1/decisions/{decision_id}",
        json={
            "action": "accept",
            "domain_revision": 0,
            "artifact": unknown_demand,
        },
    )
    assert rejected_accept.status_code == 422
    assert "unknown role demands" in rejected_accept.text


def test_context_manifest_api_is_run_scoped_and_returns_404(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "上下文清单验证。"}).json()
    response = client.post("/api/runs", json=payload(project["id"], project["workflow_id"]))
    assert response.status_code == 200
    manifest = _context_manifest()
    record = client.app.state.narrative_stores.context_manifests.write(
        "api-run-1", attempt=1, manifest=manifest
    )

    loaded = client.get(f"/api/runs/api-run-1/context-manifests/{record.manifest_id}")

    assert loaded.status_code == 200
    assert loaded.json()["manifest"]["manifest_hash"] == manifest.manifest_hash
    assert client.get(
        "/api/runs/api-run-1/context-manifests/manifest-" + "0" * 64
    ).status_code == 404
    assert client.get(
        f"/api/runs/missing/context-manifests/{record.manifest_id}"
    ).status_code == 404


def test_sse_api_reconnects_from_the_next_domain_sequence(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "SSE 断线重连验证。"}).json()
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200
    events = client.app.state.narrative_stores.events
    first = events.append(
        "api-run-1",
        event_id="api-run-1:node-started",
        type="node.started",
        stage_id="brief",
        node_id="brief.generate_candidate",
        status="running",
    )
    second = events.append(
        "api-run-1",
        event_id="api-run-1:decision-required",
        type="decision.required",
        stage_id="brief",
        node_id="brief.decision_policy",
        status="awaiting_decision",
        payload={"decision_id": "decision-brief-1"},
    )

    response = client.get(f"/api/runs/api-run-1/events?after={first.sequence}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert f"id: {first.sequence}\n" not in response.text
    assert f"id: {second.sequence}\n" in response.text
    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [json.loads(line)["sequence"] for line in data_lines] == [second.sequence]


def test_sse_replay_passes_a_resolved_interrupt_before_the_current_one(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    configure_phase27_providers(client)
    project = client.post("/api/projects", json={"idea": "SSE 回放验证。"}).json()
    assert client.post(
        "/api/runs",
        json=payload(project["id"], project["workflow_id"]),
    ).status_code == 200
    events = client.app.state.narrative_stores.events
    fixtures = [
        ("historical-required", "decision.required", "brief"),
        ("historical-resolved", "decision.resolved", "brief"),
        ("brief-committed", "artifact.committed", "brief"),
        ("spine-candidate", "artifact.candidate_ready", "spine"),
        ("current-required", "decision.required", "spine"),
    ]
    for event_id, event_type, stage_id in fixtures:
        events.append(
            "api-run-1",
            event_id=f"api-run-1:{event_id}",
            type=event_type,
            stage_id=stage_id,
            node_id=f"{stage_id}.decision_policy",
            status="awaiting_decision" if event_type == "decision.required" else "",
            payload={"decision_id": event_id}
            if event_type.startswith("decision.")
            else None,
        )

    response = client.get("/api/runs/api-run-1/events?after=0")

    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    replay = [json.loads(line) for line in data_lines]
    assert [event["sequence"] for event in replay] == [1, 2, 3, 4, 5]
    assert replay[-1]["stage_id"] == "spine"
    assert replay[-1]["type"] == "decision.required"


def _context_manifest() -> ContextManifest:
    text = "chapter script"
    body = {
        "task": "chapter-1",
        "required": ["detail.chapter"],
        "optional": [],
        "forbidden": ["full_canon"],
        "snippets": [{
            "ref": "detail.chapter",
            "purpose": "chapter_script",
            "text": text,
            "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }],
        "budget": {"input_chars": len(text), "output_tokens": 100},
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["manifest_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return ContextManifest.model_validate(body)
