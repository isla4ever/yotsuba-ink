from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.orchestration.chapters import run_chapter_text_node
from novel_workflow.orchestration.chapter_final_artifact import commit_chapter_artifact_writebacks
from novel_workflow.orchestration.cover_assets import cover_has_inflight_asset, generate_cover_assets
from novel_workflow.orchestration.constants import TEXT_NODE_TYPES
from novel_workflow.output_contracts import contract_for_stage, validate_stage_artifact
from novel_workflow.orchestration.control import (
    pause_if_requested,
    should_wait_for_stage_confirmation,
    wait_for_stage_confirmation,
)
from novel_workflow.orchestration.helpers import (
    character_graph,
    continuity_state,
    detail_outline_issue,
    memory_query,
    node_with_mode_policy,
    quality_event,
    update_worldbuilding_state,
    wiki_state,
)
from novel_workflow.orchestration.quality import quality_loop_for_result
from novel_workflow.orchestration.recovery import (
    failure_code,
    mark_stable_checkpoint,
    recovery_required,
    register_failure,
)
from novel_workflow.orchestration.detail_artifact import commit_detail_writebacks
from novel_workflow.orchestration.outline_artifact import commit_outline_writebacks
from novel_workflow.orchestration.parallel_delivery import (
    finish_parallel_delivery,
    merge_with_parallel_delivery,
    start_parallel_cover_delivery,
)
from novel_workflow.orchestration.summary_artifact import commit_summary_writebacks
from novel_workflow.orchestration.variants import drain_deferred_provider_events, execute_with_variants
from novel_workflow.usage import BudgetExceededError, drain_budget_events
from novel_workflow.workflows.schemas import NovelRunState

_MISSING = object()


async def stream_workflow(runner: Any, workflow: Any, run_id: str, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    state, resumed = _initial_state(runner, workflow, run_id, inputs)
    if resumed and cover_has_inflight_asset(state) and not recovery_required(state):
        register_failure(
            state,
            node_id="cover",
            node_type="cover_image",
            code="image_call_interrupted",
            message="封面图片调用在稳定落盘前中断，需要显式恢复并复用原幂等键",
        )
        runner.run_store.update_state(run_id, state)
    if resumed and recovery_required(state):
        state.runtime_phase = "recovery_required"
        runner.run_store.update_state(run_id, state)
        recovery_event = {
            "type": "run_recovery_required",
            "run_id": run_id,
            "node_id": str((state.recovery_state.get("last_failure") or {}).get("node_id") or state.current_stage_id or ""),
            "error": str((state.recovery_state.get("last_failure") or {}).get("message") or "运行在失败后停在最后稳定检查点"),
            "recovery_state": state.recovery_state,
            "checkpoint": state.recovery_state.get("last_stable_checkpoint") or {},
            "message": "运行已停止，请点击继续创作以从最后稳定检查点恢复。",
        }
        runner.run_store.append_event(run_id, recovery_event)
        yield recovery_event
        return
    mode = str(inputs.get("quality_mode") or workflow.quality_mode or "balanced")
    if mode in {"fast", "balanced", "deep"}:
        workflow.quality_mode = mode
        state.inputs["quality_mode"] = mode
    state.runtime_phase = "cockpit_streaming" if mode in {"fast", "balanced"} else "info_generating"
    state.run_has_started = True
    state.mode_locked = True
    state.current_phase = "running"
    ordered_nodes = runner.compiler.compile_order(workflow)
    total = len(ordered_nodes)
    runner.run_store.update_state(run_id, state)
    start_event = {
        "type": "run_resumed" if resumed else "run_started",
        "run_id": run_id,
        "total_nodes": total,
        "quality_mode": mode,
    }
    runner.run_store.append_event(run_id, start_event)
    yield start_event

    parallel_delivery = None
    for index, raw_node in enumerate(ordered_nodes, start=1):
        node = node_with_mode_policy(raw_node, workflow, state)
        if raw_node.id in state.completed_stage_ids:
            output_key = node.output_key or node.id
            artifact = _confirmed_artifact_for_event(state, node)
            if artifact is not _MISSING:
                async for event in _emit_stage_confirmed_if_needed(runner, run_id, state, node, output_key, artifact):
                    yield event
            final_artifact = state.approved_artifacts.get(output_key, state.artifacts.get(output_key, _MISSING))
            if node.type == "summary" and final_artifact is not _MISSING:
                for event in commit_summary_writebacks(runner, node, final_artifact, state, run_id):
                    yield event
            elif node.type == "outline" and final_artifact is not _MISSING:
                for event in commit_outline_writebacks(runner, node, final_artifact, state, run_id):
                    yield event
            elif node.type == "detail_outline" and final_artifact is not _MISSING:
                for event in commit_detail_writebacks(runner, node, final_artifact, state, run_id):
                    yield event
            elif node.type == "chapter_text" and final_artifact is not _MISSING:
                for event in commit_chapter_artifact_writebacks(runner, node, final_artifact, state, run_id):
                    yield event
            if final_artifact is not _MISSING:
                mark_stable_checkpoint(
                    state,
                    node_id=node.id,
                    node_type=node.type,
                    output_key=output_key,
                    status="completed",
                    artifact=final_artifact,
                )
                runner.run_store.update_state(run_id, state)
            continue
        pending_artifact = _pending_confirmation_artifact(state, node)
        if pending_artifact is not _MISSING:
            output_key = node.output_key or node.id
            next_node_id = ordered_nodes[index].id if index < total else ""
            state.current_stage_id = node.id
            state.current_stage_label = node.label
            state.current_stage_type = node.type
            runner.run_store.update_state(run_id, state)
            async for event in wait_for_stage_confirmation(
                runner,
                run_id,
                state,
                node_id=node.id,
                node_type=node.type,
                label=node.label,
                output_key=output_key,
                artifact=pending_artifact,
                next_node_id=next_node_id,
            ):
                yield event
            approved_artifact = state.approved_artifacts.get(output_key, state.artifacts.get(output_key, pending_artifact))
            state.artifacts[output_key] = approved_artifact
            if node.type == "info_recommend":
                state.story_brief = {"source": "approved_artifact", "content": approved_artifact}
                update_worldbuilding_state(node, approved_artifact, state)
            elif node.type == "summary":
                for event in commit_summary_writebacks(runner, node, approved_artifact, state, run_id):
                    yield event
            elif node.type == "outline":
                for event in commit_outline_writebacks(runner, node, approved_artifact, state, run_id):
                    yield event
            elif node.type == "detail_outline":
                for event in commit_detail_writebacks(runner, node, approved_artifact, state, run_id):
                    yield event
            elif node.type == "chapter_text":
                for event in commit_chapter_artifact_writebacks(runner, node, approved_artifact, state, run_id):
                    yield event
            state.completed_stage_ids = _completed_stage_ids(state, node.id)
            state.current_checkpoint_stage_id = node.id
            state.runtime_phase = "stage_ready_to_continue" if mode == "deep" else "cockpit_streaming"
            mark_stable_checkpoint(
                state,
                node_id=node.id,
                node_type=node.type,
                output_key=output_key,
                status="confirmed",
                artifact=approved_artifact,
            )
            runner.run_store.update_state(run_id, state)
            if node.type == "detail_outline":
                parallel_delivery = start_parallel_cover_delivery(
                    runner, workflow, state, run_id, ordered_nodes,
                )
            continue
        async for event in pause_if_requested(runner, run_id, state, node_id=raw_node.id):
            yield event
        finalizing_confirmed_artifact = _resumable_confirmed_artifact(state, node) is not _MISSING
        state.current_stage_id = node.id
        state.current_stage_label = node.label
        state.current_stage_type = node.type
        state.runtime_phase = "stage_streaming" if mode == "deep" else "cockpit_streaming"
        if node.type == "info_recommend":
            state.runtime_phase = "info_generating"
        runner.run_store.update_state(run_id, state)
        if node.memory_policy.read:
            memory_context = runner.wiki_store.load_context(
                state.project_id,
                node_id=node.id,
                node_type=node.type,
                query=memory_query(node, state),
                kinds=[str(kind) for kind in node.memory_policy.kinds],
            )
            state.memory_contexts[node.id] = memory_context
            memory_event = {
                "type": "memory_context_loaded",
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "label": node.label,
                "memory": memory_context,
            }
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, memory_event)
            yield memory_event

        started = {
            "type": "node_started",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "index": index,
            "total": total,
            "contract": (contract_for_stage(node.type).model_dump() if contract_for_stage(node.type) else None),
        }
        if finalizing_confirmed_artifact:
            started["phase"] = "finalizing"
        runner.run_store.append_event(run_id, started)
        yield started

        try:
            if node.type == "chapter_text":
                issue = detail_outline_issue(node, state)
                if issue:
                    qevent = quality_event(node, issue)
                    qevent.score = 0.32
                    qevent.passed = False
                    qevent.checks = {"detail_outline_complete": False}
                    qevent.warnings = [issue]
                    state.quality_events.append(qevent)
                    state.quality_reports.append(qevent.model_dump())
                    event = {
                        "type": "quality_check_completed",
                        "run_id": run_id,
                        "node_id": node.id,
                        "node_type": node.type,
                        "label": node.label,
                        "quality": qevent.model_dump(),
                    }
                    failure = register_failure(
                        state,
                        node_id=node.id,
                        node_type=node.type,
                        code="continuity_blocking",
                        message=issue,
                        retryable=False,
                    )
                    error = {
                        "type": "node_failed",
                        "run_id": run_id,
                        "node_id": node.id,
                        "error": issue,
                        "failure": failure,
                        "recovery_state": state.recovery_state,
                    }
                    state.errors.append(error)
                    state.progress[node.id] = {"status": "failed", "error": issue}
                    runner.run_store.update_state(run_id, state)
                    runner.run_store.append_event(run_id, event)
                    runner.run_store.append_event(run_id, error)
                    yield event
                    yield error
                    break
                chapter_stream = run_chapter_text_node(runner, node, state, workflow, run_id, index, total)
                if parallel_delivery is not None:
                    async for event in merge_with_parallel_delivery(chapter_stream, parallel_delivery):
                        yield event
                    parallel_delivery = None
                else:
                    async for event in chapter_stream:
                        yield event
                if state.errors:
                    state.runtime_phase = "failed"
                    runner.run_store.update_state(run_id, state)
                    break
                state.completed_stage_ids = _completed_stage_ids(state, node.id)
                state.current_checkpoint_stage_id = node.id
                runner.run_store.update_state(run_id, state)
                if should_wait_for_stage_confirmation(mode, node.id, node.type):
                    output_key = node.output_key or node.id
                    artifact = state.artifacts.get(output_key)
                    next_node_id = ordered_nodes[index].id if index < total else ""
                    async for event in wait_for_stage_confirmation(
                        runner,
                        run_id,
                        state,
                        node_id=node.id,
                        node_type=node.type,
                        label=node.label,
                        output_key=output_key,
                        artifact=artifact,
                        next_node_id=next_node_id,
                    ):
                        yield event
                    approved_artifact = state.approved_artifacts.get(output_key, state.artifacts.get(output_key, artifact))
                    state.artifacts[output_key] = approved_artifact
                    for event in commit_chapter_artifact_writebacks(runner, node, approved_artifact, state, run_id):
                        yield event
                    mark_stable_checkpoint(
                        state,
                        node_id=node.id,
                        node_type=node.type,
                        output_key=output_key,
                        status="confirmed",
                        artifact=approved_artifact,
                    )
                    runner.run_store.update_state(run_id, state)
                continue

            output_key = node.output_key or node.id
            resumed_after_approval = False
            resume_result = _resumable_confirmed_artifact(state, node)
            if resume_result is not _MISSING:
                result = resume_result
                state.artifacts[output_key] = result
                state.approved_artifacts[output_key] = result
                if node.type == "info_recommend":
                    state.story_brief = {"source": "approved_artifact", "content": result}
                    update_worldbuilding_state(node, result, state)
                async for event in _emit_stage_confirmed_if_needed(runner, run_id, state, node, output_key, result):
                    yield event
                resumed_after_approval = True
                if node.type != "info_recommend":
                    if node.type == "summary":
                        for event in commit_summary_writebacks(runner, node, result, state, run_id):
                            yield event
                    elif node.type == "outline":
                        for event in commit_outline_writebacks(runner, node, result, state, run_id):
                            yield event
                    elif node.type == "detail_outline":
                        for event in commit_detail_writebacks(runner, node, result, state, run_id):
                            yield event
                    mark_stable_checkpoint(
                        state,
                        node_id=node.id,
                        node_type=node.type,
                        output_key=output_key,
                        status="confirmed",
                        artifact=result,
                    )
                    state.completed_stage_ids = _completed_stage_ids(state, node.id)
                    state.current_checkpoint_stage_id = node.id
                    state.runtime_phase = "cockpit_streaming"
                    runner.run_store.update_state(run_id, state)
                    if node.type == "detail_outline":
                        parallel_delivery = start_parallel_cover_delivery(
                            runner, workflow, state, run_id, ordered_nodes,
                        )
                    continue
            else:
                if node.type == "cover_image" and parallel_delivery is not None:
                    async for event in finish_parallel_delivery(parallel_delivery):
                        yield event
                    parallel_delivery = None
                cover_plan = _resumable_cover_plan(state, node)
                if cover_plan is not _MISSING:
                    result = cover_plan
                    variant_events = []
                else:
                    result, variant_events = await execute_with_variants(runner, node, state, workflow)
                for event in variant_events:
                    event["run_id"] = run_id
                    runner.run_store.append_event(run_id, event)
                    yield event
                if node.type == "cover_image":
                    async for event in generate_cover_assets(
                        runner,
                        node,
                        state,
                        workflow,
                        run_id,
                        plan=None if cover_plan is not _MISSING else result,
                    ):
                        yield event
                    result = state.artifacts.get(output_key, result)
                validation = validate_stage_artifact(node.type, result)
                validation_event = {
                    "type": "artifact_validated" if validation.valid else "artifact_validation_failed",
                    "run_id": run_id,
                    "node_id": node.id,
                    "node_type": node.type,
                    "label": node.label,
                    "schema_name": validation.schema_name,
                    "errors": validation.errors,
                }
                runner.run_store.append_event(run_id, validation_event)
                yield validation_event
                if not validation.valid:
                    message = "; ".join(validation.errors)
                    failure = register_failure(
                        state,
                        node_id=node.id,
                        node_type=node.type,
                        code=failure_code(message, validation=True),
                        message=message,
                    )
                    error = {
                        "type": "node_failed",
                        "run_id": run_id,
                        "node_id": node.id,
                        "error": message,
                        "failure": failure,
                        "recovery_state": state.recovery_state,
                    }
                    state.errors.append(error)
                    state.progress[node.id] = {"status": "failed", "error": error["error"]}
                    state.runtime_phase = "failed"
                    runner.run_store.update_state(run_id, state)
                    runner.run_store.append_event(run_id, error)
                    yield error
                    break
                result = validation.artifact
                state.artifacts[output_key] = result
                state.progress[node.id] = {"status": "completed", "output_key": output_key}
                if node.type not in {"summary", "outline", "detail_outline"}:
                    update_worldbuilding_state(node, result, state)
                completed = {"type": "node_completed", "run_id": run_id, "node_id": node.id, "output_key": output_key, "result": result, "artifact_source": "live"}
                runner.run_store.update_state(run_id, state)
                runner.run_store.append_event(run_id, completed)
                yield completed
                for provider_event in drain_deferred_provider_events(state):
                    runner.run_store.append_event(run_id, provider_event)
                    yield provider_event

            next_node_id = ordered_nodes[index].id if index < total else ""
            if node.type == "info_recommend" and should_wait_for_stage_confirmation(mode, node.id, node.type) and not resumed_after_approval:
                state.story_brief = {"source": "draft_artifact", "content": result}
                state.approval_required = True
                runner.run_store.update_state(run_id, state)
                async for event in wait_for_stage_confirmation(
                    runner,
                    run_id,
                    state,
                    node_id=node.id,
                    node_type=node.type,
                    label=node.label,
                    output_key=output_key,
                    artifact=result,
                    next_node_id=next_node_id,
                ):
                    yield event
                approved_artifact = state.approved_artifacts.get(output_key, state.artifacts.get(output_key, result))
                if approved_artifact != result:
                    state.artifacts[output_key] = approved_artifact
                    update_worldbuilding_state(node, approved_artifact, state)
                state.story_brief = {"source": "approved_artifact", "content": approved_artifact}
                runner.run_store.update_state(run_id, state)
                result = approved_artifact
            elif node.type == "info_recommend" and not resumed_after_approval:
                state.story_brief = {"source": "auto_artifact", "content": result}
                state.approved_artifacts[output_key] = result
                runner.run_store.update_state(run_id, state)

            if node.type in TEXT_NODE_TYPES:
                async for event in quality_loop_for_result(runner, node, result, state, workflow, run_id):
                    yield event
                if state.errors:
                    break
                result = state.artifacts.get(output_key, result)
                if node.type == "info_recommend":
                    state.character_graph = character_graph(node.id, result, state.character_graph)
                    graph_event = {
                        "type": "character_graph_updated",
                        "run_id": run_id,
                        "node_id": node.id,
                        "node_type": node.type,
                        "label": node.label,
                        "character_graph": state.character_graph.model_dump(),
                    }
                    runner.run_store.update_state(run_id, state)
                    runner.run_store.append_event(run_id, graph_event)
                    yield graph_event

            if node.memory_policy.write and node.type not in {"summary", "outline", "detail_outline"}:
                refs = runner._write_memory(node, output_key, result, state)
                state.wiki_refs.extend(refs)
                state.wiki_state = wiki_state(runner, state)
                memory_event = {
                    "type": "memory_writeback_completed",
                    "run_id": run_id,
                    "node_id": node.id,
                    "node_type": node.type,
                    "label": node.label,
                    "written": refs,
                    "status": runner.wiki_store.status(state.project_id),
                }
                runner.run_store.update_state(run_id, state)
                runner.run_store.append_event(run_id, memory_event)
                yield memory_event

            if node.type == "info_recommend":
                state.story_bible = runner.quality_engine.update_story_bible(state.story_bible, node, result)
                state.foreshadow_ledger = state.story_bible.foreshadow_ledger
                state.continuity_state = continuity_state(state)
                story_event = {
                    "type": "story_bible_updated",
                    "run_id": run_id,
                    "node_id": node.id,
                    "node_type": node.type,
                    "label": node.label,
                    "story_bible": state.story_bible.model_dump(),
                }
                runner.run_store.update_state(run_id, state)
                runner.run_store.append_event(run_id, story_event)
                yield story_event
            if node.type != "info_recommend" and should_wait_for_stage_confirmation(mode, node.id, node.type) and not resumed_after_approval:
                result = state.artifacts.get(output_key, result)
                async for event in wait_for_stage_confirmation(
                    runner,
                    run_id,
                    state,
                    node_id=node.id,
                    node_type=node.type,
                    label=node.label,
                    output_key=output_key,
                    artifact=result,
                    next_node_id=next_node_id,
                ):
                    yield event
                result = state.approved_artifacts.get(output_key, state.artifacts.get(output_key, result))
            if node.type == "summary":
                for event in commit_summary_writebacks(runner, node, result, state, run_id):
                    yield event
            elif node.type == "outline":
                for event in commit_outline_writebacks(runner, node, result, state, run_id):
                    yield event
            elif node.type == "detail_outline":
                for event in commit_detail_writebacks(runner, node, result, state, run_id):
                    yield event
            state.completed_stage_ids = _completed_stage_ids(state, node.id)
            state.current_checkpoint_stage_id = node.id
            mark_stable_checkpoint(
                state,
                node_id=node.id,
                node_type=node.type,
                output_key=output_key,
                status="confirmed" if resumed_after_approval else "awaiting_confirmation" if should_wait_for_stage_confirmation(mode, node.id, node.type) else "completed",
                artifact=result,
            )
            if node.id == "export":
                state.pending_export_return = mode == "deep"
                state.runtime_phase = "stage_ready_to_continue" if mode == "deep" else "completed"
            else:
                state.runtime_phase = "stage_ready_to_continue" if should_wait_for_stage_confirmation(mode, node.id, node.type) else "cockpit_streaming"
            runner.run_store.update_state(run_id, state)
            if node.type == "detail_outline":
                parallel_delivery = start_parallel_cover_delivery(
                    runner, workflow, state, run_id, ordered_nodes,
                )
        except Exception as exc:
            message = str(exc)
            for provider_event in drain_deferred_provider_events(state):
                runner.run_store.append_event(run_id, provider_event)
                yield provider_event
            for budget_event in drain_budget_events(state):
                budget_event = {"run_id": run_id, **budget_event}
                runner.run_store.append_event(run_id, budget_event)
                yield budget_event
            failure = register_failure(
                state,
                node_id=node.id,
                node_type=node.type,
                code="budget_exceeded" if isinstance(exc, BudgetExceededError) else failure_code(message),
                message=message,
            )
            error = {
                "type": "node_failed",
                "run_id": run_id,
                "node_id": node.id,
                "error": message,
                "failure": failure,
                "recovery_state": state.recovery_state,
            }
            state.errors.append(error)
            state.progress[node.id] = {"status": "failed", "error": message}
            state.runtime_phase = "failed"
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, error)
            yield error
            break

    if not state.errors:
        state.runtime_phase = "stage_ready_to_continue" if state.pending_export_return else "completed"
        state.run_completed_at = state.run_completed_at or ""
    else:
        state.runtime_phase = "failed"
    if state.pending_export_return and not state.errors:
        done_type = "run_export_ready"
    else:
        done_type = "run_completed" if not state.errors else "run_failed"
    done = {
        "type": done_type,
        "run_id": run_id,
        "state": state.model_dump(),
        "recovery_state": state.recovery_state,
        "checkpoint": state.recovery_state.get("last_stable_checkpoint") or {},
    }
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, done)
    yield done


def _completed_stage_ids(state: NovelRunState, node_id: str) -> list[str]:
    completed = list(state.completed_stage_ids)
    if node_id and node_id not in completed:
        completed.append(node_id)
    return completed


def _initial_state(runner: Any, workflow: Any, run_id: str, inputs: dict[str, Any]) -> tuple[NovelRunState, bool]:
    try:
        stored = runner.run_store.read(run_id)
    except FileNotFoundError:
        stored = {}
    stored_state = stored.get("state") if isinstance(stored, dict) else None
    if isinstance(stored_state, dict) and stored_state.get("run_has_started"):
        state = NovelRunState.model_validate(stored_state)
        state.inputs = {**state.inputs, **inputs}
        state.current_phase = "running"
        state.mode_locked = True
        state.run_has_started = True
        return state, True
    project_id = str(inputs.get("project_id") or (stored.get("project_id") if isinstance(stored, dict) else "") or run_id)
    return NovelRunState(run_id=run_id, project_id=project_id, workflow_id=workflow.id, inputs=inputs), False


def _resumable_confirmed_artifact(state: NovelRunState, node: Any) -> Any:
    output_key = node.output_key or node.id
    confirmation = state.stage_confirmation_state.get(node.id, {})
    if confirmation.get("status") not in {"pending", "confirmed"}:
        return _MISSING
    if state.approval_required:
        return _MISSING
    if output_key in state.approved_artifacts:
        return state.approved_artifacts[output_key]
    if output_key in state.artifacts:
        return state.artifacts[output_key]
    return _MISSING


def _pending_confirmation_artifact(state: NovelRunState, node: Any) -> Any:
    output_key = node.output_key or node.id
    confirmation = state.stage_confirmation_state.get(node.id, {})
    if node.type == "info_recommend" or confirmation.get("status") != "pending" or not state.approval_required:
        return _MISSING
    if output_key in state.artifacts:
        return state.artifacts[output_key]
    return _MISSING


def _resumable_cover_plan(state: NovelRunState, node: Any) -> Any:
    if node.type != "cover_image":
        return _MISSING
    artifact = state.artifacts.get(node.output_key or node.id)
    if not isinstance(artifact, dict) or not artifact.get("candidates"):
        return _MISSING
    generation = artifact.get("asset_generation")
    if not isinstance(generation, dict) or generation.get("status") not in {"planned", "generating", "failed", "partial", "ready"}:
        return _MISSING
    return artifact


def _confirmed_artifact_for_event(state: NovelRunState, node: Any) -> Any:
    output_key = node.output_key or node.id
    confirmation = state.stage_confirmation_state.get(node.id, {})
    if confirmation.get("status") != "confirmed" or confirmation.get("event_emitted"):
        return _MISSING
    if output_key in state.approved_artifacts:
        return state.approved_artifacts[output_key]
    if output_key in state.artifacts:
        return state.artifacts[output_key]
    return _MISSING


async def _emit_stage_confirmed_if_needed(
    runner: Any,
    run_id: str,
    state: NovelRunState,
    node: Any,
    output_key: str,
    artifact: Any,
) -> AsyncIterator[dict[str, Any]]:
    if state.stage_confirmation_state.get(node.id, {}).get("event_emitted"):
        return
    state.stage_confirmation_state[node.id] = {
        "status": "confirmed",
        "node_id": node.id,
        "node_type": node.type,
        "output_key": output_key,
        "event_emitted": True,
    }
    state.approval_required = False
    state.artifacts[output_key] = artifact
    state.approved_artifacts[output_key] = artifact
    confirmed = {
        "type": "stage_artifact_confirmed",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "output_key": output_key,
        "artifact": artifact,
    }
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, confirmed)
    yield confirmed
