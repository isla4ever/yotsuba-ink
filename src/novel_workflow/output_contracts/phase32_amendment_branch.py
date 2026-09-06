"""Immutable contracts for resolving an amendment through a successor Run."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32AmendmentBranchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    plan_id: str = Field(pattern=r"^p32-amendment-branch-plan-[a-f0-9]{32}$")
    command_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    target_run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    amendment_id: str = Field(pattern=r"^p32-amendment-[a-f0-9]{32}$")
    impact_id: str = Field(pattern=r"^p32-impact-[a-f0-9]{32}$")
    apply_receipt_id: str = Field(pattern=r"^p32-amendment-receipt-[a-f0-9]{32}$")
    source_definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_domain_revision: int = Field(ge=1)
    frontier_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    inherited_stage_ids: tuple[str, ...]
    inherited_artifact_refs: dict[str, str]
    target_created_at: str = Field(min_length=1, max_length=80)
    target_definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_plan(self) -> "Phase32AmendmentBranchPlan":
        if not self.inherited_stage_ids:
            raise ValueError("Amendment branch must inherit at least its amended planning source")
        if tuple(self.inherited_artifact_refs) != self.inherited_stage_ids:
            raise ValueError("Inherited Artifact refs must follow inherited stage order")
        if len(self.inherited_stage_ids) != len(set(self.inherited_stage_ids)):
            raise ValueError("Inherited amendment branch stages must be unique")
        if any(not ref for ref in self.inherited_artifact_refs.values()):
            raise ValueError("Inherited amendment branch Artifact refs cannot be empty")
        expected = canonical_digest(
            self.model_dump(mode="json", exclude={"architecture_version", "plan_id"})
        )
        if self.plan_id != f"p32-amendment-branch-plan-{expected[:32]}":
            raise ValueError("Amendment branch plan id does not match its payload")
        return self


class Phase32AmendmentBranchReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    receipt_id: str = Field(pattern=r"^p32-amendment-branch-receipt-[a-f0-9]{32}$")
    plan_id: str = Field(pattern=r"^p32-amendment-branch-plan-[a-f0-9]{32}$")
    source_run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    target_run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    amendment_id: str = Field(pattern=r"^p32-amendment-[a-f0-9]{32}$")
    apply_receipt_id: str = Field(pattern=r"^p32-amendment-receipt-[a-f0-9]{32}$")
    source_domain_revision: int = Field(ge=1)
    target_definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    frontier_stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    imported_artifact_refs: dict[str, str]
    source_event_id: str = Field(min_length=1, max_length=240)
    target_event_id: str = Field(min_length=1, max_length=240)
    branched_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_receipt(self) -> "Phase32AmendmentBranchReceipt":
        if not self.imported_artifact_refs:
            raise ValueError("Amendment branch receipt requires imported Artifact refs")
        expected = canonical_digest(
            self.model_dump(
                mode="json",
                exclude={"architecture_version", "receipt_id", "branched_at"},
            )
        )
        if self.receipt_id != f"p32-amendment-branch-receipt-{expected[:32]}":
            raise ValueError("Amendment branch receipt id does not match its result")
        return self


__all__ = [
    "Phase32AmendmentBranchPlan",
    "Phase32AmendmentBranchReceipt",
]
