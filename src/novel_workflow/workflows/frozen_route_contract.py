from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_compiler import (
    CompiledRouteManifest,
    PHASE32_ARCHITECTURE_VERSION,
)
from novel_workflow.workflows.route_specs import CreationRouteId


class FrozenRouteContract(BaseModel):
    """The immutable route and review authority embedded into a future Run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    architecture_version: Literal["phase32-routes-v1"] = PHASE32_ARCHITECTURE_VERSION
    creation_route_id: CreationRouteId
    route_revision: str
    route_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    route_manifest: CompiledRouteManifest
    route_manifest_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_policy: ReviewPolicy
    review_policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_frozen_authority(self) -> "FrozenRouteContract":
        manifest = self.route_manifest
        if (
            self.creation_route_id != manifest.route_id
            or self.route_revision != manifest.route_revision
            or self.route_digest != manifest.route_digest
        ):
            raise ValueError("Frozen route identity does not match its compiled manifest")
        if self.route_manifest_digest != canonical_digest(
            manifest.model_dump(mode="json")
        ):
            raise ValueError("Frozen route manifest digest does not match its payload")
        if self.review_policy_digest != canonical_digest(
            self.review_policy.model_dump(mode="json")
        ):
            raise ValueError("Frozen ReviewPolicy digest does not match its payload")
        validate_review_policy_for_manifest(self.review_policy, manifest)
        if self.contract_digest != canonical_digest(
            self.model_dump(mode="json", exclude={"contract_digest"})
        ):
            raise ValueError("Frozen route contract digest does not match its payload")
        return self

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.route_manifest.stages)

    @property
    def provider_stage_ids(self) -> tuple[str, ...]:
        return tuple(
            stage.stage_id
            for stage in self.route_manifest.stages
            if stage.provider_task_kind is not None
        )

    def require_stage(self, stage_id: str) -> None:
        if stage_id not in self.stage_ids:
            raise ValueError(
                f"Stage {stage_id} is not part of route {self.creation_route_id}"
            )


def freeze_route_contract(
    manifest: CompiledRouteManifest,
    review_policy: ReviewPolicy,
) -> FrozenRouteContract:
    validate_review_policy_for_manifest(review_policy, manifest)
    payload = {
        "architecture_version": PHASE32_ARCHITECTURE_VERSION,
        "creation_route_id": manifest.route_id,
        "route_revision": manifest.route_revision,
        "route_digest": manifest.route_digest,
        "route_manifest": manifest.model_dump(mode="json"),
        "route_manifest_digest": canonical_digest(manifest.model_dump(mode="json")),
        "review_policy": review_policy.model_dump(mode="json"),
        "review_policy_digest": canonical_digest(review_policy.model_dump(mode="json")),
    }
    payload["contract_digest"] = canonical_digest(payload)
    return FrozenRouteContract.model_validate(payload)


def validate_review_policy_for_manifest(
    policy: ReviewPolicy,
    manifest: CompiledRouteManifest,
) -> None:
    if policy.route_id != manifest.route_id:
        raise ValueError("ReviewPolicy belongs to a different creation route")
    stages = {stage.stage_id: stage for stage in manifest.stages}
    referenced = (
        set(policy.auto_continue_stages)
        | set(policy.mandatory_decision_stages)
        | set(policy.directed_redraft_limit_by_stage)
    )
    unknown = referenced - set(stages)
    if unknown:
        raise ValueError(
            "ReviewPolicy references stages outside the compiled route: "
            + ", ".join(sorted(unknown))
        )
    automatic_without_provider = {
        stage_id
        for stage_id in policy.auto_continue_stages
        if stages[stage_id].provider_task_kind is None
    }
    if automatic_without_provider:
        raise ValueError(
            "Deterministic stages cannot be configured as automatic generation: "
            + ", ".join(sorted(automatic_without_provider))
        )
    redraft_without_provider = {
        stage_id
        for stage_id in policy.directed_redraft_limit_by_stage
        if stages[stage_id].provider_task_kind is None
    }
    if redraft_without_provider:
        raise ValueError(
            "Directed redraft requires a Provider stage: "
            + ", ".join(sorted(redraft_without_provider))
        )


def canonical_digest(payload: Any) -> str:
    try:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Frozen route payload must be canonical JSON") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "FrozenRouteContract",
    "canonical_digest",
    "freeze_route_contract",
    "validate_review_policy_for_manifest",
]
