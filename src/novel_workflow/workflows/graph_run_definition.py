"""Immutable Phase 32 Run authority built from one frozen creation route."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.workflows.frozen_route_contract import (
    FrozenRouteContract,
    canonical_digest,
)
from novel_workflow.workflows.route_compiler import (
    PHASE32_ARCHITECTURE_VERSION,
    CompiledRouteStage,
)
from novel_workflow.workflows.phase32_scale import (
    ScaleProfile,
    continuity_acceptance_scale_policy,
    release_smoke_scale_policy,
    scale_policy,
)


RunStatus = Literal[
    "created",
    "running",
    "awaiting_decision",
    "image_deferred",
    "needs_action",
    "completed",
    "failed",
    "cancelled",
]
StageStatus = Literal[
    "locked",
    "available",
    "running",
    "awaiting_decision",
    "stale",
    "completed",
    "failed",
]


class FrozenContractPayload(BaseModel):
    """Content-addressed snapshot for a contract owned by a later Wave."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    contract_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    contract_revision: str = Field(pattern=r"^r[1-9][0-9]*$")
    payload: dict[str, Any]
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_payload_digest(self) -> "FrozenContractPayload":
        if self.payload_digest != canonical_digest(self.payload):
            raise ValueError("Frozen contract payload digest does not match its payload")
        return self


class FrozenStageProviderBinding(BaseModel):
    """One explicit generation binding for one compiled Provider stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    binding: FrozenContractPayload


class GraphRunDefinition(BaseModel):
    """The complete immutable authority a Phase 32 graph may execute.

    This model intentionally has no production importer yet. Typed Phase 32
    ScaleProfile snapshots are validated when present; inputs and Provider
    payloads remain explicit content-addressed snapshots until later waves.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = PHASE32_ARCHITECTURE_VERSION
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
    workflow_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
    workflow_revision: str = Field(min_length=1, max_length=240)
    workflow_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    route_contract: FrozenRouteContract
    scale_profile: FrozenContractPayload
    inputs: FrozenContractPayload
    provider_bindings_by_stage: tuple[FrozenStageProviderBinding, ...]
    export_profile: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    created_at: str = Field(min_length=1, max_length=80)
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_definition_authority(self) -> "GraphRunDefinition":
        expected_provider_stages = self.route_contract.provider_stage_ids
        bound_provider_stages = tuple(
            binding.stage_id for binding in self.provider_bindings_by_stage
        )
        if bound_provider_stages != expected_provider_stages:
            raise ValueError(
                "Provider binding stages must exactly match the compiled route order"
            )
        stages = {
            stage.stage_id: stage
            for stage in self.route_contract.route_manifest.stages
        }
        for frozen_binding in self.provider_bindings_by_stage:
            binding = Phase32StageProviderBindingSnapshot.model_validate(
                frozen_binding.binding.payload
            )
            stage = stages[frozen_binding.stage_id]
            if (
                binding.creation_route_id != self.creation_route_id
                or binding.stage_id != frozen_binding.stage_id
                or binding.workflow_id != self.workflow_id
                or binding.task.provider_task_kind != stage.provider_task_kind
                or binding.task.artifact_kind != stage.artifact_kind
            ):
                raise ValueError(
                    "Provider binding identity must match its frozen Run stage"
                )
        if self.export_profile not in self.route_contract.route_manifest.export_profiles:
            raise ValueError("Export profile is not supported by the compiled route")
        _validate_typed_scale_profile(
            self.scale_profile,
            creation_route_id=self.creation_route_id,
        )
        if self.definition_digest != canonical_digest(
            self.model_dump(mode="json", exclude={"definition_digest"})
        ):
            raise ValueError("Graph Run definition digest does not match its payload")
        return self

    @property
    def creation_route_id(self) -> str:
        return self.route_contract.creation_route_id

    @property
    def route_revision(self) -> str:
        return self.route_contract.route_revision

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return self.route_contract.stage_ids

    def initial_stage_status(self) -> dict[str, StageStatus]:
        return {
            stage_id: "available" if index == 0 else "locked"
            for index, stage_id in enumerate(self.stage_ids)
        }

    def stage(self, stage_id: str) -> CompiledRouteStage:
        for stage in self.route_contract.route_manifest.stages:
            if stage.stage_id == stage_id:
                return stage
        raise ValueError(
            f"Stage {stage_id} is not part of route {self.creation_route_id}"
        )

    def validate_stage_keys(
        self,
        keys: tuple[str, ...] | list[str] | set[str],
        *,
        label: str,
        require_all: bool,
    ) -> None:
        actual = set(keys)
        expected = set(self.stage_ids)
        unknown = actual - expected
        if unknown:
            raise ValueError(
                f"{label} references stages outside the compiled route: "
                + ", ".join(sorted(unknown))
            )
        if require_all and actual != expected:
            missing = expected - actual
            raise ValueError(
                f"{label} must cover every compiled route stage; missing: "
                + ", ".join(sorted(missing))
            )

    def validate_projection_identity(
        self,
        *,
        run_id: str,
        project_id: str,
        creation_route_id: str,
        route_revision: str,
        route_manifest_digest: str,
        definition_digest: str,
    ) -> None:
        if run_id != self.run_id or project_id != self.project_id:
            raise ValueError("Run projection identity does not match its definition")
        if (
            creation_route_id != self.creation_route_id
            or route_revision != self.route_revision
            or route_manifest_digest != self.route_contract.route_manifest_digest
        ):
            raise ValueError("Run projection route identity does not match its definition")
        if definition_digest != self.definition_digest:
            raise ValueError("Run projection definition digest does not match its definition")


def freeze_contract_payload(
    *,
    contract_id: str,
    contract_revision: str,
    payload: dict[str, Any],
) -> FrozenContractPayload:
    return FrozenContractPayload(
        contract_id=contract_id,
        contract_revision=contract_revision,
        payload=payload,
        payload_digest=canonical_digest(payload),
    )


def freeze_phase32_scale_profile(profile: ScaleProfile) -> FrozenContractPayload:
    """Freeze a validated route scale profile into the Run contract envelope."""

    return freeze_contract_payload(
        contract_id=profile.policy_id,
        contract_revision=profile.policy_revision,
        payload=profile.model_dump(mode="json"),
    )


def _validate_typed_scale_profile(
    payload: FrozenContractPayload,
    *,
    creation_route_id: str,
) -> None:
    """Validate only the new length contract; legacy generic snapshots stay readable."""

    if not payload.contract_id.startswith("length."):
        return
    profile = ScaleProfile.model_validate(payload.payload)
    if profile.policy_id != payload.contract_id:
        raise ValueError("Scale profile policy id does not match its contract envelope")
    if profile.policy_revision != payload.contract_revision:
        raise ValueError("Scale profile revision does not match its contract envelope")
    if profile.route_id != creation_route_id:
        raise ValueError("Scale profile route does not match its Run route")
    if profile.profile_kind == "release_smoke":
        policy = release_smoke_scale_policy(profile.route_id)
    elif profile.profile_kind == "continuity_acceptance":
        policy = continuity_acceptance_scale_policy(profile.route_id)
    else:
        policy = scale_policy(profile.route_id)
    if profile.policy_id != policy.policy_id or profile.policy_revision != policy.revision:
        raise ValueError("Scale profile policy is not the current route policy")
    if profile.minimum != policy.minimum or profile.maximum != policy.maximum:
        raise ValueError("Scale profile envelope does not match its route policy")


def freeze_graph_run_definition(
    *,
    run_id: str,
    project_id: str,
    workflow_id: str,
    workflow_revision: str,
    workflow_digest: str,
    route_contract: FrozenRouteContract,
    scale_profile: FrozenContractPayload,
    inputs: FrozenContractPayload,
    provider_bindings_by_stage: tuple[FrozenStageProviderBinding, ...],
    export_profile: str,
    created_at: str,
) -> GraphRunDefinition:
    payload = {
        "architecture_version": PHASE32_ARCHITECTURE_VERSION,
        "run_id": run_id,
        "project_id": project_id,
        "workflow_id": workflow_id,
        "workflow_revision": workflow_revision,
        "workflow_digest": workflow_digest,
        "route_contract": route_contract.model_dump(mode="json"),
        "scale_profile": scale_profile.model_dump(mode="json"),
        "inputs": inputs.model_dump(mode="json"),
        "provider_bindings_by_stage": [
            binding.model_dump(mode="json") for binding in provider_bindings_by_stage
        ],
        "export_profile": export_profile,
        "created_at": created_at,
    }
    payload["definition_digest"] = canonical_digest(payload)
    return GraphRunDefinition.model_validate(payload)


__all__ = [
    "FrozenContractPayload",
    "FrozenStageProviderBinding",
    "GraphRunDefinition",
    "RunStatus",
    "StageStatus",
    "freeze_contract_payload",
    "freeze_phase32_scale_profile",
    "freeze_graph_run_definition",
]
