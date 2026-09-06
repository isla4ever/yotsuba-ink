"""Immutable contracts for formal Phase 32 planning Artifact amendments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


AmendmentApplyScope = Literal["affected_only", "restart_from_stage"]


class AmendmentImpactTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    artifact_kind: ArtifactKind
    artifact_ref: str = Field(default="", max_length=500)
    unit_ref: str = Field(default="", max_length=500)
    reason: str = Field(min_length=1, max_length=240)


class AmendmentBlockedReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    reference: str = Field(min_length=1, max_length=240)
    referenced_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    referenced_artifact_ref: str = Field(min_length=1, max_length=500)
    unit_ref: str = Field(default="", max_length=500)


class ArtifactImpactAnalysis(BaseModel):
    """Deterministic impact projection derived from current Run authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    impact_id: str = Field(pattern=r"^p32-impact-[a-f0-9]{32}$")
    amendment_id: str = Field(pattern=r"^p32-amendment-[a-f0-9]{32}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    creation_route_id: CreationRouteId
    route_revision: str = Field(min_length=1, max_length=80)
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    source_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    proposed_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_domain_revision: int = Field(ge=0)
    preserved: tuple[AmendmentImpactTarget, ...] = ()
    stale: tuple[AmendmentImpactTarget, ...] = ()
    historical_frozen: tuple[AmendmentImpactTarget, ...] = ()
    blocked_references: tuple[AmendmentBlockedReference, ...] = ()
    affected_only_scope: tuple[str, ...]
    restart_from_stage_scope: tuple[str, ...]
    impact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_impact(self) -> "ArtifactImpactAnalysis":
        if self.source_stage_id in self.affected_only_scope:
            raise ValueError("Affected-only scope must begin after the amended source stage")
        if self.source_stage_id in self.restart_from_stage_scope:
            raise ValueError("Restart scope must begin after the amended source stage")
        for scope in (self.affected_only_scope, self.restart_from_stage_scope):
            if len(scope) != len(set(scope)):
                raise ValueError("Amendment recompute scope cannot contain duplicates")
        if not set(self.affected_only_scope).issubset(self.restart_from_stage_scope):
            raise ValueError("Affected-only scope must be contained by restart scope")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"impact_id", "impact_digest"})
        )
        if self.impact_digest != expected:
            raise ValueError("ImpactAnalysis digest does not match its payload")
        if self.impact_id != f"p32-impact-{expected[:32]}":
            raise ValueError("ImpactAnalysis id does not match its payload")
        return self


class Phase32ArtifactAmendment(BaseModel):
    """One source-bound proposed replacement for a committed planning Artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    amendment_id: str = Field(pattern=r"^p32-amendment-[a-f0-9]{32}$")
    command_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    creation_route_id: CreationRouteId
    route_revision: str = Field(min_length=1, max_length=80)
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    artifact_kind: ArtifactKind
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    source_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_domain_revision: int = Field(ge=0)
    proposed_payload: dict[str, Any]
    proposed_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    impact_id: str = Field(pattern=r"^p32-impact-[a-f0-9]{32}$")
    author_note: str = Field(default="", max_length=4_000)
    created_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_amendment(self) -> "Phase32ArtifactAmendment":
        if self.proposed_payload_digest != canonical_digest(self.proposed_payload):
            raise ValueError("Amendment proposed payload digest does not match its payload")
        identity = {
            "run_id": self.run_id,
            "creation_route_id": self.creation_route_id,
            "route_revision": self.route_revision,
            "definition_digest": self.definition_digest,
            "source_stage_id": self.source_stage_id,
            "source_artifact_ref": self.source_artifact_ref,
            "source_payload_digest": self.source_payload_digest,
            "source_domain_revision": self.source_domain_revision,
            "proposed_payload_digest": self.proposed_payload_digest,
            "author_note": self.author_note,
        }
        if self.command_digest != canonical_digest(identity):
            raise ValueError("Amendment command digest does not match its source command")
        if self.amendment_id != f"p32-amendment-{self.command_digest[:32]}":
            raise ValueError("Amendment id does not match its source command")
        return self


class Phase32AmendmentApplyPlan(BaseModel):
    """Immutable apply intent persisted before Artifact/projection mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    plan_id: str = Field(pattern=r"^p32-amendment-plan-[a-f0-9]{32}$")
    command_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    amendment_id: str = Field(pattern=r"^p32-amendment-[a-f0-9]{32}$")
    impact_id: str = Field(pattern=r"^p32-impact-[a-f0-9]{32}$")
    scope: AmendmentApplyScope
    source_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    expected_committed_artifact_ref: str = Field(min_length=1, max_length=500)
    source_domain_revision: int = Field(ge=0)
    stale_stage_ids: tuple[str, ...]
    historical_frozen_stage_ids: tuple[str, ...]
    active_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    created_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_plan(self) -> "Phase32AmendmentApplyPlan":
        command = {
            "run_id": self.run_id,
            "amendment_id": self.amendment_id,
            "impact_id": self.impact_id,
            "scope": self.scope,
            "source_stage_id": self.source_stage_id,
            "source_artifact_ref": self.source_artifact_ref,
            "expected_committed_artifact_ref": self.expected_committed_artifact_ref,
            "source_domain_revision": self.source_domain_revision,
            "stale_stage_ids": self.stale_stage_ids,
            "historical_frozen_stage_ids": self.historical_frozen_stage_ids,
            "active_stage_id": self.active_stage_id,
        }
        if self.command_digest != canonical_digest(command):
            raise ValueError("Amendment apply plan digest does not match its command")
        if self.plan_id != f"p32-amendment-plan-{self.command_digest[:32]}":
            raise ValueError("Amendment apply plan id does not match its command")
        if len(self.stale_stage_ids) != len(set(self.stale_stage_ids)):
            raise ValueError("Amendment apply plan stale stages must be unique")
        return self


class Phase32AmendmentApplyReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    receipt_id: str = Field(pattern=r"^p32-amendment-receipt-[a-f0-9]{32}$")
    plan_id: str = Field(pattern=r"^p32-amendment-plan-[a-f0-9]{32}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    amendment_id: str = Field(pattern=r"^p32-amendment-[a-f0-9]{32}$")
    scope: AmendmentApplyScope
    previous_artifact_ref: str = Field(min_length=1, max_length=500)
    committed_artifact_ref: str = Field(min_length=1, max_length=500)
    domain_revision_before: int = Field(ge=0)
    domain_revision_after: int = Field(ge=1)
    event_id: str = Field(min_length=1, max_length=240)
    applied_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_receipt(self) -> "Phase32AmendmentApplyReceipt":
        if self.domain_revision_after != self.domain_revision_before + 1:
            raise ValueError("Amendment apply must advance domain revision exactly once")
        expected = canonical_digest(
            self.model_dump(
                mode="json",
                exclude={"architecture_version", "receipt_id", "applied_at"},
            )
        )
        if self.receipt_id != f"p32-amendment-receipt-{expected[:32]}":
            raise ValueError("Amendment apply receipt id does not match its result")
        return self


__all__ = [
    "AmendmentApplyScope",
    "AmendmentBlockedReference",
    "AmendmentImpactTarget",
    "ArtifactImpactAnalysis",
    "Phase32AmendmentApplyPlan",
    "Phase32AmendmentApplyReceipt",
    "Phase32ArtifactAmendment",
]
