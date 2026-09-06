"""Route-aware event envelope for the Phase 32 Run event stream."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


RouteRunEventType = Literal[
    "stage.started",
    "candidate.created",
    "decision.required",
    "decision.resolved",
    "artifact.committed",
    "stage.failed",
    "unit.failed",
    "review.completed",
    "review.unavailable",
    "evidence.completed",
    "evidence.recovery_required",
    "writeback.queued",
    "writeback.committed",
    "writeback.failed",
    "checkpoint.saved",
    "run.branched",
    "image.deferred",
    "export.ready",
]


class RouteRunEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_id: str = Field(min_length=1, max_length=240)
    sequence: int = Field(ge=1)
    occurred_at: str = Field(min_length=1, max_length=80)
    run_id: str
    thread_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    route_manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    type: RouteRunEventType
    stage_id: str = ""
    unit_ref: str = Field(default="", max_length=500)
    artifact_kind: ArtifactKind | None = None
    node_id: str = Field(default="", max_length=240)
    status: str = Field(default="", max_length=120)
    payload: dict[str, Any] | None = None
    payload_ref: str = Field(default="", max_length=500)
    checkpoint_id: str = Field(default="", max_length=240)

    @model_validator(mode="after")
    def validate_event_shape(self) -> "RouteRunEventEnvelope":
        if (self.unit_ref or self.artifact_kind is not None) and not self.stage_id:
            raise ValueError("Unit and Artifact event identity requires a stage")
        if self.type == "artifact.committed" and self.artifact_kind is None:
            raise ValueError("Artifact commit event requires an Artifact kind")
        if self.type in {
            "stage.started",
            "candidate.created",
            "decision.required",
            "decision.resolved",
            "artifact.committed",
            "stage.failed",
            "unit.failed",
            "review.completed",
            "review.unavailable",
        } and not self.stage_id:
            raise ValueError(f"{self.type} event requires a stage")
        if self.type == "unit.failed" and not self.unit_ref:
            raise ValueError("Unit failure event requires a unit ref")
        return self

    def validate_for_definition(
        self,
        definition: GraphRunDefinition,
    ) -> "RouteRunEventEnvelope":
        definition.validate_projection_identity(
            run_id=self.run_id,
            project_id=definition.project_id,
            creation_route_id=self.creation_route_id,
            route_revision=self.route_revision,
            route_manifest_digest=self.route_manifest_digest,
            definition_digest=self.definition_digest,
        )
        if self.thread_id != self.run_id:
            raise ValueError("Event thread identity must equal its Run identity")
        if self.stage_id:
            stage = definition.stage(self.stage_id)
            if self.artifact_kind is not None and self.artifact_kind != stage.artifact_kind:
                raise ValueError("Event Artifact kind does not match its route stage")
            if self.unit_ref and stage.unitization not in {
                "bounded_units",
                "sequential_units",
            }:
                raise ValueError("Event unit ref requires a unitized route stage")
        if self.type == "export.ready" and self.stage_id != "export":
            raise ValueError("Export ready event must belong to the Export stage")
        return self


def create_route_run_event(
    definition: GraphRunDefinition,
    *,
    event_id: str,
    sequence: int,
    occurred_at: str,
    type: RouteRunEventType,
    stage_id: str = "",
    unit_ref: str = "",
    artifact_kind: ArtifactKind | None = None,
    node_id: str = "",
    status: str = "",
    payload: dict[str, Any] | None = None,
    payload_ref: str = "",
    checkpoint_id: str = "",
) -> RouteRunEventEnvelope:
    return RouteRunEventEnvelope(
        event_id=event_id,
        sequence=sequence,
        occurred_at=occurred_at,
        run_id=definition.run_id,
        thread_id=definition.run_id,
        creation_route_id=definition.creation_route_id,
        route_revision=definition.route_revision,
        route_manifest_digest=definition.route_contract.route_manifest_digest,
        definition_digest=definition.definition_digest,
        type=type,
        stage_id=stage_id,
        unit_ref=unit_ref,
        artifact_kind=artifact_kind,
        node_id=node_id,
        status=status,
        payload=payload,
        payload_ref=payload_ref,
        checkpoint_id=checkpoint_id,
    ).validate_for_definition(definition)


def restore_route_run_event(
    definition: GraphRunDefinition,
    payload: dict[str, Any],
) -> RouteRunEventEnvelope:
    return RouteRunEventEnvelope.model_validate(payload).validate_for_definition(definition)


__all__ = [
    "RouteRunEventEnvelope",
    "RouteRunEventType",
    "create_route_run_event",
    "restore_route_run_event",
]
