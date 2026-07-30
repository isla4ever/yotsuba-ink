from __future__ import annotations

import copy
from typing import Any

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.api.bootstrap import init_app_state
from novel_workflow.orchestration.chapter_artifact import empty_chapter_artifact, upsert_chapter
from novel_workflow.orchestration.chapter_final_artifact import commit_chapter_artifact_writebacks
from novel_workflow.orchestration.chapter_revision_model import chapter_edit_signature
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import ChapterProgressItem, NovelRunState
from novel_workflow.workflows.templates import default_workflow


def test_summary_sync_rechecks_and_generates_persisted_proposal_idempotently(tmp_path: Any) -> None:
    app, client, workflow, run_id, chapter = _review_app(tmp_path, "summary-sync-review")
    local = _local_revision(chapter)
    payload = _sync_payload(workflow.id, chapter, local, "summary-sync-request-0001")

    first = client.post(f"/api/runs/{run_id}/chapters/chapter-1/sync-summary", json=payload)
    second = client.post(f"/api/runs/{run_id}/chapters/chapter-1/sync-summary", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    synced = first.json()["chapter"]
    proposal = first.json()["proposal"]
    assert synced["summary_dirty"] is False
    assert synced["quality_recheck"]["status"] == "passed"
    assert proposal["status"] == "pending"
    assert proposal["counts"] == {"wiki": 1, "character": 1, "foreshadow": 1}
    assert second.json()["proposal"]["id"] == proposal["id"]

    stored = app.state.run_store.read(run_id)
    event_types = [event["type"] for event in stored["events"]]
    assert event_types.count("chapter_summary_synced") == 1
    assert event_types.count("quality_recheck_completed") == 1
    assert event_types.count("chapter_writeback_proposal_generated") == 1
    assert stored["state"]["wiki_refs"] == []
    assert stored["approval"]["artifact"]["chapters"][0]["writeback_proposal"]["id"] == proposal["id"]


def test_proposal_acceptance_waits_for_finalization_and_commits_once(tmp_path: Any) -> None:
    app, client, workflow, run_id, chapter = _review_app(tmp_path, "accepted-proposal")
    local = _local_revision(chapter)
    synced = client.post(
        f"/api/runs/{run_id}/chapters/chapter-1/sync-summary",
        json=_sync_payload(workflow.id, chapter, local, "summary-sync-accepted-001"),
    ).json()
    proposal = synced["proposal"]
    synced_chapter = synced["chapter"]
    decision = {
        "workflow_id": workflow.id,
        "node_id": "text",
        "chapter_id": "chapter-1",
        "proposal_id": proposal["id"],
        "proposal_signature": proposal["proposal_signature"],
        "decision": "accepted",
        "base_version": synced_chapter["version"],
        "base_signature": chapter_edit_signature(synced_chapter),
        "request_id": "proposal-accept-request-001",
    }

    first = client.post(f"/api/runs/{run_id}/chapters/chapter-1/writeback-proposal", json=decision)
    second = client.post(f"/api/runs/{run_id}/chapters/chapter-1/writeback-proposal", json=decision)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["chapter"]["writeback_proposal"]["status"] == "accepted"
    assert app.state.run_store.read(run_id)["state"]["wiki_refs"] == []

    artifact = first.json()["artifact"]
    approval = client.post(
        f"/api/runs/{run_id}/approve-artifact",
        json={"node_id": "text", "output_key": "chapters", "artifact": artifact},
    )
    assert approval.status_code == 200
    runner = NovelWorkflowRunner(
        providers=app.state.providers,
        wiki_store=app.state.wiki_store,
        run_store=app.state.run_store,
    )
    state = NovelRunState.model_validate(app.state.run_store.read(run_id)["state"])
    node = next(item for item in workflow.nodes if item.id == "text")
    first_events = commit_chapter_artifact_writebacks(runner, node, artifact, state, run_id)
    second_events = commit_chapter_artifact_writebacks(runner, node, artifact, state, run_id)

    special_refs = [item for item in state.wiki_refs if ":wiki:" in str(item.get("output_key") or "")]
    assert len(special_refs) == 1
    assert special_refs[0]["title"] == "7A-13 母带"
    assert len(first_events) == 5
    assert first_events[-1]["type"] == "canon_facts_committed"
    assert second_events == []


def test_canon_conflict_requires_resolution_before_acceptance(tmp_path: Any) -> None:
    app, client, workflow, run_id, chapter = _review_app(tmp_path, "canon-conflict")
    state = NovelRunState.model_validate(app.state.run_store.read(run_id)["state"])
    state.canon_facts = [{
        "id": "canon-fact-existing",
        "target": "7A-13 母带",
        "claim_key": "condition",
        "fact": "母带完好",
        "status": "active",
    }]
    app.state.run_store.update_state(run_id, state)
    local = _local_revision(chapter)
    local["wiki_writebacks"] = [{
        "target": "7A-13 母带",
        "claim_key": "condition",
        "fact": "母带已损坏",
    }]
    synced = client.post(
        f"/api/runs/{run_id}/chapters/chapter-1/sync-summary",
        json=_sync_payload(workflow.id, chapter, local, "summary-sync-canon-conflict"),
    ).json()
    proposal = synced["proposal"]
    conflict = proposal["canon"]["conflicts"][0]
    decision = {
        "workflow_id": workflow.id,
        "node_id": "text",
        "chapter_id": "chapter-1",
        "proposal_id": proposal["id"],
        "proposal_signature": proposal["proposal_signature"],
        "decision": "accepted",
        "base_version": synced["chapter"]["version"],
        "base_signature": chapter_edit_signature(synced["chapter"]),
        "request_id": "proposal-canon-conflict-001",
    }

    blocked = client.post(f"/api/runs/{run_id}/chapters/chapter-1/writeback-proposal", json=decision)
    assert blocked.status_code == 409
    assert "未决冲突" in blocked.json()["detail"]

    resolved = client.post(
        f"/api/runs/{run_id}/chapters/chapter-1/writeback-proposal",
        json={**decision, "request_id": "proposal-canon-conflict-002", "conflict_resolutions": {conflict["id"]: "keep_existing"}},
    )
    assert resolved.status_code == 200
    proposal_after = resolved.json()["chapter"]["writeback_proposal"]
    assert proposal_after["conflict_resolutions"][conflict["id"]] == "keep_existing"


def test_rejected_proposal_does_not_write_structured_canon(tmp_path: Any) -> None:
    app, client, workflow, run_id, chapter = _review_app(tmp_path, "rejected-proposal")
    local = _local_revision(chapter)
    synced = client.post(
        f"/api/runs/{run_id}/chapters/chapter-1/sync-summary",
        json=_sync_payload(workflow.id, chapter, local, "summary-sync-rejected-001"),
    ).json()
    proposal = synced["proposal"]
    synced_chapter = synced["chapter"]
    response = client.post(
        f"/api/runs/{run_id}/chapters/chapter-1/writeback-proposal",
        json={
            "workflow_id": workflow.id,
            "node_id": "text",
            "chapter_id": "chapter-1",
            "proposal_id": proposal["id"],
            "proposal_signature": proposal["proposal_signature"],
            "decision": "rejected",
            "base_version": synced_chapter["version"],
            "base_signature": chapter_edit_signature(synced_chapter),
            "request_id": "proposal-reject-request-001",
        },
    )
    artifact = response.json()["artifact"]
    assert client.post(
        f"/api/runs/{run_id}/approve-artifact",
        json={"node_id": "text", "output_key": "chapters", "artifact": artifact},
    ).status_code == 200

    runner = NovelWorkflowRunner(
        providers=app.state.providers,
        wiki_store=app.state.wiki_store,
        run_store=app.state.run_store,
    )
    state = NovelRunState.model_validate(app.state.run_store.read(run_id)["state"])
    node = next(item for item in workflow.nodes if item.id == "text")
    commit_chapter_artifact_writebacks(runner, node, artifact, state, run_id)

    assert not any(":wiki:" in str(item.get("output_key") or "") for item in state.wiki_refs)
    assert state.stage_display_artifacts.get("chapter_character_shifts", [])[0]["change"] == ""
    assert state.story_bible.foreshadow_ledger == []


def test_stale_summary_and_blocked_recheck_cannot_be_finalized(tmp_path: Any) -> None:
    app, client, workflow, run_id, chapter = _review_app(tmp_path, "blocked-review")
    text_node = next(item for item in workflow.nodes if item.id == "text")
    text_node.quality_policy.min_score = 0.9
    app.state.run_store.update_fields(run_id, workflow=workflow.model_dump())
    local = _local_revision(chapter)
    local["content"] = "过短正文。"
    local["words"] = len(local["content"])
    payload = _sync_payload(workflow.id, chapter, local, "summary-sync-blocked-001")
    stale = client.post(
        f"/api/runs/{run_id}/chapters/chapter-1/sync-summary",
        json={**payload, "persisted_signature": "0" * 64},
    )
    assert stale.status_code == 409

    reviewed = client.post(f"/api/runs/{run_id}/chapters/chapter-1/sync-summary", json=payload)
    assert reviewed.status_code == 200
    artifact = reviewed.json()["artifact"]
    recheck = reviewed.json()["chapter"]["quality_recheck"]
    assert recheck["status"] == "blocked"
    target = next(item for item in recheck["repair_targets"] if item["dimension"] == "structure")
    assert target["chapter_version"] == local["version"]
    assert target["artifact_signature"] == recheck["artifact_signature"]
    assert target["locatable"] is True
    assert target["selected_text"] == "过短正文。"
    assert reviewed.json()["proposal"]["status"] == "blocked"
    approval = client.post(
        f"/api/runs/{run_id}/approve-artifact",
        json={"node_id": "text", "output_key": "chapters", "artifact": artifact},
    )
    assert approval.status_code == 409
    assert "质量复检" in approval.json()["detail"]


def _review_app(tmp_path: Any, run_id: str):
    app = create_app()
    init_app_state(app, tmp_path / "runtime")
    workflow = default_workflow().model_copy(deep=True)
    workflow.quality_mode = "deep"
    inputs = {"project_id": f"project-{run_id}", "quality_mode": "deep"}
    app.state.run_store.create(run_id, workflow, inputs)
    chapter = _chapter()
    artifact = upsert_chapter(empty_chapter_artifact(1), chapter)
    state = NovelRunState(
        run_id=run_id,
        project_id=str(inputs["project_id"]),
        workflow_id=workflow.id,
        inputs=inputs,
    )
    state.artifacts["chapters"] = artifact
    state.chapter_progress = [
        ChapterProgressItem(
            volume="第一卷",
            chapter="第1章",
            status="completed",
            words=chapter["words"],
            quality_score=0.91,
            node_id="text",
        )
    ]
    state.stage_confirmation_state["text"] = {"status": "pending"}
    state.approval_required = True
    app.state.run_store.update_state(run_id, state)
    app.state.run_store.request_approval(run_id, "text", "chapters", artifact)
    return app, TestClient(app), workflow, run_id, chapter


def _sync_payload(workflow_id: str, persisted: dict[str, Any], local: dict[str, Any], request_id: str):
    return {
        "workflow_id": workflow_id,
        "node_id": "text",
        "chapter_id": "chapter-1",
        "summary": local["summary"],
        "base_version": local["version"],
        "base_signature": chapter_edit_signature(local),
        "persisted_signature": chapter_edit_signature(persisted),
        "base_chapter": local,
        "request_id": request_id,
    }


def _local_revision(chapter: dict[str, Any]) -> dict[str, Any]:
    local = copy.deepcopy(chapter)
    local.update(
        {
            "content": chapter["content"] + " 林澈把新线索记入值班册。",
            "summary": "林澈确认母带声纹异常，并把新线索写入值班册。",
            "summary_dirty": True,
            "commit_signature": "",
            "version": 2,
            "revision_history": [
                {"id": "manual-draft", "type": "manual_edit", "status": "draft"}
            ],
        }
    )
    local["words"] = len(local["content"])
    return local


def _chapter() -> dict[str, Any]:
    content = "第1章 正文\n\n林澈在旧港档案馆修复母带，异常声纹像潮水一样反复出现。" * 3
    return {
        "id": "chapter-1",
        "title": "第1章",
        "generated_title": "第1章 7A-13 母带",
        "content": content,
        "words": len(content),
        "status": "completed",
        "version": 1,
        "commit_signature": "committed-signature",
        "summary": "林澈开始修复母带并发现异常声纹。",
        "summary_dirty": False,
        "context_packet": {
            "chapter": "第1章",
            "chapter_index": 1,
            "chapter_kind": "first",
            "chapter_outline": "林澈发现 7A-13 母带的异常声纹。",
        },
        "wiki_writebacks": [{"target": "7A-13 母带", "fact": "母带含有异常声纹。"}],
        "character_shift": {"character": "林澈", "change": "从被动修复转为主动调查。"},
        "foreshadow_updates": [{"name": "异常声纹", "status": "推进", "note": "进入值班册。"}],
        "quality_report": {"score": 0.91},
        "revision_history": [],
        "version_history": [],
    }
