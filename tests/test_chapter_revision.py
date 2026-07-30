from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.api.bootstrap import init_app_state
from novel_workflow.orchestration.chapter_artifact import (
    empty_chapter_artifact,
    rebuild_chapter_artifact,
    upsert_chapter,
)
from novel_workflow.orchestration.chapter_revision_model import (
    ChapterRevisionError,
    apply_revision_candidate,
    build_revision_candidate,
    chapter_edit_signature,
    replace_utf16_selection,
    validate_selection,
)
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import FakeImageProvider, FakeTextProvider


class RevisionProvider(FakeTextProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any] | None = None,
    ) -> Any:
        if task_name == "chapter_selection_revision":
            self.calls += 1
            return {"replacement": "林澈收紧指节，把唯一的声纹证据藏进档案袋。"}
        return await super().generate_structured(
            prompt, task_name=task_name, context=context, schema=schema
        )


def test_utf16_selection_replaces_only_selected_text() -> None:
    content = "开场😀林澈保留母带，结尾不变。"
    selected = "林澈保留母带"
    start = _utf16_length("开场😀")
    end = start + _utf16_length(selected)

    validate_selection(content, start, end, selected)
    revised = replace_utf16_selection(content, start, end, "林澈藏起母带")

    assert revised == "开场😀林澈藏起母带，结尾不变。"
    assert revised.startswith("开场😀")
    assert revised.endswith("，结尾不变。")


def test_selection_candidate_rejects_stale_selection() -> None:
    chapter = _chapter()
    try:
        build_revision_candidate(
            request_id="revision-stale-selection",
            chapter=chapter,
            operation="rewrite",
            direction="",
            start=0,
            end=2,
            selected_text="错误",
            replacement="替换",
        )
    except ChapterRevisionError as exc:
        assert "选区已变化" in str(exc)
    else:
        raise AssertionError("stale selection should be rejected")


def test_selection_revision_preserves_server_and_manual_draft_versions() -> None:
    current = _chapter()
    base = {
        **current,
        "content": current["content"].replace("灯暗了一下", "应急灯骤然熄灭"),
        "version": 2,
        "commit_signature": "",
        "summary_dirty": True,
        "revision_history": [
            {
                "id": "manual-draft",
                "type": "manual_edit",
                "status": "draft",
                "label": "人工修订 v2",
                "detail": "摘要待同步",
            }
        ],
    }
    selected = "林澈把母带推进修复机"
    start = _utf16_length("第1章 正文\n\n😀")
    candidate = build_revision_candidate(
        request_id="revision-local-draft",
        chapter=base,
        operation="rewrite",
        direction="",
        start=start,
        end=start + _utf16_length(selected),
        selected_text=selected,
        replacement="林澈把母带锁进修复机",
    )

    revised = apply_revision_candidate(current, base, candidate)

    assert revised["version"] == 3
    assert [item["id"] for item in revised["version_history"]] == [
        "chapter-1-v1",
        "chapter-1-v2",
    ]
    assert revised["content"].endswith("，旧港档案馆的应急灯骤然熄灭。")


def test_revision_api_is_idempotent_and_restore_creates_new_version(tmp_path: Any) -> None:
    app = create_app()
    init_app_state(app, tmp_path / "runtime")
    provider = RevisionProvider()
    app.state.providers = ProviderRegistry(
        text_provider=provider,
        image_provider=FakeImageProvider(),
        text_providers={"openai-compatible": provider},
        image_providers={"openai-compatible": FakeImageProvider()},
    )
    workflow = default_workflow().model_copy(deep=True)
    workflow.quality_mode = "deep"
    run_id = "chapter-revision-api"
    inputs = {"project_id": "revision-project", "quality_mode": "deep"}
    app.state.run_store.create(run_id, workflow, inputs)
    chapter = _chapter()
    artifact = upsert_chapter(empty_chapter_artifact(1), chapter)
    state = NovelRunState(
        run_id=run_id,
        project_id="revision-project",
        workflow_id=workflow.id,
        inputs=inputs,
    )
    state.artifacts["chapters"] = artifact
    state.stage_confirmation_state["text"] = {"status": "pending"}
    state.approval_required = True
    app.state.run_store.update_state(run_id, state)
    app.state.run_store.request_approval(run_id, "text", "chapters", artifact)
    client = TestClient(app)

    selected = "林澈把母带推进修复机"
    start = _utf16_length("第1章 正文\n\n😀")
    end = start + _utf16_length(selected)
    signature = chapter_edit_signature(chapter)
    generate_payload = {
        "workflow_id": workflow.id,
        "node_id": "text",
        "chapter_id": "chapter-1",
        "start": start,
        "end": end,
        "selected_text": selected,
        "operation": "rewrite",
        "direction": "增强紧迫感",
        "base_version": 1,
        "base_signature": signature,
        "persisted_signature": signature,
        "base_chapter": chapter,
        "request_id": "revision-request-0001",
    }
    first_generate = client.post(
        f"/api/runs/{run_id}/chapter-selection-revisions",
        json=generate_payload,
    )
    second_generate = client.post(
        f"/api/runs/{run_id}/chapter-selection-revisions",
        json=generate_payload,
    )

    assert first_generate.status_code == 200
    assert second_generate.status_code == 200
    assert provider.calls == 1
    candidate = first_generate.json()["candidate"]
    assert candidate["preview_content"].startswith("第1章 正文\n\n😀")
    assert candidate["preview_content"].endswith("，旧港档案馆的灯暗了一下。")

    apply_payload = {
        "workflow_id": workflow.id,
        "node_id": "text",
        "request_id": "revision-request-0001",
        "candidate_signature": candidate["candidate_signature"],
    }
    first_apply = client.post(
        f"/api/runs/{run_id}/chapter-selection-revisions/apply",
        json=apply_payload,
    )
    second_apply = client.post(
        f"/api/runs/{run_id}/chapter-selection-revisions/apply",
        json=apply_payload,
    )

    assert first_apply.status_code == 200
    assert second_apply.status_code == 200
    revised = first_apply.json()["chapter"]
    assert revised["version"] == 2
    assert revised["summary_dirty"] is True
    assert revised["commit_signature"] == ""
    assert revised["content"].endswith("，旧港档案馆的灯暗了一下。")
    assert revised["version_history"][0]["id"] == "chapter-1-v1"
    assert second_apply.json()["chapter"]["version"] == 2
    approval = app.state.run_store.read(run_id)["approval"]
    assert approval["artifact"]["chapters"][0]["content"] == revised["content"]

    stale_payload = {
        **generate_payload,
        "request_id": "revision-request-stale",
    }
    stale = client.post(
        f"/api/runs/{run_id}/chapter-selection-revisions",
        json=stale_payload,
    )
    assert stale.status_code == 409
    assert "刷新" in stale.json()["detail"]
    assert provider.calls == 1

    revised_signature = chapter_edit_signature(revised)
    restore_payload = {
        "workflow_id": workflow.id,
        "node_id": "text",
        "chapter_id": "chapter-1",
        "version_id": "chapter-1-v1",
        "base_version": 2,
        "base_signature": revised_signature,
        "persisted_signature": revised_signature,
        "base_chapter": revised,
        "request_id": "restore-request-0001",
    }
    first_restore = client.post(
        f"/api/runs/{run_id}/chapter-versions/restore",
        json=restore_payload,
    )
    second_restore = client.post(
        f"/api/runs/{run_id}/chapter-versions/restore",
        json=restore_payload,
    )

    assert first_restore.status_code == 200
    assert second_restore.status_code == 200
    restored = first_restore.json()["chapter"]
    assert restored["version"] == 3
    assert restored["content"] == chapter["content"]
    assert restored["summary"] == chapter["summary"]
    assert restored["summary_dirty"] is False
    assert second_restore.json()["chapter"]["version"] == 3


def _chapter() -> dict[str, Any]:
    content = "第1章 正文\n\n😀林澈把母带推进修复机，旧港档案馆的灯暗了一下。"
    return {
        "id": "chapter-1",
        "title": "第1章",
        "generated_title": "第1章 7A-13 母带",
        "content": content,
        "words": len(content),
        "status": "completed",
        "version": 1,
        "commit_signature": "committed-signature",
        "summary": "林澈开始修复母带，并发现档案馆异常。",
        "summary_dirty": False,
        "context_packet": {
            "chapter": "第1章",
            "chapter_index": 1,
            "chapter_kind": "first",
            "chapter_outline": "林澈发现 7A-13 母带异常。",
        },
        "wiki_writebacks": [],
        "character_shift": "林澈开始主动调查。",
        "foreshadow_updates": [],
        "quality_report": {"score": 0.91},
        "revision_history": [],
        "version_history": [],
    }


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2
