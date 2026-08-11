from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from langgraph.errors import GraphBubbleUp

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.runtime.graph.provider_gateway import ProviderOperationError
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import (
    GraphFailure,
    NarrativeRunState,
    copy_stage_status,
)


def guarded_node(
    executor: StageExecutor,
    node_id: str,
    stage_id: StageId,
    function: Callable[[NarrativeRunState], Any],
):
    async def guarded(state: NarrativeRunState) -> dict[str, Any]:
        if state.get("failure") is not None:
            return {}
        occurrence_id = _node_occurrence_id(state, node_id)
        executor.events.append(
            state["run_id"],
            event_id=f"{occurrence_id}:started",
            type="node.started",
            stage_id=stage_id,
            node_id=node_id,
            chapter_id=str(state.get("active_chapter_id") or ""),
            status="running",
        )
        try:
            result = function(state)
            if inspect.isawaitable(result):
                result = await result
            update = dict(result or {})
            executor.events.append(
                state["run_id"],
                event_id=f"{occurrence_id}:completed",
                type="node.completed",
                stage_id=stage_id,
                node_id=node_id,
                chapter_id=str(update.get("active_chapter_id") or state.get("active_chapter_id") or ""),
                status="completed",
                payload={
                    "provider_usage": executor.operations.usage_summary(
                        state["run_id"]
                    ).model_dump(mode="json")
                },
            )
            return update
        except GraphBubbleUp:
            raise
        except Exception as exc:
            operation_refs = [
                *list(state.get("pending_operation_refs") or []),
                *list(state.get("review_operation_refs") or []),
            ]
            evidence_ref = str(state.get("pending_writeback_ref") or "")
            if not evidence_ref and isinstance(exc, ProviderOperationError):
                evidence_ref = exc.operation_key
            if not evidence_ref and operation_refs:
                evidence_ref = str(operation_refs[-1])
            failure: GraphFailure = {
                "node_id": node_id,
                "code": type(exc).__name__,
                "retryable": False,
                "evidence_ref": evidence_ref,
            }
            return {
                "failure": failure,
                "status": "failed",
                "stage_status": copy_stage_status(state, stage_id, "failed"),
            }

    return guarded


def _node_occurrence_id(state: NarrativeRunState, node_id: str) -> str:
    stage_id = node_id.partition(".")[0]
    attempt = int((state.get("stage_attempts") or {}).get(stage_id, 1))
    chapter_id = str(state.get("active_chapter_id") or "no-chapter")
    chapter_attempt = int((state.get("chapter_attempts") or {}).get(chapter_id, 1))
    review_role = str(state.get("review_role") or "no-role")
    revision = int(state.get("domain_revision") or 0)
    return (
        f"{state['run_id']}:node:{node_id}:attempt-{attempt}:"
        f"{chapter_id}:chapter-attempt-{chapter_attempt}:{review_role}:revision-{revision}"
    )


def emit_terminal_failure(
    executor: StageExecutor,
    state: NarrativeRunState,
    stage_id: StageId,
) -> dict[str, Any]:
    failure = state.get("failure")
    if failure is None:
        raise ValueError("Failure node requires a GraphFailure")
    run_id = state["run_id"]
    node_id = failure["node_id"]
    payload = {
        **dict(failure),
        "provider_usage": executor.operations.usage_summary(run_id).model_dump(
            mode="json"
        ),
    }
    executor.events.append(
        run_id,
        event_id=f"{run_id}:{node_id}:failed",
        type="node.failed",
        stage_id=stage_id,
        node_id=node_id,
        chapter_id=str(state.get("active_chapter_id") or ""),
        status="failed",
        payload=payload,
        payload_ref=failure.get("evidence_ref", ""),
    )
    executor.events.append(
        run_id,
        event_id=f"{run_id}:run-failed:{node_id}",
        type="run.failed",
        stage_id=stage_id,
        node_id=node_id,
        chapter_id=str(state.get("active_chapter_id") or ""),
        status="failed",
        payload=payload,
        payload_ref=failure.get("evidence_ref", ""),
    )
    return {"status": "failed"}


def failure_route(state: NarrativeRunState, success: str) -> str:
    return "failure" if state.get("failure") is not None else success


__all__ = ["emit_terminal_failure", "failure_route", "guarded_node"]
