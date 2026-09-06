"""Paginated, route-aware event projection for Phase 32 Runs."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_event import RouteRunEventEnvelope
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_specs import CreationRouteId


class Phase32EventPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    route_manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    after: int = Field(ge=0)
    next_cursor: int = Field(ge=0)
    has_more: bool
    terminal: bool
    events: tuple[RouteRunEventEnvelope, ...]

    @property
    def event_sequences(self) -> tuple[int, ...]:
        return tuple(event.sequence for event in self.events)

    def validate_for_definition(
        self,
        definition: GraphRunDefinition,
    ) -> "Phase32EventPage":
        if self.run_id != definition.run_id:
            raise ValueError("Event page Run identity does not match its definition")
        if (
            self.creation_route_id != definition.creation_route_id
            or self.route_revision != definition.route_revision
            or self.route_manifest_digest
            != definition.route_contract.route_manifest_digest
            or self.definition_digest != definition.definition_digest
        ):
            raise ValueError("Event page route identity does not match its definition")
        sequences = self.event_sequences
        if sequences and sequences != tuple(
            range(self.after + 1, self.after + len(sequences) + 1)
        ):
            raise ValueError("Event page sequences must be contiguous after the cursor")
        if self.next_cursor < self.after:
            raise ValueError("Event page cursor cannot move backwards")
        return self


@dataclass(frozen=True, slots=True)
class Phase32EventProjection:
    """Read-only event page builder over the Phase 32 repository."""

    runs: Phase32RunRepository

    def page(
        self,
        run_id: str,
        *,
        after: int = 0,
        limit: int = 100,
    ) -> Phase32EventPage:
        if after < 0:
            raise ValueError("Event cursor cannot be negative")
        if not 1 <= limit <= 500:
            raise ValueError("Event page limit must be between 1 and 500")
        definition = self.runs.definition(run_id)
        history = self.runs.events(run_id)
        events = [event for event in history if event.sequence > after]
        page_events = tuple(events[:limit])
        next_cursor = page_events[-1].sequence if page_events else after
        terminal = _batch_reaches_terminal(page_events)
        if not page_events and history:
            terminal = _batch_reaches_terminal(tuple(history))
        return Phase32EventPage(
            run_id=definition.run_id,
            creation_route_id=definition.creation_route_id,
            route_revision=definition.route_revision,
            route_manifest_digest=definition.route_contract.route_manifest_digest,
            definition_digest=definition.definition_digest,
            after=after,
            next_cursor=next_cursor,
            has_more=len(events) > len(page_events),
            terminal=terminal,
            events=page_events,
        ).validate_for_definition(definition)


def _batch_reaches_terminal(events: tuple[RouteRunEventEnvelope, ...]) -> bool:
    terminal = False
    for event in events:
        if event.type in {
            "decision.required",
            "stage.failed",
            "unit.failed",
            "evidence.recovery_required",
            "writeback.failed",
            "image.deferred",
            "export.ready",
        }:
            terminal = True
        elif event.type in {"stage.started", "decision.resolved"}:
            terminal = False
    return terminal


__all__ = ["Phase32EventPage", "Phase32EventProjection"]
