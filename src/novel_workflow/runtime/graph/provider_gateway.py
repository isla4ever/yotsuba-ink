from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import CoverBrief, StageId
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.providers.usage import provider_usage_snapshot
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.workflows.schemas import ModelSettings

if TYPE_CHECKING:
    from novel_workflow.providers.registry import ProviderRegistry


class ProviderOperationError(RuntimeError):
    """A frozen Provider operation failed and must not silently reroute."""

    def __init__(
        self,
        message: str,
        *,
        operation_key: str = "",
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.operation_key = operation_key
        self.usage = usage or {}
        self.diagnostic = diagnostic or {}

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
        )


class StructuredProviderResult(BaseModel):
    """One strict Provider response plus its non-Artifact receipt metadata."""

    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


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
    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult: ...

    async def generate_chapter(self, request: ChapterGenerationRequest) -> StructuredProviderResult: ...

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage: ...

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult: ...

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult: ...


class RegistryNarrativeProviderGateway:
    """Strict vNext adapter around an explicitly selected text Provider.

    LangGraph owns control flow. This adapter owns one network call and has no
    retry, alias, schema conversion, or alternate Provider behavior.
    """

    def __init__(self, registry: "ProviderRegistry") -> None:
        self.registry = registry

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        schema = _schema_for_stage(request.stage_id)
        response = await self._structured(
            request.binding,
            request.operation_key,
            request.stage_id,
            request.context,
            schema,
        )
        try:
            _validate_stage_payload(request.stage_id, response.payload)
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def generate_chapter(self, request: ChapterGenerationRequest) -> StructuredProviderResult:
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

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        response = await self._structured(
            request.binding,
            request.operation_key,
            "text.review",
            request.context,
            _schema_for_review_role(request.role),
        )
        try:
            result = ChapterReviewResult.model_validate(response.payload)
            if result.role != request.role:
                raise ValueError(
                    "Reviewer result role does not match its frozen lane"
                )
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        response = await self._structured(
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
        ChapterEvidenceResult.model_validate(response.payload)
        return response

    async def _structured(
        self,
        binding: ProviderBinding,
        operation_key: str,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> StructuredProviderResult:
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
        try:
            result = await provider.generate_strict_structured(
                prompt,
                task_name=task_name,
                context={"idempotency_key": operation_key},
                schema=schema,
            )
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=operation_key,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            ) from exc
        if not isinstance(result, dict):
            raise ProviderOperationError(
                "Provider structured result must be a JSON object",
                operation_key=operation_key,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            )
        return StructuredProviderResult(
            payload=result,
            usage=provider_usage_snapshot(provider),
            diagnostic=_provider_diagnostic(provider),
        )


def _provider_diagnostic(provider: Any) -> dict[str, Any]:
    value = getattr(provider, "last_response_diagnostic", None)
    return dict(value) if isinstance(value, dict) else {}


def _schema_for_stage(stage_id: str) -> dict[str, Any]:
    from novel_workflow.output_contracts.artifacts_vnext import ARTIFACT_MODELS

    if stage_id == "cover":
        return CoverBrief.model_json_schema()
    if stage_id == "text":
        return ARTIFACT_MODELS["text"].model_json_schema()
    if stage_id in ARTIFACT_MODELS:
        return ARTIFACT_MODELS[stage_id].model_json_schema()
    raise ProviderOperationError(f"No vNext schema for Provider task {stage_id}")


def _schema_for_review_role(role: str) -> dict[str, Any]:
    """Constrain one parallel review call to its immutable graph-assigned role."""

    schema = ChapterReviewResult.model_json_schema()
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not isinstance(properties.get("role"), dict):
        raise RuntimeError("Chapter review schema is missing its role property")
    properties["role"] = {**properties["role"], "const": role}
    return schema


def _validate_stage_payload(stage_id: str, payload: dict[str, Any]) -> None:
    from novel_workflow.output_contracts.artifacts_vnext import ARTIFACT_MODELS

    if stage_id == "cover":
        CoverBrief.model_validate(payload)
        return
    ARTIFACT_MODELS[stage_id].model_validate(payload)


def _render_prompt(
    binding: ProviderBinding,
    task_name: str,
    context: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    template = binding.prompt_template.strip()
    prefix = f"{template}\n\n" if template else ""
    revision_contract = _revision_contract(context)
    return (
        f"{prefix}You are the Yotsuba Ink {task_name} node.\n"
        "Return exactly one JSON object matching the supplied schema. Do not add commentary, defaults, or fields.\n"
        f"{revision_contract}"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n"
        f"Context:\n{json.dumps(context, ensure_ascii=False, sort_keys=True)}"
    )


def _revision_contract(context: dict[str, Any]) -> str:
    material = context.get("material")
    revision = material.get("revision_request") if isinstance(material, dict) else None
    if not isinstance(revision, dict):
        return ""
    return (
        "The revision_request is the controlling instruction for this call. "
        "Treat source_chapter or source_artifact only as the immutable draft to replace, not as accepted truth. "
        "Return a complete replacement that executes direction; rewrite or remove every source passage that "
        "conflicts with direction, and preserve only unaffected frozen story commitments.\n"
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
    "StructuredProviderResult",
]
