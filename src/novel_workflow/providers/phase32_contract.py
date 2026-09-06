"""Frozen Provider contracts shared by the Phase 32 driver and gateway."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.providers.frozen_contract import (
    FrozenProviderConfig,
    FrozenProviderTemplate,
    frozen_provider_config_digest,
    frozen_provider_template_digest,
    prompt_digest,
    schema_digest,
)
from novel_workflow.providers.usage import Phase32ProviderPricingSnapshot
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.workflows.route_specs import (
    ArtifactKind,
    CreationRouteId,
    ProviderTaskKind,
)


class Phase32ModelSettings(BaseModel):
    """Execution settings frozen independently of the editable workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    model: str = Field(min_length=1, max_length=240)
    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(ge=1, le=200_000)
    top_p: float = Field(gt=0, le=1)
    timeout_seconds: int = Field(ge=1, le=1_800)


class Phase32ProviderExecutionSnapshot(BaseModel):
    """Secret-free executable Provider snapshot owned by one frozen Run."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider_profile_id: str = Field(min_length=1, max_length=240)
    provider_template_id: str = Field(min_length=1, max_length=240)
    provider_config: FrozenProviderConfig
    provider_template: FrozenProviderTemplate
    provider_config_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_template_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_id: str = Field(min_length=1, max_length=240)
    model_settings: Phase32ModelSettings
    pricing_snapshot: Phase32ProviderPricingSnapshot

    @model_validator(mode="after")
    def validate_frozen_identity(self) -> "Phase32ProviderExecutionSnapshot":
        if self.provider_config.kind != "openai-compatible":
            raise ValueError("Phase 32 structured generation requires a text Provider")
        if self.provider_config.provider_profile_id != self.provider_profile_id:
            raise ValueError("Provider profile does not match its frozen config")
        if self.provider_config.template_id != self.provider_template_id:
            raise ValueError("Provider template does not match its frozen config")
        if self.provider_template.id != self.provider_template_id:
            raise ValueError("Provider template does not match its frozen snapshot")
        if self.provider_template.kind != "openai-compatible":
            raise ValueError("Phase 32 structured generation requires a text template")
        if frozen_provider_config_digest(self.provider_config) != self.provider_config_digest:
            raise ValueError("Provider config digest does not match its frozen snapshot")
        if frozen_provider_template_digest(self.provider_template) != self.provider_template_digest:
            raise ValueError("Provider template digest does not match its frozen snapshot")
        if self.model_settings.model != self.model_id:
            raise ValueError("Provider model does not match its frozen settings")
        if (
            self.pricing_snapshot.provider_profile_id != self.provider_profile_id
            or self.pricing_snapshot.provider_template_id != self.provider_template_id
            or self.pricing_snapshot.model_id != self.model_id
        ):
            raise ValueError("Provider pricing does not match its frozen execution identity")
        return self


class Phase32ImageProviderExecutionSnapshot(BaseModel):
    """Frozen image-provider identity reserved for the cover sub-operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider_profile_id: str = Field(min_length=1, max_length=240)
    provider_template_id: str = Field(min_length=1, max_length=240)
    provider_config: FrozenProviderConfig
    provider_template: FrozenProviderTemplate
    provider_config_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_template_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_id: str = Field(min_length=1, max_length=240)
    candidate_count: int = Field(ge=1, le=4)
    size: str = Field(pattern=r"^\d{3,5}x\d{3,5}$")
    quality: Literal["low", "medium", "high"]
    timeout_seconds: int = Field(ge=1, le=1_800)
    pricing_snapshot: Phase32ProviderPricingSnapshot

    @model_validator(mode="after")
    def validate_frozen_identity(self) -> "Phase32ImageProviderExecutionSnapshot":
        if self.provider_config.kind != "openai-compatible-image":
            raise ValueError("Phase 32 cover assets require an image Provider")
        if self.provider_config.provider_profile_id != self.provider_profile_id:
            raise ValueError("Image Provider profile does not match its frozen config")
        if self.provider_config.template_id != self.provider_template_id:
            raise ValueError("Image Provider template does not match its frozen config")
        if self.provider_template.id != self.provider_template_id:
            raise ValueError("Image Provider template does not match its frozen snapshot")
        if self.provider_template.kind != "openai-compatible-image":
            raise ValueError("Phase 32 cover assets require an image template")
        if frozen_provider_config_digest(self.provider_config) != self.provider_config_digest:
            raise ValueError("Image Provider config digest does not match its frozen snapshot")
        if frozen_provider_template_digest(self.provider_template) != self.provider_template_digest:
            raise ValueError("Image Provider template digest does not match its frozen snapshot")
        if (
            self.pricing_snapshot.provider_profile_id != self.provider_profile_id
            or self.pricing_snapshot.provider_template_id != self.provider_template_id
            or self.pricing_snapshot.model_id != self.model_id
        ):
            raise ValueError("Image Provider pricing does not match its execution identity")
        return self


class Phase32ProviderTaskSnapshot(BaseModel):
    """Exact task instructions and schema frozen before a Run can execute."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider_task_kind: ProviderTaskKind
    artifact_kind: ArtifactKind
    transport_task_name: str = Field(pattern=r"^[a-z][a-z0-9_.]{1,79}$")
    prompt_template_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    prompt_template: str = Field(min_length=1, max_length=40_000)
    prompt_template_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_schema: dict[str, Any]
    output_schema_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_task_snapshot(self) -> "Phase32ProviderTaskSnapshot":
        if prompt_digest(self.prompt_template) != self.prompt_template_digest:
            raise ValueError("Phase 32 prompt digest does not match its frozen template")
        if schema_digest(self.output_schema) != self.output_schema_digest:
            raise ValueError("Phase 32 schema digest does not match its frozen contract")
        return self


class Phase32StageProviderBindingSnapshot(BaseModel):
    """One typed Provider binding for one route stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    workflow_id: str = Field(min_length=1, max_length=240)
    creation_route_id: CreationRouteId
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    execution: Phase32ProviderExecutionSnapshot
    image_execution: Phase32ImageProviderExecutionSnapshot | None = None
    task: Phase32ProviderTaskSnapshot

    @model_validator(mode="after")
    def validate_stage_identity(self) -> "Phase32StageProviderBindingSnapshot":
        if self.task.artifact_kind == "script_delivery" or self.task.artifact_kind == "book_delivery":
            raise ValueError("Deterministic delivery stages cannot have a Provider binding")
        if self.image_execution is not None and self.task.provider_task_kind != "cover":
            raise ValueError("Only the cover stage may freeze an image Provider")
        return self


class Phase32ProviderRequest(BaseModel):
    """Secret-free, content-addressable request persisted before network IO."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    operation_key: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=240)
    creation_route_id: CreationRouteId
    route_revision: str = Field(min_length=1, max_length=80)
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    provider_task_kind: ProviderTaskKind
    artifact_kind: ArtifactKind
    provider_profile_id: str = Field(min_length=1, max_length=240)
    provider_template_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    provider_binding_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    transport_task_name: str = Field(pattern=r"^[a-z][a-z0-9_.]{1,79}$")
    rendered_prompt: str = Field(min_length=1, max_length=200_000)
    rendered_prompt_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_schema: dict[str, Any]
    output_schema_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    context: dict[str, Any]
    direction: str = Field(default="", max_length=4_000)

    @model_validator(mode="after")
    def validate_exact_input(self) -> "Phase32ProviderRequest":
        if prompt_digest(self.rendered_prompt) != self.rendered_prompt_digest:
            raise ValueError("Rendered Provider prompt digest does not match its content")
        if schema_digest(self.output_schema) != self.output_schema_digest:
            raise ValueError("Provider output schema digest does not match its content")
        return self


class Phase32ProviderResponse(BaseModel):
    """Provider payload plus non-authoritative, public receipt hints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


class Phase32WritebackProviderRequest(BaseModel):
    """Frozen Evidence proposal request for one accepted Script/Text Artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    operation_key: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=240)
    creation_route_id: CreationRouteId
    route_revision: str = Field(min_length=1, max_length=80)
    stage_id: Literal["script", "text"]
    unit_ref: str = Field(min_length=1, max_length=500)
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    provider_profile_id: str = Field(min_length=1, max_length=240)
    provider_template_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    provider_binding_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract_revision: Literal["phase32-writeback-v1"] = "phase32-writeback-v1"
    rendered_prompt: str = Field(min_length=1, max_length=200_000)
    rendered_prompt_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_schema: dict[str, Any]
    output_schema_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    context: dict[str, Any]

    @model_validator(mode="after")
    def validate_exact_input(self) -> "Phase32WritebackProviderRequest":
        if prompt_digest(self.rendered_prompt) != self.rendered_prompt_digest:
            raise ValueError("Writeback prompt digest does not match its content")
        if schema_digest(self.output_schema) != self.output_schema_digest:
            raise ValueError("Writeback schema digest does not match its content")
        return self


class Phase32CoverImageRequest(BaseModel):
    """Secret-free image sub-operation frozen after the cover proposal returns."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    operation_key: str = Field(min_length=1, max_length=500)
    run_id: str = Field(min_length=1, max_length=240)
    creation_route_id: CreationRouteId
    route_revision: str = Field(min_length=1, max_length=80)
    stage_id: Literal["cover"] = "cover"
    candidate_index: int = Field(ge=1, le=4)
    generation_attempt: int = Field(ge=1)
    provider_profile_id: str = Field(min_length=1, max_length=240)
    provider_template_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    provider_binding_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: str = Field(pattern=r"^\d{3,5}x\d{3,5}$")
    quality: Literal["low", "medium", "high"]
    prompt: str = Field(min_length=1, max_length=6_000)


class Phase32ProviderGateway(Protocol):
    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding: Phase32StageProviderBindingSnapshot,
    ) -> Phase32ProviderResponse: ...

    async def generate_cover_image(
        self,
        request: Phase32CoverImageRequest,
        *,
        binding: Phase32ImageProviderExecutionSnapshot,
    ) -> GeneratedImage: ...


class Phase32WritebackGateway(Protocol):
    async def generate_writeback(
        self,
        request: Phase32WritebackProviderRequest,
        *,
        binding: Phase32StageProviderBindingSnapshot,
    ) -> Phase32ProviderResponse: ...


@runtime_checkable
class Phase32ProviderReadinessGate(Protocol):
    """Optional pre-IO gate implemented by real Provider adapters."""

    def ensure_ready(self, binding: Phase32StageProviderBindingSnapshot) -> None: ...


__all__ = [
    "Phase32ModelSettings",
    "Phase32ImageProviderExecutionSnapshot",
    "Phase32CoverImageRequest",
    "Phase32ProviderExecutionSnapshot",
    "Phase32ProviderGateway",
    "Phase32ProviderReadinessGate",
    "Phase32ProviderRequest",
    "Phase32ProviderResponse",
    "Phase32ProviderTaskSnapshot",
    "Phase32StageProviderBindingSnapshot",
    "Phase32WritebackGateway",
    "Phase32WritebackProviderRequest",
]
