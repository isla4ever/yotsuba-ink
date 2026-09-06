"""Dormant event sink from the shared Phase 32 Graph into its Repository."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from novel_workflow.runtime.graph.route_run_state import RouteRunStateSnapshot
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_event import (
    RouteRunEventEnvelope,
    create_route_run_event,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_compiler import CompiledRouteStage


_GRAPH_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "stage.started",
        "candidate.created",
        "decision.required",
        "decision.resolved",
        "artifact.committed",
        "evidence.completed",
        "evidence.recovery_required",
        "writeback.queued",
        "writeback.committed",
        "writeback.failed",
        "image.deferred",
        "export.ready",
    }
)

_FINAL_TERMINAL_EVENT_TYPES: frozenset[str] = frozenset(
    {"image.deferred", "export.ready"}
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class Phase32RepositoryEventSink:
    """Persist Graph domain events without owning orchestration or Provider calls."""

    runs: Phase32RunRepository
    clock: Callable[[], str] = _now

    def __call__(
        self,
        definition: GraphRunDefinition,
        event_type: str,
        stage: CompiledRouteStage,
        state: RouteRunStateSnapshot,
        payload: dict[str, Any],
    ) -> RouteRunEventEnvelope:
        if event_type not in _GRAPH_EVENT_TYPES:
            raise ValueError(f"Unsupported Phase 32 Graph event type: {event_type}")
        history = self.runs.events(definition.run_id)
        unit_ref = str(payload.get("unit_ref") or state.active_unit_ref or "")
        node_id = str(payload.get("node_id") or "")
        existing = next(
            (
                event
                for event in reversed(history)
                if event.type == event_type
                and event.stage_id == stage.stage_id
                and event.unit_ref == unit_ref
                and event.node_id == node_id
                and event.payload == payload
            ),
            None,
        )
        if existing is not None:
            return existing
        if event_type in _FINAL_TERMINAL_EVENT_TYPES:
            terminal = next(
                (
                    event
                    for event in history
                    if event.type in _FINAL_TERMINAL_EVENT_TYPES
                ),
                None,
            )
            if terminal is not None:
                raise ValueError(
                    "Phase 32 Run already has a different final terminal event: "
                    f"{terminal.type}"
                )
        sequence = len(history) + 1
        event = create_route_run_event(
            definition,
            event_id=f"{definition.run_id}:graph:{sequence}",
            sequence=sequence,
            occurred_at=self.clock(),
            type=event_type,  # type: ignore[arg-type]
            stage_id=stage.stage_id,
            unit_ref=unit_ref,
            artifact_kind=payload.get("artifact_kind"),
            node_id=node_id,
            status=state.status,
            payload=dict(payload),
        )
        return self.runs.append_event(event)


__all__ = ["Phase32RepositoryEventSink"]
