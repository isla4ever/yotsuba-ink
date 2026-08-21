from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding


class ProviderOperationError(RuntimeError):
    """A frozen Provider operation failed and must not silently reroute."""

    def __init__(
        self,
        message: str,
        *,
        operation_key: str = "",
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
        provider_result: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation_key = operation_key
        self.usage = usage or {}
        self.diagnostic = diagnostic or {}
        self.provider_result = provider_result

    @classmethod
    def for_operation(
        cls,
        operation_key: str,
        error: Exception | str,
    ) -> "ProviderOperationError":
        return cls(
            str(error),
            operation_key=operation_key,
            usage=getattr(error, "usage", {}),
            diagnostic=getattr(error, "diagnostic", {}),
            provider_result=getattr(error, "provider_result", None),
        )


class StageGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    stage_id: StageId
    attempt: int = Field(ge=1)
    binding: ProviderBinding
    context: dict[str, Any]


class ProposalGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    stage_id: StageId
    proposal_type: Literal[
        "role_demand",
        "role_demand_review",
        "spine_review",
        "cast_review",
        "cast_relation",
        "volume_boundary",
        "detail_layout",
    ]
    attempt: int = Field(ge=1)
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterSceneGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_number: int = Field(ge=1)
    chapter_attempt: int = Field(ge=1)
    scene_index: int = Field(ge=1)
    scene_attempt: int = Field(ge=1, le=2)
    mode: Literal["generate", "fact_repair"] = "generate"
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    role: str
    required: bool
    attempt: int = Field(ge=1)
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    attempt: int = Field(ge=1)
    content: str = Field(min_length=1)
    binding: ProviderBinding
    context: dict[str, Any] = Field(default_factory=dict)


class CoverImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    candidate_index: int = Field(ge=1, le=4)
    generation_attempt: int = Field(ge=1)
    binding: CoverAssetBinding
    prompt: str = Field(min_length=1, max_length=6000)


ProviderRequest = (
    StageGenerationRequest
    | ProposalGenerationRequest
    | ChapterSceneGenerationRequest
    | ChapterReviewRequest
    | ChapterEvidenceRequest
    | CoverImageRequest
)


__all__ = [
    "ChapterEvidenceRequest",
    "ChapterSceneGenerationRequest",
    "ChapterReviewRequest",
    "CoverImageRequest",
    "ProposalGenerationRequest",
    "ProviderOperationError",
    "ProviderRequest",
    "StageGenerationRequest",
]
