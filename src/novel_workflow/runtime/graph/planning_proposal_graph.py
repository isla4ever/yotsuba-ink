from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.runtime.graph.failure import guarded_node
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState, copy_stage_status


MAX_PLANNING_PROPOSAL_RETRIES = 1


def build_planning_proposal_graph(
    executor: StageExecutor,
    *,
    stage_id: StageId,
    node_id: str,
    generate: Callable[[NarrativeRunState], Awaitable[dict[str, Any]]],
):
    """Run a planning proposal with one author-approved frozen-input retry."""

    builder = StateGraph(NarrativeRunState)

    def prepare(state: NarrativeRunState) -> dict[str, Any]:
        attempts = dict(state.get("stage_attempts") or {})
        attempts.setdefault(stage_id, 1)
        return {
            "active_stage_id": stage_id,
            "stage_attempts": attempts,
            "stage_status": copy_stage_status(state, stage_id, "running"),
            "status": "running",
        }

    async def generate_proposal(state: NarrativeRunState) -> dict[str, Any]:
        return await generate(state)

    def failure_decision(state: NarrativeRunState) -> dict[str, Any]:
        failure = state.get("failure")
        if failure is None:
            raise ValueError("Planning proposal failure decision requires a failure")
        if not failure.get("retryable"):
            return {"status": "failed"}
        attempt = int((state.get("stage_attempts") or {}).get(stage_id) or 1)
        if attempt > MAX_PLANNING_PROPOSAL_RETRIES:
            return {
                "failure": {**failure, "retryable": False},
                "status": "failed",
            }

        decision_id = (
            f"{state['run_id']}:{stage_id}:{_decision_scope(node_id)}:"
            f"failure-attempt-{attempt}"
        )
        decision = {
            "type": "stage_failure_decision",
            "decision_id": decision_id,
            "thread_id": state["run_id"],
            "node_id": f"{node_id}.failure_decision",
            "artifact_ref": "",
            "domain_revision": state.get("domain_revision", 0),
            "allowed_actions": ["regenerate", "cancel"],
            "failure": dict(failure),
        }
        failure_payload = {
            **dict(failure),
            "provider_usage": executor.operations.usage_summary(
                state["run_id"]
            ).model_dump(mode="json"),
        }
        executor.events.append(
            state["run_id"],
            event_id=f"{decision_id}:node-failed",
            type="node.failed",
            stage_id=stage_id,
            node_id=node_id,
            status="failed",
            payload=failure_payload,
            payload_ref=str(failure.get("evidence_ref") or ""),
        )
        executor.events.append(
            state["run_id"],
            event_id=f"{decision_id}:required",
            type="decision.required",
            stage_id=stage_id,
            node_id=f"{node_id}.failure_decision",
            status="awaiting_decision",
            payload=decision,
        )
        value = interrupt(decision)
        action = _validate_failure_decision(
            value,
            decision_id=decision_id,
            domain_revision=int(state.get("domain_revision") or 0),
        )
        executor.events.append(
            state["run_id"],
            event_id=f"{decision_id}:{action}:resolved",
            type="decision.resolved",
            stage_id=stage_id,
            node_id=f"{node_id}.failure_decision",
            status=action,
            payload={"decision_id": decision_id, "action": action},
        )
        if action == "cancel":
            return {"failure": None, "status": "cancelled"}

        attempts = dict(state.get("stage_attempts") or {})
        attempts[stage_id] = attempt + 1
        return {
            "failure": None,
            "stage_attempts": attempts,
            "stage_status": copy_stage_status(state, stage_id, "running"),
            "status": "running",
        }

    builder.add_node("prepare", prepare)
    builder.add_node(
        "generate",
        guarded_node(executor, node_id, stage_id, generate_proposal),
    )
    builder.add_node("failure_decision", failure_decision)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "generate")
    builder.add_conditional_edges(
        "generate",
        lambda state: "failure" if state.get("failure") is not None else "done",
        {"failure": "failure_decision", "done": END},
    )
    builder.add_conditional_edges(
        "failure_decision",
        lambda state: (
            "retry"
            if state.get("status") == "running" and state.get("failure") is None
            else "done"
        ),
        {"retry": "generate", "done": END},
    )
    return builder.compile(name=f"{stage_id}_{_decision_scope(node_id)}")


def _validate_failure_decision(
    value: Any,
    *,
    decision_id: str,
    domain_revision: int,
) -> str:
    if not isinstance(value, dict):
        raise ValueError("Planning proposal failure decision must be an object")
    if value.get("decision_id") != decision_id:
        raise ValueError("Planning proposal failure decision id does not match")
    if int(value.get("domain_revision", -1)) != domain_revision:
        raise ValueError("Planning proposal failure decision revision is stale")
    action = value.get("action")
    if action not in {"regenerate", "cancel"}:
        raise ValueError("Unsupported planning proposal failure action")
    if str(value.get("direction") or "").strip():
        raise ValueError("A failed planning proposal retry cannot change frozen input")
    return action


def _decision_scope(node_id: str) -> str:
    return node_id.rsplit(".", maxsplit=1)[-1].replace("_", "-")


__all__ = ["build_planning_proposal_graph"]
