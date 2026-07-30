from __future__ import annotations

import copy
from typing import Any

from novel_workflow.orchestration.chapter_artifact import upsert_chapter
from novel_workflow.orchestration.chapter_revision_model import (
    ChapterRevisionError,
    apply_revision_candidate,
    build_revision_candidate,
    chapter_edit_signature,
    restore_chapter_version,
)
from novel_workflow.orchestration.chapter_revision_support import (
    commit_artifact,
    persist_state_event,
    read_state,
    request_signature,
    revision_context,
    revision_prompt,
    trim_revision_state,
    update_chapter_draft,
    validated_base_chapter,
)
from novel_workflow.orchestration.provider_execution import execute_text_provider_call
from novel_workflow.usage import drain_budget_events
from novel_workflow.workflows.schemas import NovelRunState, WorkflowDefinition


async def generate_chapter_selection_revision(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    payload: Any,
) -> dict[str, Any]:
    stored, state, node, artifact, current = revision_context(
        runner, workflow, run_id, payload.node_id, payload.chapter_id
    )
    base = validated_base_chapter(current, payload)
    request_sig = request_signature(payload)
    existing = state.chapter_revision_state.get(payload.request_id, {})
    if existing:
        if existing.get("request_signature") != request_sig:
            raise ChapterRevisionError("request_id 已被其他修订请求使用")
        if existing.get("candidate"):
            return copy.deepcopy(existing["candidate"])
        if existing.get("status") == "generating":
            raise ChapterRevisionError("同一修订请求正在生成，请勿重复提交")
        if existing.get("status") == "failed":
            raise ChapterRevisionError(str(existing.get("error") or "局部修订生成失败"))

    requested = {
        "type": "chapter_selection_revision_requested",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": current.get("title"),
        "chapter_id": payload.chapter_id,
        "request_id": payload.request_id,
        "operation": payload.operation,
        "section": payload.selected_text,
        "message": "已提交局部修订请求。",
    }
    state.chapter_revision_state[payload.request_id] = {
        "status": "generating",
        "request_signature": request_sig,
    }
    persist_state_event(runner, run_id, stored, state, requested)

    prompt = revision_prompt(base, payload)
    try:
        result = await execute_text_provider_call(
            runner,
            node,
            state,
            prompt=prompt,
            task_name="chapter_selection_revision",
            context={
                **state.inputs,
                "chapter_id": payload.chapter_id,
                "operation": payload.operation,
                "direction": payload.direction,
            },
            schema={"type": "object", "properties": {"replacement": {"type": "string"}}, "required": ["replacement"]},
            kind="revision",
            chapter=str(current.get("title") or payload.chapter_id),
            idempotency_root=payload.request_id,
            run_store=runner.run_store,
        )
        replacement = str(result.get("replacement") or "") if isinstance(result, dict) else ""
        candidate = build_revision_candidate(
            request_id=payload.request_id,
            chapter=base,
            operation=payload.operation,
            direction=payload.direction,
            start=payload.start,
            end=payload.end,
            selected_text=payload.selected_text,
            replacement=replacement,
        )
    except Exception as exc:
        latest = read_state(runner, run_id)
        audit_events = [{"run_id": run_id, **event} for event in drain_budget_events(latest)]
        latest.chapter_revision_state[payload.request_id] = {
            "status": "failed",
            "request_signature": request_sig,
            "error": str(exc),
        }
        failed = {
            "type": "chapter_selection_revision_failed",
            "run_id": run_id,
            "node_id": node.id,
            "chapter_id": payload.chapter_id,
            "request_id": payload.request_id,
            "message": str(exc),
        }
        runner.run_store.commit_state_events(
            run_id,
            latest,
            [*audit_events, failed],
            approval=(runner.run_store.read(run_id).get("approval") or {}),
        )
        if isinstance(exc, ChapterRevisionError):
            raise
        raise ChapterRevisionError(f"局部修订生成失败：{exc}") from exc

    audit_events = [{"run_id": run_id, **event} for event in drain_budget_events(state)]
    if audit_events:
        runner.run_store.commit_state_events(run_id, state, audit_events)
    latest_stored = runner.run_store.read(run_id)
    latest = NovelRunState.model_validate(latest_stored.get("state") or {})
    latest.chapter_revision_state[payload.request_id] = {
        "status": "generated",
        "request_signature": request_sig,
        "candidate": candidate,
        "base_chapter": base,
        "persisted_signature": chapter_edit_signature(current),
        "output_key": node.output_key or node.id,
    }
    trim_revision_state(latest)
    generated = {
        "type": "chapter_selection_revision_generated",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": current.get("title"),
        "chapter_id": payload.chapter_id,
        "request_id": payload.request_id,
        "operation": payload.operation,
        "candidate_signature": candidate["candidate_signature"],
        "preview": candidate,
        "message": "局部修订候选已生成，等待确认。",
    }
    persist_state_event(runner, run_id, latest_stored, latest, generated)
    return candidate


def apply_chapter_selection_revision(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    payload: Any,
) -> dict[str, Any]:
    stored = runner.run_store.read(run_id)
    state = NovelRunState.model_validate(stored.get("state") or {})
    saved = state.chapter_revision_state.get(payload.request_id, {})
    if saved.get("status") == "applied":
        if saved.get("candidate", {}).get("candidate_signature") != payload.candidate_signature:
            raise ChapterRevisionError("候选稿签名不匹配")
        return copy.deepcopy(saved["result"])
    candidate = saved.get("candidate")
    base = saved.get("base_chapter")
    if not isinstance(candidate, dict) or not isinstance(base, dict):
        raise ChapterRevisionError("找不到待接受的局部修订候选")
    if candidate.get("candidate_signature") != payload.candidate_signature:
        raise ChapterRevisionError("候选稿签名不匹配")
    _, state, node, artifact, current = revision_context(
        runner, workflow, run_id, payload.node_id, str(candidate.get("chapter_id") or "")
    )
    if chapter_edit_signature(current) != saved.get("persisted_signature"):
        raise ChapterRevisionError("章节已被其他修订更新，请刷新后重试")
    revised = apply_revision_candidate(current, base, candidate)
    artifact = upsert_chapter(copy.deepcopy(artifact), revised)
    update_chapter_draft(state, revised)
    result = {"artifact": artifact, "chapter": revised}
    event = {
        "type": "chapter_selection_revision_applied",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": revised.get("title"),
        "chapter_id": revised.get("id"),
        "request_id": payload.request_id,
        "operation": candidate.get("operation"),
        "candidate_signature": payload.candidate_signature,
        "artifact": artifact,
        "message": f"局部修订已应用为 v{revised.get('version')}。",
    }
    state.chapter_revision_state[payload.request_id] = {
        **saved,
        "status": "applied",
        "result": result,
    }
    return commit_artifact(
        runner,
        stored,
        state,
        node.id,
        node.output_key or node.id,
        artifact,
        str(revised.get("id") or ""),
        event,
    )


def restore_chapter_revision_version(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    payload: Any,
) -> dict[str, Any]:
    initial_stored = runner.run_store.read(run_id)
    initial_state = NovelRunState.model_validate(initial_stored.get("state") or {})
    existing = initial_state.chapter_revision_state.get(payload.request_id, {})
    if existing.get("status") == "restored":
        return copy.deepcopy(existing["result"])
    stored, state, node, artifact, current = revision_context(
        runner, workflow, run_id, payload.node_id, payload.chapter_id
    )
    base = validated_base_chapter(current, payload)
    restored = restore_chapter_version(current, base, payload.version_id, payload.request_id)
    artifact = upsert_chapter(copy.deepcopy(artifact), restored)
    update_chapter_draft(state, restored)
    result = {"artifact": artifact, "chapter": restored}
    event = {
        "type": "chapter_version_restored",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": restored.get("title"),
        "chapter_id": restored.get("id"),
        "request_id": payload.request_id,
        "version_id": payload.version_id,
        "artifact": artifact,
        "message": f"历史版本已恢复为 v{restored.get('version')}。",
    }
    state.chapter_revision_state[payload.request_id] = {
        "status": "restored",
        "result": result,
    }
    trim_revision_state(state)
    return commit_artifact(
        runner,
        stored,
        state,
        node.id,
        node.output_key or node.id,
        artifact,
        str(restored.get("id") or ""),
        event,
    )
