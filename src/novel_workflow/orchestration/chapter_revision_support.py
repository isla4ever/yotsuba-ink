from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from novel_workflow.orchestration.chapter_artifact import rebuild_chapter_artifact
from novel_workflow.orchestration.chapter_revision_model import (
    ChapterRevisionError,
    chapter_edit_signature,
)
from novel_workflow.workflows.schemas import NovelRunState, WorkflowDefinition


def revision_context(
    runner: Any,
    workflow: WorkflowDefinition,
    run_id: str,
    node_id: str,
    chapter_id: str,
) -> tuple[dict[str, Any], NovelRunState, Any, dict[str, Any], dict[str, Any]]:
    try:
        stored = runner.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise ChapterRevisionError(f"Unknown run: {run_id}") from exc
    state = NovelRunState.model_validate(stored.get("state") or {})
    node = next((item for item in workflow.nodes if item.id == node_id), None)
    if node is None or node.type != "chapter_text":
        raise ChapterRevisionError("局部修订只支持正文阶段")
    if state.stage_confirmation_state.get(node.id, {}).get("status") == "confirmed":
        raise ChapterRevisionError("正文阶段已定稿，不能继续修改")
    output_key = node.output_key or node.id
    artifact = state.artifacts.get(output_key)
    if not isinstance(artifact, dict):
        raise ChapterRevisionError("正文 Artifact 尚未准备完成")
    artifact = rebuild_chapter_artifact(copy.deepcopy(artifact))
    current = next(
        (item for item in artifact.get("chapters", []) if item.get("id") == chapter_id),
        None,
    )
    if current is None:
        raise ChapterRevisionError("找不到要修订的章节")
    if current.get("status") != "completed":
        raise ChapterRevisionError("章节生成完成后才能局部修订")
    return stored, state, node, artifact, current


def validated_base_chapter(current: dict[str, Any], payload: Any) -> dict[str, Any]:
    base = copy.deepcopy(payload.base_chapter)
    if str(base.get("id") or "") != payload.chapter_id:
        raise ChapterRevisionError("修订章节身份不匹配")
    if int(base.get("version") or 0) != payload.base_version:
        raise ChapterRevisionError("修订版本基线不匹配")
    if chapter_edit_signature(base) != payload.base_signature:
        raise ChapterRevisionError("修订正文签名不匹配")
    current_signature = chapter_edit_signature(current)
    if current_signature != payload.persisted_signature:
        raise ChapterRevisionError("章节已被其他修订更新，请刷新后重试")
    current_version = int(current.get("version") or 0)
    if payload.base_version not in {current_version, current_version + 1}:
        raise ChapterRevisionError("本地版本与已落盘版本跨度异常，请刷新后重试")
    if payload.base_version == current_version + 1:
        revisions = base.get("revision_history") if isinstance(base.get("revision_history"), list) else []
        has_manual_draft = any(
            item.get("type") == "manual_edit" and item.get("status") == "draft"
            for item in revisions
            if isinstance(item, dict)
        )
        if not has_manual_draft:
            raise ChapterRevisionError("本地版本缺少人工修订记录")
    return base


def revision_prompt(chapter: dict[str, Any], payload: Any) -> str:
    operation_rules = {
        "rewrite": "保持事实、人物和情节功能不变，重新组织表达与节奏。",
        "expand": "补足动作、感官和因果衔接，不引入未经上下文支持的新事实。",
        "compress": "删除重复解释和弱信息，保留关键行动、证据与转折。",
        "restyle": "只调整语言气质和句式，不改变事实、人物动机与事件顺序。",
    }
    content = str(chapter.get("content") or "")
    encoded = content.encode("utf-16-le")
    try:
        prefix = encoded[: payload.start * 2].decode("utf-16-le")[-800:]
        suffix = encoded[payload.end * 2 :].decode("utf-16-le")[:800]
    except UnicodeDecodeError as exc:
        raise ChapterRevisionError("选区边界切入了复合字符，请重新选择") from exc
    return (
        "你是专业小说编辑，只改写给定选区。\n"
        f"操作：{operation_rules[payload.operation]}\n"
        f"补充方向：{payload.direction or '保持当前叙事视角与语言风格'}\n"
        f"上文：{prefix}\n"
        f"待修订选区：{payload.selected_text}\n"
        f"下文：{suffix}\n"
        "只返回 JSON 对象 {\"replacement\": \"替换后的正文\"}。replacement 不得包含解释、标题或 Markdown 代码块。"
    )


def request_signature(payload: Any) -> str:
    data = {
        "chapter_id": payload.chapter_id,
        "start": payload.start,
        "end": payload.end,
        "selected_text": payload.selected_text,
        "operation": payload.operation,
        "direction": payload.direction,
        "base_version": payload.base_version,
        "base_signature": payload.base_signature,
        "persisted_signature": payload.persisted_signature,
    }
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def commit_artifact(
    runner: Any,
    stored: dict[str, Any],
    state: NovelRunState,
    node_id: str,
    output_key: str,
    artifact: dict[str, Any],
    chapter_id: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    return commit_artifact_events(
        runner,
        stored,
        state,
        node_id,
        output_key,
        artifact,
        chapter_id,
        [event],
    )


def commit_artifact_events(
    runner: Any,
    stored: dict[str, Any],
    state: NovelRunState,
    node_id: str,
    output_key: str,
    artifact: dict[str, Any],
    chapter_id: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    state.artifacts[output_key] = artifact
    approval = stored.get("approval") or {}
    if approval.get("node_id") == node_id and approval.get("required"):
        approval = {**approval, "artifact": artifact}
    runner.run_store.commit_state_events(
        state.run_id,
        state,
        events,
        approval=approval,
    )
    chapter = next(item for item in artifact["chapters"] if item.get("id") == chapter_id)
    return {"artifact": artifact, "chapter": chapter, "events": events}


def update_chapter_draft(state: NovelRunState, chapter: dict[str, Any]) -> None:
    for draft in state.chapter_drafts:
        if draft.chapter != chapter.get("title"):
            continue
        draft.content = str(chapter.get("content") or "")
        draft.words = int(chapter.get("words") or 0)
        draft.artifact = {
            **draft.artifact,
            "content": chapter.get("content"),
            "summary": chapter.get("summary"),
        }


def persist_state(runner: Any, run_id: str, stored: dict[str, Any], state: NovelRunState) -> None:
    runner.run_store.update_fields(
        run_id,
        state=state.model_dump(),
        approval=stored.get("approval") or {},
    )


def persist_state_event(
    runner: Any,
    run_id: str,
    stored: dict[str, Any],
    state: NovelRunState,
    event: dict[str, Any],
) -> None:
    runner.run_store.commit_state_event(
        run_id,
        state,
        event,
        approval=stored.get("approval") or {},
    )


def read_state(runner: Any, run_id: str) -> NovelRunState:
    return NovelRunState.model_validate(runner.run_store.read(run_id).get("state") or {})


def trim_revision_state(state: NovelRunState) -> None:
    if len(state.chapter_revision_state) > 40:
        state.chapter_revision_state = dict(
            list(state.chapter_revision_state.items())[-40:]
        )
