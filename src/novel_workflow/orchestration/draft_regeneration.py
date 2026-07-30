from __future__ import annotations

from typing import Any
from uuid import uuid4

from novel_workflow.orchestration.draft_candidate_artifacts import (
    artifact_preview,
    build_candidate_prompt,
    candidate_history,
    chapter_candidate_artifact,
    preview_deltas,
)
from novel_workflow.orchestration.provider_execution import execute_text_provider_call
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.usage import drain_budget_events
from novel_workflow.workflows.schemas import NovelRunState, WorkflowDefinition


class DraftRegenerationError(RuntimeError):
    pass


async def regenerate_stage_drafts(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    node_id: str,
    direction: str,
    candidate_count: int = 3,
    request_id: str = "",
) -> list[dict[str, Any]]:
    stored = runner.run_store.read(run_id)
    if not stored.get("state"):
        raise DraftRegenerationError("Run has no active state")
    state = NovelRunState.model_validate(stored.get("state") or {})
    node = next((item for item in workflow.nodes if item.id == node_id), None)
    if node is None:
        raise DraftRegenerationError(f"Unknown stage: {node_id}")
    if node.type == "export_artifact":
        raise DraftRegenerationError(f"Stage does not support draft regeneration: {node_id}")
    mode = str(state.inputs.get("quality_mode") or workflow.quality_mode or "")
    if node.type == "info_recommend":
        if mode not in {"balanced", "deep"}:
            raise DraftRegenerationError("Info draft regeneration requires a manual Info checkpoint")
    elif mode != "deep":
        raise DraftRegenerationError("Draft regeneration is only available in deep mode")
    confirmation = state.stage_confirmation_state.get(node.id, {})
    if confirmation.get("status") == "confirmed":
        raise DraftRegenerationError(f"Stage has already been confirmed: {node_id}")
    if state.artifacts.get(node.output_key or node.id) is None:
        raise DraftRegenerationError(f"Stage artifact is not ready for regeneration: {node_id}")
    count = max(1, min(3, int(candidate_count or 3)))
    request_id = request_id.strip() or f"{node.id}-{uuid4().hex[:10]}"
    request_event = {
        "type": "draft_regeneration_requested",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "section": direction,
        "message": f"按「{direction}」生成候选稿。",
        "request_id": request_id,
        "candidate_count": count,
    }
    previous_draft_state = state.draft_regeneration_state.get(node.id, {})
    history = candidate_history(previous_draft_state)
    state.draft_regeneration_state[node.id] = {
        "status": "generating",
        "direction": direction,
        "candidate_count": count,
        "history": history,
        "request_id": request_id,
    }
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, request_event)
    events = [request_event]

    base_prompt = runner.stages._render_prompt(node, state)
    previous = state.artifacts.get(node.output_key or node.id)
    generated: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        section = f"候选 {index}"
        candidate_id = f"{request_id}-{index}"
        prompt = build_candidate_prompt(base_prompt, direction=direction, candidate_index=index, previous=previous)
        try:
            result = await execute_text_provider_call(
                runner,
                node,
                state,
                prompt=prompt,
                task_name=node.type,
                context={
                    **state.inputs,
                    "artifacts": state.artifacts,
                    "draft_direction": direction,
                    "candidate_index": index,
                },
                schema=None if node.type == "chapter_text" else node.output_schema,
                kind="regeneration",
                idempotency_root=candidate_id,
                primary_attempt_limit=12,
                run_store=runner.run_store,
            )
        except Exception as exc:
            failed = {
                "type": "draft_regeneration_failed",
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "label": node.label,
                "request_id": request_id,
                "error": str(exc),
                "message": "候选生成失败，已退出本轮换稿。",
            }
            state = NovelRunState.model_validate(runner.run_store.read(run_id).get("state") or {})
            audit_events = [{"run_id": run_id, **event} for event in drain_budget_events(state)]
            state.draft_regeneration_state[node.id] = _draft_batch_state(
                status="failed",
                direction=direction,
                count=count,
                generated=generated,
                history=history,
                request_id=request_id,
                error=str(exc),
            )
            runner.run_store.commit_state_events(run_id, state, [*audit_events, failed])
            raise DraftRegenerationError(str(exc)) from exc
        audit_events = [{"run_id": run_id, **event} for event in drain_budget_events(state)]
        if audit_events:
            runner.run_store.commit_state_events(run_id, state, audit_events)
            events.extend(audit_events)
        if node.type == "chapter_text":
            result = chapter_candidate_artifact(result, previous)
        validation = validate_stage_artifact(node.type, result)
        if not validation.valid:
            failed = {
                "type": "artifact_validation_failed",
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "label": node.label,
                "schema_name": validation.schema_name,
                "errors": validation.errors,
                "section": section,
                "candidate_id": candidate_id,
                "request_id": request_id,
            }
            runner.run_store.append_event(run_id, failed)
            events.append(failed)
            continue
        artifact = validation.artifact
        preview = artifact_preview(artifact)
        for delta in preview_deltas(preview):
            delta_event = {
                "type": "draft_candidate_stream_delta",
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "label": node.label,
                "section": section,
                "candidate_id": candidate_id,
                "request_id": request_id,
                "delta": delta,
            }
            runner.run_store.append_event(run_id, delta_event)
            events.append(delta_event)
        candidate = {
            "type": "draft_candidate_generated",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "artifact": artifact,
            "preview": preview,
            "section": section,
            "candidate_id": candidate_id,
            "request_id": request_id,
            "score": round(0.82 + index * 0.02, 2),
        }
        runner.run_store.append_event(run_id, candidate)
        events.append(candidate)
        generated.append(candidate)

    if not generated:
        failed = {
            "type": "draft_regeneration_failed",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "request_id": request_id,
            "error": "所有候选均未通过阶段产物合同校验",
            "message": "候选生成失败，已退出本轮换稿。",
        }
        runner.run_store.append_event(run_id, failed)
        events.append(failed)

    state = NovelRunState.model_validate(runner.run_store.read(run_id).get("state") or {})
    state.draft_regeneration_state[node.id] = _draft_batch_state(
        status="completed" if generated else "failed",
        direction=direction,
        count=count,
        generated=generated,
        history=history,
        request_id=request_id,
    )
    runner.run_store.update_state(run_id, state)
    return events


def _draft_batch_state(
    *,
    status: str,
    direction: str,
    count: int,
    generated: list[dict[str, Any]],
    history: list[dict[str, Any]],
    request_id: str,
    error: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "direction": direction,
        "candidate_count": count,
        "generated_count": len(generated),
        "history": history,
        "request_id": request_id,
        "error": error,
        "candidates": [
            {key: item.get(key) for key in ("section", "candidate_id", "artifact", "preview", "score")}
            for item in generated
        ],
    }


def select_stage_draft_candidate(
    runner: Any,
    workflow: WorkflowDefinition,
    *,
    run_id: str,
    node_id: str,
    section: str,
) -> dict[str, Any]:
    stored = runner.run_store.read(run_id)
    if not stored.get("state"):
        raise DraftRegenerationError("Run has no active state")
    state = NovelRunState.model_validate(stored.get("state") or {})
    node = next((item for item in workflow.nodes if item.id == node_id), None)
    if node is None:
        raise DraftRegenerationError(f"Unknown stage: {node_id}")
    confirmation = state.stage_confirmation_state.get(node.id, {})
    if confirmation.get("status") == "confirmed":
        raise DraftRegenerationError(f"Stage has already been confirmed: {node_id}")
    draft_state = state.draft_regeneration_state.get(node.id, {})
    candidates = draft_state.get("candidates") if isinstance(draft_state, dict) else None
    if not isinstance(candidates, list):
        raise DraftRegenerationError(f"Stage has no generated draft candidates: {node_id}")
    history = draft_state.get("history") if isinstance(draft_state.get("history"), list) else []
    selected = next(
        (
            item
            for item in [*candidates, *history]
            if isinstance(item, dict)
            and (item.get("candidate_id") == section or item.get("section") == section)
        ),
        None,
    )
    if selected is None:
        raise DraftRegenerationError(f"Unknown draft candidate: {section}")
    artifact = selected.get("artifact")
    validation = validate_stage_artifact(node.type, artifact)
    if not validation.valid:
        raise DraftRegenerationError("; ".join(validation.errors))
    output_key = node.output_key or node.id
    artifact = validation.artifact
    state.artifacts[output_key] = artifact
    state.progress[node.id] = {"status": "completed", "output_key": output_key}
    state.draft_regeneration_state[node.id] = {
        **draft_state,
        "status": "selected",
        "selected_section": selected.get("section"),
        "selected_candidate_id": selected.get("candidate_id"),
    }
    approval = stored.get("approval") or {}
    if approval.get("node_id") == node.id:
        approval = {
            **approval,
            "artifact": artifact,
        }
    event = {
        "type": "draft_candidate_selected",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "section": selected.get("section"),
        "candidate_id": selected.get("candidate_id"),
        "request_id": draft_state.get("request_id"),
        "artifact": artifact,
        "preview": selected.get("preview", ""),
        "message": f"{selected.get('section') or '候选稿'} 已选为当前稿。",
    }
    runner.run_store.update_state(run_id, state)
    if approval:
        runner.run_store.update_fields(run_id, approval=approval)
    runner.run_store.append_event(run_id, event)
    return event
