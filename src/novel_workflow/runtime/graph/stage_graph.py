from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.failure import (
    emit_terminal_failure,
    failure_route,
    guarded_node,
)
from novel_workflow.runtime.graph.state import (
    NarrativeRunState,
    copy_stage_mapping,
    copy_stage_status,
)


DecisionAction = Literal["accept", "regenerate", "cancel"]


def build_stage_graph(stage_id: StageId, executor: StageExecutor):
    builder = StateGraph(NarrativeRunState)

    async def load_context(state: NarrativeRunState) -> dict[str, Any]:
        executor.context_for(state, stage_id)
        attempts = dict(state.get("stage_attempts") or {})
        attempts.setdefault(stage_id, 1)
        return {
            "active_stage_id": stage_id,
            "status": "running",
            "stage_attempts": attempts,
            "stage_status": copy_stage_status(state, stage_id, "running"),
        }

    async def generate_candidate(state: NarrativeRunState) -> dict[str, Any]:
        candidate = await executor.generate_candidate(state, stage_id)
        return {
            "candidate_artifact_refs": copy_stage_mapping(
                state, "candidate_artifact_refs", stage_id, candidate.artifact_id
            ),
            "pending_operation_refs": executor.stage_operation_keys(state, stage_id),
        }

    def validate_contract(state: NarrativeRunState) -> dict[str, Any]:
        executor.validate_candidate(state, stage_id)
        return {}

    def decision_policy(state: NarrativeRunState) -> dict[str, Any]:
        quality_mode = state.get("quality_mode", "balanced")
        replacement_ref = ""
        allowed_actions = (
            ["accept", "cancel"]
            if stage_id == "export"
            else ["accept", "regenerate", "cancel"]
        )
        if quality_mode == "fast":
            action: DecisionAction = "accept"
            direction = ""
            decision_id = _decision_id(state, stage_id)
            _emit_decision_resolved(executor, state, stage_id, decision_id, action)
        else:
            candidate_ref = (state.get("candidate_artifact_refs") or {})[stage_id]
            decision_id = _decision_id(state, stage_id)
            executor.events.append(
                state["run_id"],
                event_id=f"{decision_id}:required",
                type="decision.required",
                stage_id=stage_id,
                node_id=f"{stage_id}.human_decision",
                status="awaiting_decision",
                payload={
                    "decision_id": decision_id,
                    "thread_id": state["run_id"],
                    "node_id": f"{stage_id}.human_decision",
                    "artifact_ref": candidate_ref,
                    "domain_revision": state.get("domain_revision", 0),
                    "allowed_actions": allowed_actions,
                },
            )
            value = interrupt(
                {
                    "type": "stage_artifact_decision",
                    "decision_id": decision_id,
                    "thread_id": state["run_id"],
                    "node_id": f"{stage_id}.human_decision",
                    "artifact_ref": candidate_ref,
                    "domain_revision": state.get("domain_revision", 0),
                    "allowed_actions": allowed_actions,
                }
            )
            action, replacement_ref, direction = _validate_decision(
                value,
                decision_id,
                state.get("domain_revision", 0),
                allowed_actions,
            )
            _emit_decision_resolved(executor, state, stage_id, decision_id, action)
        update: dict[str, Any] = {
            "decision_actions": copy_stage_mapping(
                state, "decision_actions", stage_id, action
            ),
            "decision_ids": copy_stage_mapping(
                state, "decision_ids", stage_id, decision_id
            ),
            "status": "running" if action != "cancel" else "cancelled",
        }
        if replacement_ref:
            update["candidate_artifact_refs"] = copy_stage_mapping(
                state,
                "candidate_artifact_refs",
                stage_id,
                replacement_ref,
            )
        if action == "regenerate":
            update["stage_revision_directions"] = copy_stage_mapping(
                state,
                "stage_revision_directions",
                stage_id,
                direction,
            )
        return update

    def commit_artifact(state: NarrativeRunState) -> dict[str, Any]:
        decision_id = str((state.get("decision_ids") or {}).get(stage_id) or "")
        if not decision_id:
            raise ValueError(f"Missing resolved decision id for {stage_id}")
        committed = executor.commit_candidate(
            state,
            stage_id,
            decision_id=decision_id,
        )
        return {
            "artifact_refs": copy_stage_mapping(
                state, "artifact_refs", stage_id, committed.artifact_id
            ),
            "domain_revision": int(state.get("domain_revision") or 0) + 1,
        }

    def checkpoint_stage(state: NarrativeRunState) -> dict[str, Any]:
        return {
            "stage_status": copy_stage_status(state, stage_id, "completed"),
            "status": "running",
        }

    def prepare_regeneration(state: NarrativeRunState) -> dict[str, Any]:
        attempts = dict(state.get("stage_attempts") or {})
        attempts[stage_id] = int(attempts.get(stage_id) or 1) + 1
        return {"stage_attempts": attempts}

    def fail_stage(state: NarrativeRunState) -> dict[str, Any]:
        return emit_terminal_failure(executor, state, stage_id)

    builder.add_node("load_context", guarded_node(executor, f"{stage_id}.load_context", stage_id, load_context))
    builder.add_node("generate_candidate", guarded_node(executor, f"{stage_id}.generate_candidate", stage_id, generate_candidate))
    builder.add_node("validate_contract", guarded_node(executor, f"{stage_id}.validate_contract", stage_id, validate_contract))
    builder.add_node("decision_policy", guarded_node(executor, f"{stage_id}.decision_policy", stage_id, decision_policy))
    builder.add_node("commit_artifact", guarded_node(executor, f"{stage_id}.commit_artifact", stage_id, commit_artifact))
    builder.add_node("checkpoint_stage", guarded_node(executor, f"{stage_id}.checkpoint_stage", stage_id, checkpoint_stage))
    builder.add_node("prepare_regeneration", guarded_node(executor, f"{stage_id}.prepare_regeneration", stage_id, prepare_regeneration))
    builder.add_node("fail_stage", fail_stage)
    builder.add_edge(START, "load_context")
    builder.add_conditional_edges("load_context", lambda state: failure_route(state, "generate_candidate"), {"failure": "fail_stage", "generate_candidate": "generate_candidate"})
    builder.add_conditional_edges("generate_candidate", lambda state: failure_route(state, "validate_contract"), {"failure": "fail_stage", "validate_contract": "validate_contract"})
    builder.add_conditional_edges("validate_contract", lambda state: failure_route(state, "decision_policy"), {"failure": "fail_stage", "decision_policy": "decision_policy"})
    builder.add_conditional_edges(
        "decision_policy",
        lambda state: (
            "failure"
            if state.get("failure") is not None
            else (state.get("decision_actions") or {}).get(stage_id, "cancel")
        ),
        {
            "accept": "commit_artifact",
            "regenerate": "prepare_regeneration",
            "cancel": END,
            "failure": "fail_stage",
        },
    )
    builder.add_conditional_edges("prepare_regeneration", lambda state: failure_route(state, "generate_candidate"), {"failure": "fail_stage", "generate_candidate": "generate_candidate"})
    builder.add_conditional_edges("commit_artifact", lambda state: failure_route(state, "checkpoint_stage"), {"failure": "fail_stage", "checkpoint_stage": "checkpoint_stage"})
    builder.add_conditional_edges("checkpoint_stage", lambda state: failure_route(state, "done"), {"failure": "fail_stage", "done": END})
    builder.add_edge("fail_stage", END)
    return builder.compile(name=f"yotsuba_{stage_id}_stage")


def _decision_id(state: NarrativeRunState, stage_id: StageId) -> str:
    candidate = (state.get("candidate_artifact_refs") or {}).get(stage_id, "missing")
    return f"{state['run_id']}:{stage_id}:{candidate}"


def _validate_decision(
    value: Any,
    decision_id: str,
    domain_revision: int,
    allowed_actions: list[str],
) -> tuple[DecisionAction, str, str]:
    if not isinstance(value, dict):
        raise ValueError("Decision resume value must be an object")
    if value.get("decision_id") != decision_id:
        raise ValueError("Decision id does not match the active interrupt")
    if int(value.get("domain_revision", -1)) != domain_revision:
        raise ValueError("Decision domain revision is stale")
    action = value.get("action")
    if action not in allowed_actions:
        raise ValueError("Unsupported stage decision action")
    replacement_ref = value.get("candidate_artifact_id", "")
    if replacement_ref and (action != "accept" or not isinstance(replacement_ref, str)):
        raise ValueError("Candidate Artifact replacement is only valid for accept")
    direction = str(value.get("direction") or "").strip()
    if action == "regenerate" and not direction:
        raise ValueError("A stage regeneration requires an explicit direction")
    if direction and action != "regenerate":
        raise ValueError("A revision direction is only valid for regeneration")
    return action, replacement_ref, direction


def _emit_decision_resolved(
    executor: StageExecutor,
    state: NarrativeRunState,
    stage_id: StageId,
    decision_id: str,
    action: DecisionAction,
) -> None:
    """Record policy and human decisions through the same stable event contract."""
    executor.events.append(
        state["run_id"],
        event_id=f"{decision_id}:{action}:resolved",
        type="decision.resolved",
        stage_id=stage_id,
        node_id=f"{stage_id}.human_decision",
        status=action,
        payload={"decision_id": decision_id, "action": action},
    )


__all__ = ["DecisionAction", "build_stage_graph"]
