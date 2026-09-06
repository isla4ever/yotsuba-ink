"""Rebuildable Phase 32 Run projection for API, monitor, and workbench readers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.providers.usage import Phase32ProviderUsageSummary
from novel_workflow.runtime.graph.route_run_state import SequentialStageProgress
from novel_workflow.workflows.graph_run_definition import (
    GraphRunDefinition,
    RunStatus,
    StageStatus,
)
from novel_workflow.workflows.route_compiler import CompiledRouteStage
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


class ReviewPolicySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    revision: str
    checkpoint_policy: str
    warning_policy: str
    auto_continue_stages: tuple[str, ...]
    mandatory_decision_stages: tuple[str, ...]


class ArtifactRefProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    artifact_kind: ArtifactKind
    artifact_ref: str = Field(min_length=1, max_length=500)


class PendingDecisionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    decision_id: str = Field(min_length=1, max_length=240)
    stage_id: str
    unit_ref: str = Field(default="", max_length=500)
    artifact_ref: str = Field(default="", max_length=500)
    kind: str = Field(min_length=1, max_length=120)
    domain_revision: int | None = Field(default=None, ge=0)
    allowed_actions: tuple[
        Literal["accept", "regenerate", "retry_writeback", "cancel"], ...
    ] = ()
    redraft_limit: int | None = Field(default=None, ge=0)
    redraft_used: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_decision_authority(self) -> "PendingDecisionProjection":
        if self.kind == "writeback_recovery":
            if self.domain_revision is None:
                raise ValueError("Writeback recovery requires a domain revision")
            if self.redraft_limit is not None or self.redraft_used is not None:
                raise ValueError("Writeback recovery cannot expose prose redraft usage")
            if set(self.allowed_actions) != {"retry_writeback", "cancel"}:
                raise ValueError("Writeback recovery exposes only retry and cancel")
            return self
        authority = (self.domain_revision, self.redraft_limit, self.redraft_used)
        if all(value is None for value in authority):
            if self.allowed_actions:
                raise ValueError("Historical decision projection cannot invent allowed actions")
            return self
        if any(value is None for value in authority) or not self.allowed_actions:
            raise ValueError("Pending decision authority must be projected as one complete contract")
        if self.redraft_used > self.redraft_limit:
            raise ValueError("Pending decision redraft usage exceeds its frozen limit")
        if len(self.allowed_actions) != len(set(self.allowed_actions)):
            raise ValueError("Pending decision actions must be unique")
        if "accept" not in self.allowed_actions or "cancel" not in self.allowed_actions:
            raise ValueError("Pending decision must expose accept and cancel actions")
        return self


class RunFailureProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=160)
    stage_id: str = ""
    unit_ref: str = Field(default="", max_length=500)
    retryable: bool = False
    message: str = Field(default="", max_length=2_000)


class RouteRunReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    thread_id: str
    creation_route_id: CreationRouteId
    route_revision: str
    route_manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    stage_manifest: tuple[CompiledRouteStage, ...]
    review_policy_summary: ReviewPolicySummary
    status: RunStatus
    active_stage_id: str
    active_unit_ref: str = ""
    stage_status: dict[str, StageStatus]
    artifact_refs: dict[str, ArtifactRefProjection] = Field(default_factory=dict)
    sequential_stage_progress: dict[str, SequentialStageProgress] = Field(
        default_factory=dict
    )
    pending_decisions: tuple[PendingDecisionProjection, ...] = ()
    active_amendment_id: str = Field(default="", max_length=240)
    stale_stage_ids: tuple[str, ...] = ()
    historical_frozen_stage_ids: tuple[str, ...] = ()
    provider_usage: Phase32ProviderUsageSummary = Field(
        default_factory=Phase32ProviderUsageSummary
    )
    failure: RunFailureProjection | None = None
    checkpoint_id: str = ""
    updated_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_internal_projection(self) -> "RouteRunReadModel":
        stage_ids = tuple(stage.stage_id for stage in self.stage_manifest)
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("Read model stage manifest contains duplicate stages")
        if tuple(stage.ordinal for stage in self.stage_manifest) != tuple(
            range(len(self.stage_manifest))
        ):
            raise ValueError("Read model stage manifest ordinals must be contiguous")
        if set(self.stage_status) != set(stage_ids):
            raise ValueError("Read model stage status must cover its stage manifest")
        stages = {stage.stage_id: stage for stage in self.stage_manifest}
        if self.active_stage_id not in stages:
            raise ValueError("Read model active stage is outside its stage manifest")
        if self.active_unit_ref and stages[self.active_stage_id].unitization not in {
            "bounded_units",
            "sequential_units",
        }:
            raise ValueError("Read model active unit requires a unitized stage")
        for stage_id, artifact in self.artifact_refs.items():
            stage = stages.get(stage_id)
            if stage is None:
                raise ValueError("Read model Artifact ref belongs to an unknown stage")
            if artifact.artifact_kind != stage.artifact_kind:
                raise ValueError("Read model Artifact kind does not match its stage")
        for stage_id in self.sequential_stage_progress:
            stage = stages.get(stage_id)
            if stage is None or stage.unitization != "sequential_units":
                raise ValueError(
                    "Read model sequential progress requires a sequential stage"
                )
        for label, stage_ids in (
            ("Stale stages", self.stale_stage_ids),
            ("Historical frozen stages", self.historical_frozen_stage_ids),
        ):
            unknown = set(stage_ids) - set(stages)
            if unknown:
                raise ValueError(f"{label} contain unknown route stages")
            if len(stage_ids) != len(set(stage_ids)):
                raise ValueError(f"{label} cannot contain duplicates")
        if not set(self.historical_frozen_stage_ids).issubset(self.stale_stage_ids):
            raise ValueError("Historical frozen stages must also be stale")
        if self.stale_stage_ids and self.status != "needs_action":
            raise ValueError("Stale read model stages require needs_action Run status")
        if self.status == "needs_action" and (
            not self.active_amendment_id or not self.stale_stage_ids
        ):
            raise ValueError("needs_action read model requires an active amendment and stale stages")
        for stage_id in self.stale_stage_ids:
            if self.stage_status.get(stage_id) != "stale":
                raise ValueError("Read model stale sidecar must match stage status")
        active_progress = self.sequential_stage_progress.get(self.active_stage_id)
        if (
            active_progress is not None
            and self.active_unit_ref
            and self.active_unit_ref != active_progress.next_unit_ref
        ):
            raise ValueError("Read model active unit does not match its sequential cursor")
        decision_ids = tuple(item.decision_id for item in self.pending_decisions)
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("Read model contains duplicate pending decisions")
        if self.status in {"failed", "cancelled", "completed", "image_deferred"} and (
            self.pending_decisions
        ):
            raise ValueError("Terminal read model cannot expose pending decisions")
        for decision in self.pending_decisions:
            stage = stages.get(decision.stage_id)
            if stage is None:
                raise ValueError("Pending decision belongs to an unknown stage")
            if decision.unit_ref and stage.unitization not in {
                "bounded_units",
                "sequential_units",
            }:
                raise ValueError("Pending decision unit requires a unitized stage")
        if self.failure:
            if self.failure.unit_ref and not self.failure.stage_id:
                raise ValueError("Run failure unit requires a stage")
            if self.failure.stage_id:
                stage = stages.get(self.failure.stage_id)
                if stage is None:
                    raise ValueError("Run failure belongs to an unknown stage")
                if self.failure.unit_ref and stage.unitization not in {
                    "bounded_units",
                    "sequential_units",
                }:
                    raise ValueError("Run failure unit requires a unitized stage")
        return self

    def validate_for_definition(
        self,
        definition: GraphRunDefinition,
    ) -> "RouteRunReadModel":
        definition.validate_projection_identity(
            run_id=self.run_id,
            project_id=self.project_id,
            creation_route_id=self.creation_route_id,
            route_revision=self.route_revision,
            route_manifest_digest=self.route_manifest_digest,
            definition_digest=self.definition_digest,
        )
        if self.thread_id != self.run_id:
            raise ValueError("Read model thread identity must equal its Run identity")
        if self.stage_manifest != definition.route_contract.route_manifest.stages:
            raise ValueError("Read model stage manifest does not match its Run definition")
        if self.review_policy_summary != review_policy_summary(definition):
            raise ValueError("Read model ReviewPolicy summary does not match its Run definition")
        return self


def review_policy_summary(definition: GraphRunDefinition) -> ReviewPolicySummary:
    policy = definition.route_contract.review_policy
    return ReviewPolicySummary(
        policy_id=policy.policy_id,
        revision=policy.revision,
        checkpoint_policy=policy.checkpoint_policy,
        warning_policy=policy.warning_policy,
        auto_continue_stages=policy.auto_continue_stages,
        mandatory_decision_stages=policy.mandatory_decision_stages,
    )


def initial_route_run_read_model(
    definition: GraphRunDefinition,
    *,
    updated_at: str,
) -> RouteRunReadModel:
    return RouteRunReadModel(
        run_id=definition.run_id,
        project_id=definition.project_id,
        thread_id=definition.run_id,
        creation_route_id=definition.creation_route_id,
        route_revision=definition.route_revision,
        route_manifest_digest=definition.route_contract.route_manifest_digest,
        definition_digest=definition.definition_digest,
        stage_manifest=definition.route_contract.route_manifest.stages,
        review_policy_summary=review_policy_summary(definition),
        status="created",
        active_stage_id=definition.route_contract.route_manifest.start_stage_id,
        stage_status=definition.initial_stage_status(),
        updated_at=updated_at,
    ).validate_for_definition(definition)


def restore_route_run_read_model(
    definition: GraphRunDefinition,
    payload: dict[str, Any],
) -> RouteRunReadModel:
    return RouteRunReadModel.model_validate(payload).validate_for_definition(definition)


__all__ = [
    "ArtifactRefProjection",
    "PendingDecisionProjection",
    "ReviewPolicySummary",
    "RouteRunReadModel",
    "RunFailureProjection",
    "initial_route_run_read_model",
    "restore_route_run_read_model",
    "review_policy_summary",
]
