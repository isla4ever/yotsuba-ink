"""Stepwise execution adapter for the shared Phase 32 route graph.

The adapter owns no Provider behavior.  A caller supplies the route driver and
durable LangGraph checkpointer; this module binds graph output to the native
Run repository/read model so monitor state cannot drift into local UI state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langgraph.types import Command

from novel_workflow.orchestration.phase32_run_preflight import Phase32RunPreflight
from novel_workflow.runtime.graph.route_graph import (
    RouteGraphDriver,
    build_route_graph,
)
from novel_workflow.runtime.graph.route_run_state import (
    RouteRunStateSnapshot,
    SequentialStageProgress,
    restore_route_run_state,
)
from novel_workflow.storage.phase32_graph_event_sink import Phase32RepositoryEventSink
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_read_model import (
    ArtifactRefProjection,
    PendingDecisionProjection,
    RunFailureProjection,
    RouteRunReadModel,
)
from novel_workflow.providers.usage import Phase32ProviderUsageSummary
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


class Phase32ExecutionError(ValueError):
    code = "phase32_execution_invalid"

    def __init__(
        self,
        message: str,
        *,
        frontier: "Phase32FailureFrontier | None" = None,
    ) -> None:
        super().__init__(message)
        self.frontier = frontier


@dataclass(frozen=True, slots=True)
class Phase32StepResult:
    record: Phase32RunRecord
    interrupted: bool
    decision: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class Phase32FailureFrontier:
    """Latest checkpointed graph state after a node failure."""

    state: RouteRunStateSnapshot
    checkpoint_id: str
    node_id: str


GraphBuilder = Callable[..., Any]


class Phase32GraphExecutionService:
    """Invoke one graph step and atomically project its state/read model."""

    def __init__(
        self,
        repository: Phase32RunRepository,
        *,
        graph_builder: GraphBuilder = build_route_graph,
        preflight: Phase32RunPreflight | None = None,
    ) -> None:
        self.repository = repository
        self.graph_builder = graph_builder
        self.preflight = preflight or Phase32RunPreflight()

    async def step(
        self,
        run_id: str,
        *,
        driver: RouteGraphDriver,
        checkpointer: Any,
        resume: dict[str, Any] | None = None,
    ) -> Phase32StepResult:
        current = self.repository.read(run_id)
        self.preflight.validate(
            current.definition,
            state=current.state,
            read_model=current.read_model,
        )
        event_sink = Phase32RepositoryEventSink(self.repository)
        graph = self.graph_builder(
            current.definition,
            driver,
            checkpointer=checkpointer,
            event_sink=event_sink,
        )
        config = {"configurable": {"thread_id": current.definition.run_id}}
        input_value: Any = current.state
        if resume is not None:
            # A route decision is a business-level id, while LangGraph resumes
            # interrupts by their checkpoint-scoped interrupt id.  Passing the
            # payload as a scalar works while a single node is active, but can
            # leak the value into a downstream mandatory decision when a
            # sequential stage finishes and the next stage interrupts during
            # the same invocation.  Resolve the active id from the durable
            # checkpoint so the command is consumed exactly once by the
            # intended frontier.
            input_value = Command(
                resume=await _resume_by_interrupt_id(graph, config, resume)
            )
        try:
            output = await graph.ainvoke(input_value, config=config)
        except Exception as exc:
            frontier = await _failure_frontier(graph, config, current.definition)
            raise Phase32ExecutionError(
                f"Phase 32 graph step failed for Run {run_id}",
                frontier=frontier,
            ) from exc
        if not isinstance(output, dict):
            raise Phase32ExecutionError("Phase 32 graph returned a non-object state")
        interrupted, decision = _interrupt_payload(output)
        projection = output
        if interrupted:
            projection, checkpoint_id = await _interrupt_projection(graph, config)
        else:
            checkpoint_id = await _checkpoint_id(graph, config)
        state = _state_from_output(
            current.definition,
            projection,
            interrupted=interrupted,
        )
        if interrupted:
            _validate_interrupt_projection(state, decision)
        read_model = project_phase32_read_model(
            current.read_model,
            current.definition,
            state,
            decision=decision,
            checkpoint_id=checkpoint_id,
            provider_usage=_provider_usage(driver, run_id, current.read_model.provider_usage),
        )
        committed = self.repository.commit_projection(
            run_id,
            state=state,
            read_model=read_model,
        )
        return Phase32StepResult(
            record=committed,
            interrupted=interrupted,
            decision=decision,
        )


def _state_from_output(
    definition: GraphRunDefinition,
    output: dict[str, Any],
    *,
    interrupted: bool,
) -> RouteRunStateSnapshot:
    fields = set(RouteRunStateSnapshot.model_fields)
    payload = {key: output[key] for key in fields if key in output}
    if interrupted:
        payload["status"] = "awaiting_decision"
        stage_status = dict(payload.get("stage_status") or {})
        active_stage_id = str(payload.get("active_stage_id") or "")
        if active_stage_id:
            stage_status[active_stage_id] = "awaiting_decision"
        payload["stage_status"] = stage_status
    try:
        return restore_route_run_state(definition, payload)
    except Exception as exc:
        raise Phase32ExecutionError(
            "Phase 32 graph output does not satisfy its frozen Run state contract"
        ) from exc


def project_phase32_read_model(
    previous: RouteRunReadModel,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    *,
    decision: dict[str, Any] | None,
    checkpoint_id: str,
    provider_usage: Phase32ProviderUsageSummary,
) -> RouteRunReadModel:
    stages = {stage.stage_id: stage for stage in definition.route_contract.route_manifest.stages}
    artifact_refs = {
        stage_id: ArtifactRefProjection(
            artifact_kind=stages[stage_id].artifact_kind,
            artifact_ref=artifact_ref,
        )
        for stage_id, artifact_ref in state.artifact_refs.items()
        if stage_id in stages
    }
    pending = ()
    if decision is not None:
        decision_kind = str(decision.get("type") or "route_stage_decision")
        is_writeback_recovery = decision_kind == "writeback_recovery"
        pending = (
            PendingDecisionProjection(
                decision_id=str(decision.get("decision_id") or ""),
                stage_id=str(decision.get("stage_id") or state.active_stage_id),
                unit_ref=str(decision.get("unit_ref") or ""),
                artifact_ref=str(decision.get("artifact_ref") or ""),
                kind=decision_kind,
                domain_revision=int(decision.get("domain_revision", -1)),
                allowed_actions=tuple(decision.get("allowed_actions") or ()),
                redraft_limit=(
                    None
                    if is_writeback_recovery
                    else int(decision.get("redraft_limit", 0))
                ),
                redraft_used=(
                    None
                    if is_writeback_recovery
                    else int(decision.get("redraft_used", 0))
                ),
            ),
        )
    failure = None
    if state.failure is not None:
        failure = RunFailureProjection(
            code=state.failure.code,
            stage_id=state.failure.node_id.split(".", 1)[0],
            unit_ref=state.active_unit_ref,
            retryable=state.failure.retryable,
            message=state.failure.message,
        )
    updated = previous.model_copy(
        update={
            "status": state.status,
            "active_stage_id": state.active_stage_id,
            "active_unit_ref": state.active_unit_ref,
            "stage_status": dict(state.stage_status),
            "artifact_refs": artifact_refs,
            "sequential_stage_progress": {
                stage_id: SequentialStageProgress.model_validate(progress)
                for stage_id, progress in state.sequential_stage_progress.items()
            },
            "pending_decisions": pending,
            "provider_usage": provider_usage,
            "failure": failure,
            "checkpoint_id": checkpoint_id,
            "updated_at": _now(),
        }
    )
    return updated.validate_for_definition(definition)


def _provider_usage(
    driver: RouteGraphDriver,
    run_id: str,
    previous: Phase32ProviderUsageSummary,
) -> Phase32ProviderUsageSummary:
    """Project usage from the driver's durable receipt store when available."""

    store = getattr(driver, "provider_operations", None)
    summary = getattr(store, "usage_summary", None)
    if not callable(summary):
        return previous
    try:
        value = summary(run_id)
        return Phase32ProviderUsageSummary.model_validate(value)
    except Exception:
        # Usage is a read-model enhancement; a malformed sidecar must not
        # fabricate counts or block an otherwise valid graph transition.
        return previous


def _interrupt_payload(output: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    interrupts = output.get("__interrupt__") or ()
    if not interrupts:
        return False, None
    value = getattr(interrupts[0], "value", interrupts[0])
    if not isinstance(value, dict):
        raise Phase32ExecutionError("Phase 32 graph interrupt must be an object")
    return True, dict(value)


async def _checkpoint_id(graph: Any, config: dict[str, Any]) -> str:
    try:
        snapshot = await graph.aget_state(config, subgraphs=True)
        value = snapshot.config.get("configurable", {}).get("checkpoint_id", "")
        return str(value or "")
    except Exception:
        # Checkpoint id is a projection hint; failure to read it must not invent
        # an identity or prevent the already validated state from committing.
        return ""


async def _interrupt_projection(
    graph: Any,
    config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Overlay the one active subgraph interrupt onto its parent state."""

    try:
        snapshot = await graph.aget_state(config, subgraphs=True)
        frontiers = _interrupted_frontiers(snapshot)
        if len(frontiers) != 1:
            raise ValueError(
                "A Phase 32 Run must expose exactly one active decision frontier"
            )
        values = dict(snapshot.values or {})
        values.update(dict(frontiers[0].values or {}))
        checkpoint_id = str(
            snapshot.config.get("configurable", {}).get("checkpoint_id", "") or ""
        )
        if not checkpoint_id:
            raise ValueError("An interrupted Phase 32 Run requires a durable checkpoint")
        return values, checkpoint_id
    except Exception as exc:
        raise Phase32ExecutionError(
            "Phase 32 interrupt frontier could not be projected from its checkpoint"
        ) from exc


async def _resume_by_interrupt_id(
    graph: Any,
    config: dict[str, Any],
    resume: dict[str, Any],
) -> dict[str, Any]:
    """Bind one business decision to the active LangGraph interrupt id.

    The route contract guarantees one active human decision frontier.  Older
    checkpoints (or test doubles) may not expose an interrupt id, so the
    original scalar-style payload remains the safe fallback in that case.
    """

    try:
        snapshot = await graph.aget_state(config, subgraphs=True)
        interrupt_ids = _active_interrupt_ids(snapshot)
        if len(interrupt_ids) == 1:
            return {interrupt_ids[0]: resume}
    except Exception:
        # Resume binding is a correctness enhancement; the graph still owns
        # validation and can reject a malformed/stale scalar payload.
        pass
    return resume


def _active_interrupt_ids(snapshot: Any) -> list[str]:
    """Collect checkpoint interrupt ids across nested route subgraphs."""

    found: list[str] = []
    for interrupt_item in getattr(snapshot, "interrupts", ()):
        value = getattr(interrupt_item, "id", "")
        if value:
            found.append(str(value))
    for task in getattr(snapshot, "tasks", ()):
        child = getattr(task, "state", None)
        if child is not None and hasattr(child, "tasks"):
            found.extend(_active_interrupt_ids(child))
        for interrupt_item in getattr(task, "interrupts", ()):
            value = getattr(interrupt_item, "id", "")
            if value:
                found.append(str(value))
    return list(dict.fromkeys(found))


def _interrupted_frontiers(snapshot: Any) -> list[Any]:
    frontiers: list[Any] = []
    for task in getattr(snapshot, "tasks", ()):
        child = getattr(task, "state", None)
        if child is None or not hasattr(child, "values"):
            continue
        nested = _interrupted_frontiers(child)
        if nested:
            frontiers.extend(nested)
        elif getattr(child, "interrupts", ()) or getattr(task, "interrupts", ()):
            frontiers.append(child)
    if frontiers:
        return frontiers
    return [snapshot] if getattr(snapshot, "interrupts", ()) else []


def _validate_interrupt_projection(
    state: RouteRunStateSnapshot,
    decision: dict[str, Any] | None,
) -> None:
    if decision is None:
        raise Phase32ExecutionError("Interrupted Phase 32 state has no decision payload")
    stage_id = str(decision.get("stage_id") or "")
    if state.active_stage_id != stage_id:
        raise Phase32ExecutionError(
            "Phase 32 decision stage does not match its checkpoint frontier"
        )
    if int(decision.get("domain_revision", -1)) != state.domain_revision:
        raise Phase32ExecutionError(
            "Phase 32 decision revision does not match its checkpoint frontier"
        )
    decision_kind = str(decision.get("type") or "route_stage_decision")
    artifact_ref = str(decision.get("artifact_ref") or "")
    if decision_kind == "writeback_recovery":
        if (
            not artifact_ref
            or not str(decision.get("writeback_receipt_ref") or "")
            or not state.candidate_artifact_refs.get(stage_id)
        ):
            raise Phase32ExecutionError(
                "Phase 32 writeback recovery authority is incomplete"
            )
        if str(decision.get("unit_ref") or "") != state.active_unit_ref:
            raise Phase32ExecutionError(
                "Phase 32 writeback recovery unit does not match its checkpoint frontier"
            )
    elif decision_kind != "route_stage_decision":
        raise Phase32ExecutionError("Phase 32 decision kind is not supported")
    elif artifact_ref and state.candidate_artifact_refs.get(stage_id) != artifact_ref:
        raise Phase32ExecutionError(
            "Phase 32 decision candidate does not match its checkpoint frontier"
        )
    if state.stage_status.get(stage_id) != "awaiting_decision":
        raise Phase32ExecutionError(
            "Phase 32 decision stage is not awaiting a decision"
        )


async def _failure_frontier(
    graph: Any,
    config: dict[str, Any],
    definition: GraphRunDefinition,
) -> Phase32FailureFrontier | None:
    """Recover the deepest failed subgraph state without re-running a node."""

    try:
        root = await graph.aget_state(config, subgraphs=True)
        snapshot, failed_node = _deepest_failed_snapshot(root)
        state = restore_route_run_state(definition, dict(snapshot.values))
        checkpoint_id = str(
            root.config.get("configurable", {}).get("checkpoint_id", "") or ""
        )
    except Exception:
        return None
    node_id = (
        f"{state.active_stage_id}.{failed_node}"
        if failed_node and failed_node != state.active_stage_id
        else f"{state.active_stage_id}.failure"
    )
    return Phase32FailureFrontier(
        state=state,
        checkpoint_id=checkpoint_id,
        node_id=node_id,
    )


def _deepest_failed_snapshot(snapshot: Any) -> tuple[Any, str]:
    for task in getattr(snapshot, "tasks", ()):
        if not getattr(task, "error", None):
            continue
        child = getattr(task, "state", None)
        if hasattr(child, "values"):
            nested, nested_node = _deepest_failed_snapshot(child)
            return nested, nested_node or str(getattr(task, "name", ""))
        return snapshot, str(getattr(task, "name", ""))
    return snapshot, ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32ExecutionError",
    "Phase32FailureFrontier",
    "Phase32GraphExecutionService",
    "Phase32StepResult",
    "project_phase32_read_model",
]
