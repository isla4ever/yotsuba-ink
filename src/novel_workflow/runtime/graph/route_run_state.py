"""Checkpoint-safe routing state for a Phase 32 creation route."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.graph_run_definition import (
    GraphRunDefinition,
    RunStatus,
    StageStatus,
)
from novel_workflow.workflows.route_specs import CreationRouteId


class RouteGraphFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    node_id: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=160)
    retryable: bool
    provider_code: str = Field(default="", max_length=160)
    evidence_ref: str = Field(default="", max_length=240)
    message: str = Field(default="", max_length=2_000)


class SequentialStageProgress(BaseModel):
    """Frozen unit order and accepted immutable versions for one sequential stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    ordered_unit_refs: tuple[str, ...] = Field(min_length=1, max_length=4_000)
    committed_artifact_refs: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_accepted_prefix(self) -> "SequentialStageProgress":
        if len(self.ordered_unit_refs) != len(set(self.ordered_unit_refs)):
            raise ValueError("Sequential stage unit refs must be unique")
        if any(not ref for ref in self.ordered_unit_refs):
            raise ValueError("Sequential stage unit refs cannot be empty")
        committed_refs = tuple(self.committed_artifact_refs)
        expected_prefix = self.ordered_unit_refs[: len(committed_refs)]
        if committed_refs != expected_prefix:
            raise ValueError("Sequential stage commits must form the frozen unit prefix")
        if any(not ref for ref in self.committed_artifact_refs.values()):
            raise ValueError("Sequential stage committed Artifact refs cannot be empty")
        return self

    @property
    def complete(self) -> bool:
        return len(self.committed_artifact_refs) == len(self.ordered_unit_refs)

    @property
    def next_unit_ref(self) -> str:
        return "" if self.complete else self.ordered_unit_refs[len(self.committed_artifact_refs)]

    def accept(self, unit_ref: str, artifact_ref: str) -> "SequentialStageProgress":
        if not unit_ref or unit_ref != self.next_unit_ref:
            raise ValueError("Sequential stage can only accept its next frozen unit")
        if not artifact_ref:
            raise ValueError("Sequential stage commit requires an Artifact ref")
        committed = dict(self.committed_artifact_refs)
        committed[unit_ref] = artifact_ref
        return self.model_copy(update={"committed_artifact_refs": committed})


class RouteRunStateSnapshot(BaseModel):
    """Only routing cursors and immutable references enter the checkpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    run_id: str
    project_id: str
    thread_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    route_manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: RunStatus
    active_stage_id: str
    active_unit_ref: str = ""
    stage_status: dict[str, StageStatus]
    artifact_refs: dict[str, str] = Field(default_factory=dict)
    candidate_artifact_refs: dict[str, str] = Field(default_factory=dict)
    stage_attempts: dict[str, int] = Field(default_factory=dict)
    stage_revision_directions: dict[str, str] = Field(default_factory=dict)
    unit_attempts: dict[str, int] = Field(default_factory=dict)
    sequential_stage_progress: dict[str, dict[str, Any]] = Field(default_factory=dict)
    context_manifest_ref: str = ""
    pending_operation_refs: tuple[str, ...] = ()
    review_operation_refs: tuple[str, ...] = ()
    active_amendment_id: str = Field(default="", max_length=240)
    stale_stage_ids: tuple[str, ...] = ()
    historical_frozen_stage_ids: tuple[str, ...] = ()
    # These fields are routing sidecars, not review content. They let a
    # checkpoint replay a bounded redraft without losing the new candidate.
    pending_decision_action: Literal["", "accept", "regenerate", "cancel"] = ""
    pending_decision_redraft_count: int = 0
    failure: RouteGraphFailure | None = None
    domain_revision: int = Field(default=0, ge=0)

    def validate_for_definition(
        self,
        definition: GraphRunDefinition,
    ) -> "RouteRunStateSnapshot":
        definition.validate_projection_identity(
            run_id=self.run_id,
            project_id=self.project_id,
            creation_route_id=self.creation_route_id,
            route_revision=self.route_revision,
            route_manifest_digest=self.route_manifest_digest,
            definition_digest=self.definition_digest,
        )
        if self.thread_id != self.run_id:
            raise ValueError("Graph thread identity must equal its Run identity")
        definition.stage(self.active_stage_id)
        definition.validate_stage_keys(
            list(self.stage_status), label="Stage status", require_all=True
        )
        for label, mapping in (
            ("Artifact refs", self.artifact_refs),
            ("Candidate Artifact refs", self.candidate_artifact_refs),
            ("Stage attempts", self.stage_attempts),
            ("Stage revision directions", self.stage_revision_directions),
        ):
            definition.validate_stage_keys(list(mapping), label=label, require_all=False)
        for label, mapping in (
            ("Artifact refs", self.artifact_refs),
            ("Candidate Artifact refs", self.candidate_artifact_refs),
        ):
            if any(not value.strip() for value in mapping.values()):
                raise ValueError(f"{label} cannot contain empty references")
        definition.validate_stage_keys(
            list(self.sequential_stage_progress),
            label="Sequential stage progress",
            require_all=False,
        )
        definition.validate_stage_keys(
            list(self.stale_stage_ids),
            label="Stale stages",
            require_all=False,
        )
        definition.validate_stage_keys(
            list(self.historical_frozen_stage_ids),
            label="Historical frozen stages",
            require_all=False,
        )
        if len(self.stale_stage_ids) != len(set(self.stale_stage_ids)):
            raise ValueError("Stale stage ids cannot contain duplicates")
        if len(self.historical_frozen_stage_ids) != len(
            set(self.historical_frozen_stage_ids)
        ):
            raise ValueError("Historical frozen stage ids cannot contain duplicates")
        if not set(self.historical_frozen_stage_ids).issubset(self.stale_stage_ids):
            raise ValueError("Historical frozen stages must also be stale")
        if self.stale_stage_ids and self.status != "needs_action":
            raise ValueError("Stale stages require needs_action Run status")
        if self.status == "needs_action" and (
            not self.active_amendment_id or not self.stale_stage_ids
        ):
            raise ValueError("needs_action Run requires an active amendment and stale stages")
        for stage_id in self.stale_stage_ids:
            if self.stage_status.get(stage_id) != "stale":
                raise ValueError("Stale routing sidecar must match stage status")
        for stage_id, payload in self.sequential_stage_progress.items():
            if definition.stage(stage_id).unitization != "sequential_units":
                raise ValueError("Sequential progress requires a sequential route stage")
            progress = SequentialStageProgress.model_validate(payload)
            if (
                self.active_stage_id == stage_id
                and self.active_unit_ref
                and self.active_unit_ref != progress.next_unit_ref
            ):
                raise ValueError("Active unit does not match the sequential stage cursor")
        if self.active_unit_ref and definition.stage(self.active_stage_id).unitization not in {
            "bounded_units",
            "sequential_units",
        }:
            raise ValueError("Active unit ref requires a unitized route stage")
        if any(attempt < 0 for attempt in self.stage_attempts.values()):
            raise ValueError("Stage attempts cannot be negative")
        if any(not direction.strip() for direction in self.stage_revision_directions.values()):
            raise ValueError("Stage revision directions cannot contain empty values")
        if any(attempt < 0 for attempt in self.unit_attempts.values()):
            raise ValueError("Unit attempts cannot be negative")
        if self.pending_decision_redraft_count < 0:
            raise ValueError("Pending decision redraft count cannot be negative")
        if any(not unit_ref.strip() for unit_ref in self.unit_attempts):
            raise ValueError("Unit attempts require non-empty unit refs")
        for label, refs in (
            ("Pending operation refs", self.pending_operation_refs),
            ("Review operation refs", self.review_operation_refs),
        ):
            if len(refs) != len(set(refs)):
                raise ValueError(f"{label} cannot contain duplicates")
            if any(not ref.strip() for ref in refs):
                raise ValueError(f"{label} cannot contain empty references")
        return self

    def sequential_progress(self, stage_id: str) -> SequentialStageProgress | None:
        payload = self.sequential_stage_progress.get(stage_id)
        return SequentialStageProgress.model_validate(payload) if payload else None


def initial_route_run_state(definition: GraphRunDefinition) -> RouteRunStateSnapshot:
    return RouteRunStateSnapshot(
        run_id=definition.run_id,
        project_id=definition.project_id,
        thread_id=definition.run_id,
        creation_route_id=definition.creation_route_id,
        route_revision=definition.route_revision,
        route_manifest_digest=definition.route_contract.route_manifest_digest,
        definition_digest=definition.definition_digest,
        status="created",
        active_stage_id=definition.route_contract.route_manifest.start_stage_id,
        stage_status=definition.initial_stage_status(),
    ).validate_for_definition(definition)


def restore_route_run_state(
    definition: GraphRunDefinition,
    payload: dict[str, Any],
) -> RouteRunStateSnapshot:
    return RouteRunStateSnapshot.model_validate(payload).validate_for_definition(definition)


__all__ = [
    "RouteGraphFailure",
    "RouteRunStateSnapshot",
    "SequentialStageProgress",
    "initial_route_run_state",
    "restore_route_run_state",
]
