from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import CoverBrief, StageId
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.workflows.schemas import ModelSettings

if TYPE_CHECKING:
    from novel_workflow.providers.registry import ProviderRegistry


class ProviderOperationError(RuntimeError):
    """A frozen Provider operation failed and must not silently reroute."""


class StageGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    stage_id: StageId
    attempt: int = Field(ge=1)
    binding: ProviderBinding
    context: dict[str, Any]


class ChapterGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_number: int = Field(ge=1)
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
    binding: ProviderBinding
    context: dict[str, Any]


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    severity: Literal["warning", "blocking"]
    claim: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(default="", max_length=2000)


class ChapterReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    available: bool = True
    findings: list[ReviewFinding] = Field(default_factory=list)


class EvidenceSpanProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class EvidenceClaimProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["fact", "character", "relationship", "foreshadow", "summary"]
    claim: str = Field(min_length=1, max_length=2000)
    spans: list[EvidenceSpanProposal] = Field(min_length=1, max_length=20)


class ChapterEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[EvidenceClaimProposal] = Field(default_factory=list, max_length=80)


class ChapterEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    content: str = Field(min_length=1)
    binding: ProviderBinding


class CoverImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    candidate_index: int = Field(ge=1, le=4)
    generation_attempt: int = Field(ge=1)
    binding: CoverAssetBinding
    prompt: str = Field(min_length=1, max_length=6000)


class NarrativeProviderGateway(Protocol):
    async def generate_stage(self, request: StageGenerationRequest) -> dict[str, Any]: ...

    async def generate_chapter(self, request: ChapterGenerationRequest) -> dict[str, Any]: ...

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage: ...

    async def review_chapter(self, request: ChapterReviewRequest) -> ChapterReviewResult: ...

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> ChapterEvidenceResult: ...


class RegistryNarrativeProviderGateway:
    """Strict vNext adapter around an explicitly selected text Provider.

    LangGraph owns control flow. This adapter owns one network call and has no
    retry, alias, schema conversion, or alternate Provider behavior.
    """

    def __init__(self, registry: "ProviderRegistry") -> None:
        self.registry = registry

    async def generate_stage(self, request: StageGenerationRequest) -> dict[str, Any]:
        schema = _schema_for_stage(request.stage_id)
        return await self._structured(request.binding, request.operation_key, request.stage_id, request.context, schema)

    async def generate_chapter(self, request: ChapterGenerationRequest) -> dict[str, Any]:
        schema = _schema_for_stage("text")
        return await self._structured(request.binding, request.operation_key, "text", request.context, schema)

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage:
        provider = self.registry.image_for(request.binding.provider_profile_id)
        return await provider.generate_cover(
            request.prompt,
            context={
                "idempotency_key": request.operation_key,
                "model": request.binding.model,
                "size": request.binding.size,
                "quality": request.binding.quality,
                "timeout_seconds": request.binding.timeout_seconds,
            },
        )

    async def review_chapter(self, request: ChapterReviewRequest) -> ChapterReviewResult:
        payload = await self._structured(
            request.binding,
            request.operation_key,
            "text.review",
            request.context,
            ChapterReviewResult.model_json_schema(),
        )
        return ChapterReviewResult.model_validate(payload)

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> ChapterEvidenceResult:
        payload = await self._structured(
            request.binding,
            request.operation_key,
            "text.evidence",
            {
                "chapter_id": request.chapter_id,
                "chapter_version_id": request.chapter_version_id,
                "content": request.content,
            },
            ChapterEvidenceResult.model_json_schema(),
        )
        return ChapterEvidenceResult.model_validate(payload)

    async def _structured(
        self,
        binding: ProviderBinding,
        operation_key: str,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        provider = self.registry.text_for(
            binding.provider_profile_id,
            ModelSettings(
                model=binding.model,
                temperature=binding.temperature,
                max_tokens=binding.max_tokens,
                top_p=binding.top_p,
                timeout_seconds=binding.timeout_seconds,
            ),
        )
        prompt = _render_prompt(binding, task_name, context, schema)
        result = await provider.generate_strict_structured(
            prompt,
            task_name=task_name,
            context={"idempotency_key": operation_key},
            schema=schema,
        )
        if not isinstance(result, dict):
            raise ProviderOperationError("Provider structured result must be a JSON object")
        return result


def _schema_for_stage(stage_id: str) -> dict[str, Any]:
    from novel_workflow.output_contracts.artifacts_vnext import ARTIFACT_MODELS

    if stage_id == "cover":
        return CoverBrief.model_json_schema()
    if stage_id == "text":
        return ARTIFACT_MODELS["text"].model_json_schema()
    if stage_id in ARTIFACT_MODELS:
        return ARTIFACT_MODELS[stage_id].model_json_schema()
    raise ProviderOperationError(f"No vNext schema for Provider task {stage_id}")


def _render_prompt(
    binding: ProviderBinding,
    task_name: str,
    context: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    template = binding.prompt_template.strip()
    prefix = f"{template}\n\n" if template else ""
    return (
        f"{prefix}You are the Yotsuba Ink {task_name} node.\n"
        "Return exactly one JSON object matching the supplied schema. Do not add commentary, defaults, or fields.\n"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        f"Context:\n{json.dumps(context, ensure_ascii=False, sort_keys=True)}"
    )


__all__ = [
    "ChapterGenerationRequest",
    "ChapterEvidenceRequest",
    "ChapterEvidenceResult",
    "ChapterReviewRequest",
    "ChapterReviewResult",
    "CoverImageRequest",
    "NarrativeProviderGateway",
    "ProviderOperationError",
    "RegistryNarrativeProviderGateway",
    "ReviewFinding",
    "StageGenerationRequest",
]
