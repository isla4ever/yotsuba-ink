"""Checkpoint-authoritative failure projection for Phase 32 execution."""

from __future__ import annotations

from datetime import datetime, timezone

from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32FailureFrontier,
    project_phase32_read_model,
)
from novel_workflow.providers.usage import Phase32ProviderUsageSummary
from novel_workflow.runtime.graph.route_graph import RouteGraphDriver
from novel_workflow.runtime.graph.route_run_state import (
    RouteGraphFailure,
    RouteRunStateSnapshot,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_event import create_route_run_event
from novel_workflow.storage.route_run_read_model import RunFailureProjection


def project_phase32_execution_failure(
    repository: Phase32RunRepository,
    current: Phase32RunRecord,
    driver: RouteGraphDriver,
    exc: Exception,
    *,
    consumed_decision: dict[str, object] | None = None,
) -> None:
    """Project one graph failure from its deepest durable checkpoint frontier."""

    frontier = _exception_frontier(exc)
    state = frontier.state if frontier is not None else current.state
    code, stage_id, retryable, message = _failure_context(
        exc,
        fallback_stage_id=state.active_stage_id,
    )
    failure_node_id = (
        frontier.node_id if frontier is not None else f"{stage_id}.failure"
    )
    if not retryable:
        stage_status = dict(state.stage_status)
        stage_status[stage_id] = "failed"
        redraft_count = state.pending_decision_redraft_count
        decision_action = state.pending_decision_action
        if _consumed_regeneration(current, stage_id, consumed_decision):
            decision_action = "regenerate"
            redraft_count = max(
                redraft_count,
                _consumed_redraft_count(current, consumed_decision),
            )
        state = state.model_copy(
            update={
                "status": "failed",
                "stage_status": stage_status,
                "pending_decision_action": decision_action,
                "pending_decision_redraft_count": redraft_count,
                "failure": RouteGraphFailure(
                    node_id=failure_node_id,
                    code=code,
                    retryable=False,
                    message=message,
                ),
            }
        ).validate_for_definition(current.definition)
    usage = _driver_usage(
        driver,
        current.definition.run_id,
        current.read_model.provider_usage,
    )
    failure = RunFailureProjection(
        code=code,
        stage_id=stage_id,
        unit_ref=state.active_unit_ref,
        retryable=retryable,
        message=message,
    )
    checkpoint_id = (
        frontier.checkpoint_id
        if frontier is not None
        else current.read_model.checkpoint_id
    )
    read_model = project_phase32_read_model(
        current.read_model,
        current.definition,
        state,
        decision=None,
        checkpoint_id=checkpoint_id,
        provider_usage=usage,
    )
    if _retain_pending_decision(current, state, retryable=retryable):
        read_model = read_model.model_copy(
            update={"pending_decisions": current.read_model.pending_decisions}
        )
    read_model = read_model.model_copy(
        update={"failure": failure, "updated_at": _now()}
    ).validate_for_definition(current.definition)
    event_type = "unit.failed" if state.active_unit_ref else "stage.failed"
    sequence = len(repository.events(current.definition.run_id)) + 1
    failure_event = create_route_run_event(
        current.definition,
        event_id=f"{current.definition.run_id}:failure:{sequence}",
        sequence=sequence,
        occurred_at=_now(),
        type=event_type,  # type: ignore[arg-type]
        stage_id=stage_id,
        unit_ref=state.active_unit_ref,
        node_id=failure_node_id,
        status=state.status,
        payload={
            "code": code,
            "retryable": retryable,
            "message": message,
        },
    )
    try:
        repository.commit_projection_with_event(
            current.definition.run_id,
            state=state,
            read_model=read_model,
            event=failure_event,
        )
    except Exception:
        # Preserve the execution error; a projection failure must not mask the
        # Provider or graph root cause.
        return


def _exception_chain(exc: Exception) -> tuple[Exception, ...]:
    chain: list[Exception] = []
    current: Exception | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__
    return tuple(chain)


def _exception_frontier(exc: Exception) -> Phase32FailureFrontier | None:
    for error in _exception_chain(exc):
        frontier = getattr(error, "frontier", None)
        if isinstance(frontier, Phase32FailureFrontier):
            return frontier
    return None


def _failure_context(
    exc: Exception,
    *,
    fallback_stage_id: str,
) -> tuple[str, str, bool, str]:
    chain = _exception_chain(exc)
    semantic = next(
        (
            error
            for error in chain
            if str(getattr(error, "code", ""))
            in {"provider_transport_failed", "provider_contract_failed"}
        ),
        None,
    )
    root = chain[-1]
    if semantic is not None:
        code = str(getattr(semantic, "code"))
        retryable = bool(
            getattr(semantic, "retryable", code == "provider_transport_failed")
        )
        stage_id = str(getattr(semantic, "stage_id", "") or fallback_stage_id)
        message_source = root if retryable else semantic
        message = str(message_source)[:2_000] or "Phase 32 execution failed"
        return code, stage_id, retryable, message
    code, retryable = _failure_code(root)
    return (
        code,
        fallback_stage_id,
        retryable,
        str(root)[:2_000] or "Phase 32 execution failed",
    )


def _failure_code(exc: Exception) -> tuple[str, bool]:
    message = str(exc).lower()
    if (
        isinstance(exc, (TimeoutError, ConnectionError, OSError))
        or "transport failed" in message
        or "provider operation is already running" in message
    ):
        return "provider_transport_failed", True
    if "retry limit" in message or "contract" in message or "artifact payload" in message:
        return "provider_contract_failed", False
    code = str(getattr(exc, "code", "phase32_execution_failed"))
    return code, False


def _retain_pending_decision(
    current: Phase32RunRecord,
    frontier_state: RouteRunStateSnapshot,
    *,
    retryable: bool,
) -> bool:
    return bool(
        retryable
        and current.read_model.pending_decisions
        and frontier_state.domain_revision == current.state.domain_revision
        and frontier_state.active_stage_id == current.state.active_stage_id
    )


def _consumed_regeneration(
    current: Phase32RunRecord,
    stage_id: str,
    consumed_decision: dict[str, object] | None,
) -> bool:
    if not consumed_decision or consumed_decision.get("action") != "regenerate":
        return False
    decision_id = str(consumed_decision.get("decision_id") or "")
    return any(
        item.decision_id == decision_id and item.stage_id == stage_id
        for item in current.read_model.pending_decisions
    )


def _consumed_redraft_count(
    current: Phase32RunRecord,
    consumed_decision: dict[str, object] | None,
) -> int:
    decision_id = str((consumed_decision or {}).get("decision_id") or "")
    active = next(
        (
            item
            for item in current.read_model.pending_decisions
            if item.decision_id == decision_id
        ),
        None,
    )
    return int(active.redraft_used or 0) + 1 if active is not None else 1


def _driver_usage(
    driver: RouteGraphDriver,
    run_id: str,
    previous: Phase32ProviderUsageSummary,
) -> Phase32ProviderUsageSummary:
    store = getattr(driver, "provider_operations", None)
    summary = getattr(store, "usage_summary", None)
    if not callable(summary):
        return previous
    try:
        return Phase32ProviderUsageSummary.model_validate(summary(run_id))
    except Exception:
        return previous


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["project_phase32_execution_failure"]
