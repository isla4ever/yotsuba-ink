"""Dormant Phase 32 LangGraph builder driven by a frozen route manifest.

This module is intentionally independent from the legacy NarrativeRuntime.  It
is the small, testable graph slice used to prove that one builder can assemble
the three route contracts without importing the retired fixed-stage executor.
Provider, Artifact and event stores are supplied through the driver/observer
ports so the graph itself owns only routing and review control flow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.runtime.graph.route_run_state import (
    RouteRunStateSnapshot,
    SequentialStageProgress,
    restore_route_run_state,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_compiler import CompiledRouteStage
from novel_workflow.workflows.workflow_ids import is_image_acceptance_deferred_workflow_id


class RouteStageCandidate(BaseModel):
    """The narrow result a Provider-backed stage hands to the graph."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    artifact_ref: str = Field(default="", max_length=500)
    unit_ref: str = Field(default="", max_length=500)


class RouteGraphDriver(Protocol):
    """Provider/Artifact boundary consumed by the shared route graph.

    ``generate_stage`` is never called for a deterministic stage.  In
    particular, Export can only use ``commit_stage`` and therefore cannot
    accidentally acquire a Provider binding through the graph builder.
    """

    async def generate_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        direction: str = "",
    ) -> RouteStageCandidate: ...

    async def validate_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        candidate: RouteStageCandidate,
    ) -> None: ...

    async def commit_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        candidate: RouteStageCandidate,
    ) -> str: ...

    async def commit_writeback(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        artifact_ref: str,
        unit_ref: str,
        retry: bool = False,
    ) -> Any: ...

    def cancel_writeback(self, run_id: str, receipt_ref: str) -> None: ...

    def sequential_unit_refs(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
    ) -> tuple[str, ...]: ...


RouteGraphEventSink = Callable[
    [
        GraphRunDefinition,
        str,
        CompiledRouteStage,
        RouteRunStateSnapshot,
        dict[str, Any],
    ],
    None,
]


@dataclass(frozen=True, slots=True)
class _StageContext:
    definition: GraphRunDefinition
    stage: CompiledRouteStage
    driver: RouteGraphDriver
    event_sink: RouteGraphEventSink | None


def build_route_graph(
    definition: GraphRunDefinition,
    driver: RouteGraphDriver,
    *,
    checkpointer: Any,
    event_sink: RouteGraphEventSink | None = None,
):
    """Compile one route-aware graph for any Phase 32 ``GraphRunDefinition``.

    The graph is assembled from the frozen manifest rather than a local stage
    list.  Each manifest stage is a shared lifecycle subgraph, and the parent
    graph links those subgraphs using the manifest's upstream/downstream edges.
    The function is dormant until the persistence/API cutover wave imports it.
    """

    manifest = definition.route_contract.route_manifest
    builder = StateGraph(RouteRunStateSnapshot)

    for stage in manifest.stages:
        context = _StageContext(definition, stage, driver, event_sink)
        builder.add_node(stage.stage_id, _build_stage_subgraph(context))

    builder.add_conditional_edges(
        START,
        lambda state: state.active_stage_id,
        {stage.stage_id: stage.stage_id for stage in manifest.stages},
    )
    for stage in manifest.stages:
        downstream = tuple(stage.downstream_stage_ids)
        if not downstream:
            builder.add_conditional_edges(
                stage.stage_id,
                lambda state: "stop"
                if state.status in {"cancelled", "failed", "image_deferred"}
                else "done",
                {"stop": END, "done": END},
            )
            continue
        path_map: dict[str, str] = {"stop": END}
        path_map.update({target: target for target in downstream})

        def route_after_stage(
            state: RouteRunStateSnapshot,
            *,
            targets: tuple[str, ...] = downstream,
        ) -> str | list[str]:
            if state.status in {"cancelled", "failed", "image_deferred"}:
                return "stop"
            return targets[0] if len(targets) == 1 else list(targets)

        builder.add_conditional_edges(stage.stage_id, route_after_stage, path_map)

    return builder.compile(
        checkpointer=checkpointer,
        name=f"yotsuba_phase32_{definition.creation_route_id}_route",
    )


def _build_stage_subgraph(context: _StageContext):
    definition = context.definition
    stage = context.stage
    driver = context.driver
    builder = StateGraph(RouteRunStateSnapshot)

    async def stage_started(state: RouteRunStateSnapshot) -> dict[str, Any]:
        state = _validated_state(definition, state)
        sequential_progress = dict(state.sequential_stage_progress)
        active_unit_ref = ""
        ordered_unit_refs = _sequential_unit_refs(context, state)
        if ordered_unit_refs:
            progress_payload = sequential_progress.get(stage.stage_id)
            if progress_payload is None:
                progress = SequentialStageProgress(ordered_unit_refs=ordered_unit_refs)
                sequential_progress[stage.stage_id] = progress.model_dump(mode="json")
            else:
                progress = SequentialStageProgress.model_validate(progress_payload)
            if progress.ordered_unit_refs != ordered_unit_refs:
                raise ValueError(
                    f"Sequential unit order drifted for stage {stage.stage_id}"
                )
            if progress.complete:
                raise ValueError(
                    f"Completed sequential stage {stage.stage_id} cannot restart"
                )
            active_unit_ref = progress.next_unit_ref
        _emit(context, "stage.started", state, {"node_id": f"{stage.stage_id}.started"})
        return {
            "active_stage_id": stage.stage_id,
            "active_unit_ref": active_unit_ref,
            "sequential_stage_progress": sequential_progress,
            "status": "running",
            "stage_status": _stage_status(state, stage.stage_id, "running"),
        }

    async def generate_candidate(state: RouteRunStateSnapshot) -> dict[str, Any]:
        state = _validated_state(definition, state)
        if stage.provider_task_kind is None:
            # Export is deterministic and deliberately has no generation hook.
            return {}
        candidate = await driver.generate_stage(
            definition=definition,
            state=state,
            stage=stage,
            direction=state.stage_revision_directions.get(stage.stage_id, ""),
        )
        candidate = RouteStageCandidate.model_validate(candidate)
        if not candidate.artifact_ref.strip():
            raise ValueError(f"Provider stage {stage.stage_id} returned no candidate ref")
        progress = state.sequential_progress(stage.stage_id)
        if progress is not None and candidate.unit_ref != progress.next_unit_ref:
            raise ValueError(
                f"Provider stage {stage.stage_id} returned a unit outside the frozen cursor"
            )
        _emit(
            context,
            "candidate.created",
            state,
            {
                "node_id": f"{stage.stage_id}.generate",
                "artifact_ref": candidate.artifact_ref,
                "unit_ref": candidate.unit_ref,
            },
        )
        candidates = dict(state.candidate_artifact_refs)
        candidates[stage.stage_id] = candidate.artifact_ref
        return {
            "candidate_artifact_refs": candidates,
            "active_unit_ref": candidate.unit_ref,
        }

    async def validate_candidate(state: RouteRunStateSnapshot) -> dict[str, Any]:
        state = _validated_state(definition, state)
        if stage.provider_task_kind is None:
            # Export has no candidate or Provider binding.  Its deterministic
            # delivery validation happens inside ``commit_stage``.
            return {}
        candidate = RouteStageCandidate(
            artifact_ref=state.candidate_artifact_refs.get(stage.stage_id, ""),
            unit_ref=state.active_unit_ref,
        )
        await driver.validate_stage(
            definition=definition,
            state=state,
            stage=stage,
            candidate=candidate,
        )
        return {}

    async def review_decision(state: RouteRunStateSnapshot) -> dict[str, Any]:
        state = _validated_state(definition, state)
        policy = definition.route_contract.review_policy
        if stage.stage_id in policy.auto_continue_stages:
            _emit(
                context,
                "decision.resolved",
                state,
                {"node_id": f"{stage.stage_id}.decision", "action": "auto_continue"},
            )
            return {
                "pending_decision_action": "accept",
                "pending_decision_redraft_count": 0,
            }
        if stage.stage_id not in policy.mandatory_decision_stages:
            _emit(
                context,
                "decision.resolved",
                state,
                {"node_id": f"{stage.stage_id}.decision", "action": "continue"},
            )
            return {
                "pending_decision_action": "accept",
                "pending_decision_redraft_count": 0,
            }

        candidate = RouteStageCandidate(
            artifact_ref=state.candidate_artifact_refs.get(stage.stage_id, ""),
            unit_ref=state.active_unit_ref,
        )
        redraft_limit = policy.directed_redraft_limit_by_stage.get(stage.stage_id, 0)
        redraft_count = state.pending_decision_redraft_count
        while True:
            decision_id = f"{definition.run_id}:{stage.stage_id}:{candidate.artifact_ref or 'stage'}"
            payload = {
                "type": "route_stage_decision",
                "decision_id": decision_id,
                "thread_id": definition.run_id,
                "creation_route_id": definition.creation_route_id,
                "route_revision": definition.route_revision,
                "stage_id": stage.stage_id,
                "artifact_ref": candidate.artifact_ref,
                "unit_ref": candidate.unit_ref,
                "domain_revision": state.domain_revision,
                "allowed_actions": [
                    "accept",
                    *(["regenerate"] if redraft_count < redraft_limit else []),
                    "cancel",
                ],
                "redraft_limit": redraft_limit,
                "redraft_used": redraft_count,
            }
            _emit(context, "decision.required", state, payload)
            value = interrupt(payload)
            if not isinstance(value, dict) or value.get("decision_id") != decision_id:
                raise ValueError("Route decision id does not match the active interrupt")
            if int(value.get("domain_revision", -1)) != state.domain_revision:
                raise ValueError("Route decision domain revision is stale")
            action = str(value.get("action") or "")
            if action == "accept":
                accepted_ref = str(value.get("candidate_ref") or candidate.artifact_ref)
                accepted = RouteStageCandidate(
                    artifact_ref=accepted_ref,
                    unit_ref=candidate.unit_ref,
                )
                await driver.validate_stage(
                    definition=definition,
                    state=state,
                    stage=stage,
                    candidate=accepted,
                )
                candidate = accepted
                _emit(
                    context,
                    "decision.resolved",
                    state,
                    {
                        "decision_id": decision_id,
                        "action": action,
                        "artifact_ref": candidate.artifact_ref,
                        "draft_ref": str(value.get("draft_ref") or ""),
                    },
                )
                candidates = dict(state.candidate_artifact_refs)
                candidates[stage.stage_id] = candidate.artifact_ref
                return {
                    "candidate_artifact_refs": candidates,
                    "active_unit_ref": candidate.unit_ref,
                    "pending_decision_action": "accept",
                    "pending_decision_redraft_count": 0,
                }
            if action == "cancel":
                _emit(
                    context,
                    "decision.resolved",
                    state,
                    {"decision_id": decision_id, "action": action},
                )
                return {
                    "status": "cancelled",
                    "pending_decision_action": "cancel",
                    "pending_decision_redraft_count": 0,
                }
            if action != "regenerate" or redraft_count >= redraft_limit:
                raise ValueError("Route decision action is not allowed by ReviewPolicy")
            direction = str(value.get("direction") or "").strip()
            if not direction:
                raise ValueError("A directed regeneration requires an explicit direction")
            redraft_count += 1
            candidate = await driver.generate_stage(
                definition=definition,
                state=state,
                stage=stage,
                direction=direction,
            )
            candidate = RouteStageCandidate.model_validate(candidate)
            if not candidate.artifact_ref.strip():
                raise ValueError(f"Regenerated stage {stage.stage_id} returned no candidate ref")
            await driver.validate_stage(
                definition=definition,
                state=state,
                stage=stage,
                candidate=candidate,
            )
            _emit(
                context,
                "decision.resolved",
                state,
                {
                    "decision_id": decision_id,
                    "action": action,
                    "artifact_ref": candidate.artifact_ref,
                },
            )
            _emit(
                context,
                "candidate.created",
                state,
                {
                    "node_id": f"{stage.stage_id}.regenerate",
                    "artifact_ref": candidate.artifact_ref,
                    "unit_ref": candidate.unit_ref,
                },
            )
            candidates = dict(state.candidate_artifact_refs)
            candidates[stage.stage_id] = candidate.artifact_ref
            return {
                "candidate_artifact_refs": candidates,
                "active_unit_ref": candidate.unit_ref,
                "pending_decision_action": "regenerate",
                "pending_decision_redraft_count": redraft_count,
            }

    async def commit_candidate(state: RouteRunStateSnapshot) -> dict[str, Any]:
        state = _validated_state(definition, state)
        if state.status in {"cancelled", "failed"}:
            return {}
        candidate = RouteStageCandidate(
            artifact_ref=state.candidate_artifact_refs.get(stage.stage_id, ""),
            unit_ref=state.active_unit_ref,
        )
        artifact_ref = await driver.commit_stage(
            definition=definition,
            state=state,
            stage=stage,
            candidate=candidate,
        )
        if not str(artifact_ref).strip():
            raise ValueError(f"Stage {stage.stage_id} commit returned no Artifact ref")
        artifacts = dict(state.artifact_refs)
        revision_directions = dict(state.stage_revision_directions)
        revision_directions.pop(stage.stage_id, None)
        sequential_progress = dict(state.sequential_stage_progress)
        progress = state.sequential_progress(stage.stage_id)
        next_unit_ref = ""
        if progress is None:
            artifacts[stage.stage_id] = str(artifact_ref)
        else:
            progress = progress.accept(candidate.unit_ref, str(artifact_ref))
            sequential_progress[stage.stage_id] = progress.model_dump(mode="json")
            next_unit_ref = progress.next_unit_ref
        _emit(
            context,
            "artifact.committed",
            state,
            {
                "artifact_ref": str(artifact_ref),
                "artifact_kind": stage.artifact_kind,
                "node_id": f"{stage.stage_id}.commit",
                "unit_ref": candidate.unit_ref,
            },
        )
        writeback = await _commit_writeback(
            context,
            state,
            artifact_ref=str(artifact_ref),
            unit_ref=candidate.unit_ref,
            retry=False,
        )
        if writeback is not None:
            recovery_count = int(getattr(writeback, "recovery_count", 0) or 0)

            def resolve_writeback_decision(decision_number: int) -> str:
                """Replay one exact interrupt before applying a new side effect."""

                decision_recovery_count = decision_number - 1
                decision_id = (
                    f"{definition.run_id}:writeback:{writeback.receipt_ref}:"
                    f"recovery-{decision_number}"
                )
                payload = {
                    "type": "writeback_recovery",
                    "decision_id": decision_id,
                    "thread_id": definition.run_id,
                    "creation_route_id": definition.creation_route_id,
                    "route_revision": definition.route_revision,
                    "stage_id": stage.stage_id,
                    "unit_ref": candidate.unit_ref,
                    "artifact_ref": str(artifact_ref),
                    "writeback_receipt_ref": writeback.receipt_ref,
                    "domain_revision": state.domain_revision,
                    "allowed_actions": ["retry_writeback", "cancel"],
                    "error_code": writeback.error_code,
                    "error_message": writeback.error_message,
                    "recovery_count": decision_recovery_count,
                }
                _emit(context, "decision.required", state, payload)
                value = interrupt(payload)
                if not isinstance(value, dict) or value.get("decision_id") != decision_id:
                    raise ValueError("Writeback recovery decision id does not match")
                if int(value.get("domain_revision", -1)) != state.domain_revision:
                    raise ValueError("Writeback recovery decision is stale")
                action = str(value.get("action") or "")
                if action not in {"retry_writeback", "cancel"}:
                    raise ValueError("Writeback recovery action is not allowed")
                _emit(
                    context,
                    "decision.resolved",
                    state,
                    {
                        "decision_id": decision_id,
                        "action": action,
                        "unit_ref": candidate.unit_ref,
                        "writeback_receipt_ref": writeback.receipt_ref,
                    },
                )
                return action

            # A node resume reruns this function from the beginning.  Each
            # durable recovery count therefore represents one already-applied
            # retry whose interrupt value LangGraph must replay before it can
            # reach the currently pending recovery decision.  Replaying the
            # decisions without repeating their writeback calls keeps Provider
            # operations and Outbox transitions exactly-once.
            replayed_decisions = recovery_count
            if writeback.status == "cancelled":
                replayed_decisions += 1
            for decision_number in range(1, replayed_decisions + 1):
                action = resolve_writeback_decision(decision_number)
                if action == "cancel":
                    _cancel_writeback(context, writeback.receipt_ref)
                    return {
                        "status": "cancelled",
                        "pending_decision_action": "cancel",
                        "pending_decision_redraft_count": 0,
                    }
                if action != "retry_writeback":
                    raise ValueError("Historical writeback recovery action is invalid")

        decision_number = (
            int(getattr(writeback, "recovery_count", 0) or 0) + 1
            if writeback is not None
            else 1
        )
        while writeback is not None and writeback.status == "needs_action":
            if writeback.evidence_refs:
                _emit_evidence_completed(context, state, writeback)
            _emit(
                context,
                "writeback.failed",
                state,
                {
                    "node_id": f"{stage.stage_id}.writeback",
                    "unit_ref": candidate.unit_ref,
                    "receipt_ref": writeback.receipt_ref,
                    "error_code": writeback.error_code,
                    "error_message": writeback.error_message,
                    "recovery_count": writeback.recovery_count,
                },
            )
            action = resolve_writeback_decision(decision_number)
            if action == "cancel":
                _cancel_writeback(context, writeback.receipt_ref)
                return {
                    "status": "cancelled",
                    "pending_decision_action": "cancel",
                    "pending_decision_redraft_count": 0,
                }
            writeback = await _commit_writeback(
                context,
                state,
                artifact_ref=str(artifact_ref),
                unit_ref=candidate.unit_ref,
                retry=True,
            )
            decision_number += 1
        if writeback is not None and writeback.status not in {"committed", "cancelled"}:
            raise ValueError(
                f"Writeback returned an incomplete status: {writeback.status}"
            )
        if writeback is not None and writeback.status == "cancelled":
            return {
                "status": "cancelled",
                "pending_decision_action": "cancel",
                "pending_decision_redraft_count": 0,
            }
        if writeback is not None:
            _emit_evidence_completed(context, state, writeback)
            _emit(
                context,
                "writeback.queued",
                state,
                {
                    "node_id": f"{stage.stage_id}.writeback",
                    "unit_ref": candidate.unit_ref,
                    "receipt_ref": writeback.receipt_ref,
                    "transaction_ref": writeback.transaction_ref,
                },
            )
            _emit(
                context,
                "writeback.committed",
                state,
                {
                    "node_id": f"{stage.stage_id}.writeback",
                    "unit_ref": candidate.unit_ref,
                    "receipt_ref": writeback.receipt_ref,
                    "transaction_ref": writeback.transaction_ref,
                    "evidence_count": len(writeback.evidence_refs),
                    "fact_count": len(writeback.fact_refs),
                },
            )
        if stage.stage_id == definition.route_contract.route_manifest.terminal_stage_id:
            _emit(
                context,
                "export.ready",
                state,
                {"artifact_ref": str(artifact_ref), "node_id": "export.ready"},
            )
        return {
            "artifact_refs": artifacts,
            "sequential_stage_progress": sequential_progress,
            "active_unit_ref": next_unit_ref,
            "candidate_artifact_refs": {
                key: value
                for key, value in state.candidate_artifact_refs.items()
                if key != stage.stage_id
            },
            "stage_revision_directions": revision_directions,
            "domain_revision": state.domain_revision + 1,
            "pending_decision_action": "",
            "pending_decision_redraft_count": 0,
        }

    def stage_finished(state: RouteRunStateSnapshot) -> dict[str, Any]:
        state = _validated_state(definition, state)
        image_deferred = (
            is_image_acceptance_deferred_workflow_id(definition.workflow_id)
            and stage.stage_id == "cover"
        )
        if image_deferred:
            _emit(
                context,
                "image.deferred",
                state,
                {
                    "node_id": "cover.image_deferred",
                    "reason": "image_acceptance_not_in_current_wave",
                },
            )
        return {
            "stage_status": _stage_status(state, stage.stage_id, "completed"),
            "active_unit_ref": "",
            "pending_decision_action": "",
            "pending_decision_redraft_count": 0,
            "status": (
                "completed"
                if stage.stage_id == definition.route_contract.route_manifest.terminal_stage_id
                else "image_deferred"
                if image_deferred
                else "running"
            ),
        }

    builder.add_node("started", stage_started)
    builder.add_node("generate", generate_candidate)
    builder.add_node("validate", validate_candidate)
    builder.add_node("decision", review_decision)
    builder.add_node("commit", commit_candidate)
    builder.add_node("finished", stage_finished)
    builder.add_edge(START, "started")
    builder.add_edge("started", "generate")
    builder.add_edge("generate", "validate")
    builder.add_edge("validate", "decision")

    def decision_route(state: RouteRunStateSnapshot) -> str:
        if state.status in {"cancelled", "failed", "image_deferred"}:
            return "stop"
        if state.pending_decision_action == "regenerate":
            return "validate"
        return "commit"

    builder.add_conditional_edges(
        "decision",
        decision_route,
        {"stop": END, "validate": "validate", "commit": "commit"},
    )

    def commit_route(state: RouteRunStateSnapshot) -> str:
        if state.status in {"cancelled", "failed", "image_deferred"}:
            return "stop"
        progress = state.sequential_progress(stage.stage_id)
        return "next_unit" if progress is not None and not progress.complete else "finished"

    builder.add_conditional_edges(
        "commit",
        commit_route,
        {"stop": END, "next_unit": "generate", "finished": "finished"},
    )
    builder.add_edge("finished", END)
    return builder.compile(name=f"yotsuba_phase32_{stage.stage_id}_lifecycle")


def _validated_state(
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot | dict[str, Any],
) -> RouteRunStateSnapshot:
    if isinstance(state, RouteRunStateSnapshot):
        return state.validate_for_definition(definition)
    return restore_route_run_state(definition, dict(state))


def _stage_status(
    state: RouteRunStateSnapshot,
    stage_id: str,
    status: str,
) -> dict[str, str]:
    values = dict(state.stage_status)
    values[stage_id] = status
    return values


def _sequential_unit_refs(
    context: _StageContext,
    state: RouteRunStateSnapshot,
) -> tuple[str, ...]:
    if context.stage.unitization != "sequential_units":
        return ()
    resolver = getattr(context.driver, "sequential_unit_refs", None)
    if not callable(resolver):
        return ()
    refs = tuple(
        str(ref).strip()
        for ref in resolver(
            definition=context.definition,
            state=state,
            stage=context.stage,
        )
    )
    if not refs:
        return ()
    if len(refs) != len(set(refs)) or any(not ref for ref in refs):
        raise ValueError(
            f"Sequential unit resolver returned invalid refs for {context.stage.stage_id}"
        )
    return refs


async def _commit_writeback(
    context: _StageContext,
    state: RouteRunStateSnapshot,
    *,
    artifact_ref: str,
    unit_ref: str,
    retry: bool,
) -> Any:
    writer = getattr(context.driver, "commit_writeback", None)
    if not callable(writer):
        return None
    return await writer(
        definition=context.definition,
        state=state,
        stage=context.stage,
        artifact_ref=artifact_ref,
        unit_ref=unit_ref,
        retry=retry,
    )


def _cancel_writeback(context: _StageContext, receipt_ref: str) -> None:
    cancel = getattr(context.driver, "cancel_writeback", None)
    if not callable(cancel):
        raise ValueError("Writeback cancellation is not configured")
    cancel(context.definition.run_id, receipt_ref)


def _emit_evidence_completed(
    context: _StageContext,
    state: RouteRunStateSnapshot,
    writeback: Any,
) -> None:
    _emit(
        context,
        "evidence.completed",
        state,
        {
            "node_id": f"{context.stage.stage_id}.writeback",
            "unit_ref": writeback.unit_ref,
            "receipt_ref": writeback.receipt_ref,
            "evidence_count": len(writeback.evidence_refs),
            "fact_count": len(writeback.fact_refs),
        },
    )


def _emit(
    context: _StageContext,
    event_type: str,
    state: RouteRunStateSnapshot,
    payload: dict[str, Any],
) -> None:
    if context.event_sink is not None:
        context.event_sink(context.definition, event_type, context.stage, state, payload)


__all__ = [
    "RouteGraphDriver",
    "RouteGraphEventSink",
    "RouteStageCandidate",
    "build_route_graph",
]
