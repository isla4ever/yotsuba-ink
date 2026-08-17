from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterDossierBatch,
    CoverBrief,
    DetailSegmentArtifact,
    StorySpineDraftArtifact,
    VolumeArchitectureUnitArtifact,
)
from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from novel_workflow.providers.usage import provider_usage_snapshot
from novel_workflow.runtime.graph.provider_contract_compiler import (
    schema_for_proposal,
)
from novel_workflow.runtime.graph.provider_input_compiler import compile_provider_input
from novel_workflow.runtime.graph.provider_prompt_compiler import (
    render_structured_prompt,
)
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.runtime.graph.provider_requests import (
    ChapterEvidenceRequest,
    ChapterSceneGenerationRequest,
    ChapterReviewRequest,
    CoverImageRequest,
    ProposalGenerationRequest,
    ProviderOperationError,
    StageGenerationRequest,
)
from novel_workflow.output_contracts.provider_tasks import (
    ChapterEvidenceResult,
    ChapterReviewResult,
    EvidenceClaimProposal,
    ReviewFinding,
)


class StructuredProviderResult(BaseModel):
    """One strict Provider response plus its non-Artifact receipt metadata."""

    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


class PlainTextProviderResult(BaseModel):
    """One complete prose response; chapter generation never parses JSON."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)


class NarrativeProviderGateway(Protocol):
    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult: ...

    async def generate_chapter_scene(
        self,
        request: ChapterSceneGenerationRequest,
    ) -> PlainTextProviderResult: ...

    async def generate_proposal(self, request: ProposalGenerationRequest) -> StructuredProviderResult: ...

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage: ...

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult: ...

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult: ...


class FrozenNarrativeProviderGateway:
    """Strict vNext adapter built only from a Run's executable Provider snapshots.

    LangGraph owns control flow. This adapter owns one network call and has no
    retry, alias, schema conversion, or alternate Provider behavior.
    """

    def __init__(
        self,
        secret_resolver: Callable[[str], str | None],
        *,
        text_provider_factory: Callable[[ProviderBinding, str], TextProvider] | None = None,
        image_provider_factory: Callable[[CoverAssetBinding, str], ImageProvider] | None = None,
    ) -> None:
        self.secret_resolver = secret_resolver
        self.text_provider_factory = text_provider_factory or _build_text_provider
        self.image_provider_factory = image_provider_factory or _build_image_provider

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        compiled = compile_provider_input(request)
        schema = compiled.output_contract.json_schema_contract or {}
        response = await self._structured(
            request.binding,
            request.operation_key,
            request.stage_id,
            request.context,
            schema,
            rendered_prompt=compiled.rendered_prompt,
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

    async def generate_chapter_scene(
        self,
        request: ChapterSceneGenerationRequest,
    ) -> PlainTextProviderResult:
        provider = self._text_provider(request.binding)
        prompt = compile_provider_input(request).rendered_prompt
        try:
            content = await provider.generate_text(
                prompt,
                task_name="text",
                context={"idempotency_key": request.operation_key},
            )
            result = PlainTextProviderResult(
                content=content,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            )
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=provider_usage_snapshot(provider),
                diagnostic=_provider_diagnostic(provider),
            ) from exc
        if not result.content.strip():
            raise ProviderOperationError(
                "Chapter Provider returned empty prose",
                operation_key=request.operation_key,
                usage=result.usage,
                diagnostic=result.diagnostic,
            )
        return result

    async def generate_proposal(self, request: ProposalGenerationRequest) -> StructuredProviderResult:
        compiled = compile_provider_input(request)
        schema = compiled.output_contract.json_schema_contract or {}
        _, model = schema_for_proposal(request.proposal_type)
        response = await self._structured(
            request.binding,
            request.operation_key,
            f"{request.proposal_type}.proposal",
            request.context,
            schema,
            rendered_prompt=compiled.rendered_prompt,
        )
        try:
            model.model_validate(response.payload)
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage:
        provider = self._image_provider(request.binding)
        compiled = compile_provider_input(request)
        return await provider.generate_cover(
            compiled.rendered_prompt,
            context={
                "idempotency_key": request.operation_key,
                "model": request.binding.model,
                "size": request.binding.size,
                "quality": request.binding.quality,
                "timeout_seconds": request.binding.timeout_seconds,
            },
        )

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        compiled = compile_provider_input(request)
        response = await self._structured(
            request.binding,
            request.operation_key,
            "text.review",
            request.context,
            compiled.output_contract.json_schema_contract or {},
            frozen_task_name=f"text.review.{request.role}",
            rendered_prompt=compiled.rendered_prompt,
        )
        try:
            result = ChapterReviewResult.model_validate(response.payload)
            validate_review_result_contract(request, result)
        except Exception as exc:
            raise ProviderOperationError(
                str(exc),
                operation_key=request.operation_key,
                usage=response.usage,
                diagnostic=response.diagnostic,
            ) from exc
        return response

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        compiled = compile_provider_input(request)
        response = await self._structured(
            request.binding,
            request.operation_key,
            "text.evidence",
            compiled.structured_context,
            compiled.output_contract.json_schema_contract or {},
            rendered_prompt=compiled.rendered_prompt,
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
        *,
        frozen_task_name: str = "",
        rendered_prompt: str = "",
    ) -> StructuredProviderResult:
        provider = self._text_provider(binding)
        prompt = rendered_prompt or render_structured_prompt(binding, task_name, context, schema)
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

    def _text_provider(self, binding: ProviderBinding) -> TextProvider:
        secret = self._secret(binding.provider_config.secret_ref)
        return self.text_provider_factory(binding, secret)

    def _image_provider(self, binding: CoverAssetBinding) -> ImageProvider:
        secret = self._secret(binding.provider_config.secret_ref)
        return self.image_provider_factory(binding, secret)

    def _secret(self, secret_ref: str) -> str:
        value = self.secret_resolver(secret_ref)
        if not isinstance(value, str) or not value.strip():
            raise ProviderOperationError(
                "Frozen Provider secret is unavailable",
                diagnostic={"code": "secret_unavailable"},
            )
        return value.strip()


def _build_text_provider(binding: ProviderBinding, secret: str) -> TextProvider:
    config = binding.provider_config
    return OpenAICompatibleTextProvider(
        base_url=config.base_url,
        api_key=secret,
        model=binding.model,
        temperature=binding.temperature,
        max_tokens=binding.max_tokens,
        top_p=binding.top_p,
        timeout_seconds=binding.timeout_seconds,
        template_id=binding.template_id,
        template=binding.provider_template,
    )


def _build_image_provider(binding: CoverAssetBinding, secret: str) -> ImageProvider:
    config = binding.provider_config
    return OpenAICompatibleImageProvider(
        base_url=config.base_url,
        api_key=secret,
        model=binding.model,
        timeout_seconds=binding.timeout_seconds,
        template_id=binding.template_id,
        template=binding.provider_template,
    )


def _provider_diagnostic(provider: Any) -> dict[str, Any]:
    value = getattr(provider, "last_response_diagnostic", None)
    return dict(value) if isinstance(value, dict) else {}


def _validate_stage_payload(stage_id: str, payload: dict[str, Any]) -> None:
    from novel_workflow.output_contracts.artifacts_vnext import ARTIFACT_MODELS

    if stage_id == "cover":
        CoverBrief.model_validate(payload)
        return
    if stage_id == "cast":
        CharacterDossierBatch.model_validate(payload)
        return
    if stage_id == "spine":
        StorySpineDraftArtifact.model_validate(payload)
        return
    if stage_id == "volumes":
        VolumeArchitectureUnitArtifact.model_validate(payload)
        return
    if stage_id == "detail":
        DetailSegmentArtifact.model_validate(payload)
        return
    ARTIFACT_MODELS[stage_id].model_validate(payload)


def validate_review_result_contract(
    request: ChapterReviewRequest,
    result: ChapterReviewResult,
) -> None:
    """Reject a reviewer result that cannot be grounded in its frozen chapter context."""

    if result.role != request.role:
        raise ValueError("Reviewer result role does not match its frozen lane")
    if not result.findings:
        return
    material = request.context.get("material")
    if not isinstance(material, dict):
        raise ValueError("Reviewer context must contain its immutable material")
    chapter = material.get("chapter")
    content = chapter.get("content") if isinstance(chapter, dict) else None
    if not isinstance(content, str) or not content:
        raise ValueError("Reviewer context must contain the immutable chapter content")
    for finding in result.findings:
        if finding.evidence not in content:
            raise ValueError("Reviewer evidence must be an exact excerpt from the chapter")
    if request.role != "character":
        return
    policy = material.get("appearance_policy")
    if not isinstance(policy, dict):
        raise ValueError("Character reviewer context must contain an appearance policy")
    future_ids = {
        str(value)
        for value in policy.get("not_yet_eligible_subject_ids") or []
    }
    known_ids = {
        *(
            str(value)
            for value in policy.get("eligible_subject_ids") or []
        ),
        *future_ids,
    }
    for finding in result.findings:
        subject_ids = set(finding.subject_ids)
        if not subject_ids:
            raise ValueError("Character review findings must identify their frozen subjects")
        unknown = subject_ids - known_ids
        if unknown:
            raise ValueError(
                f"Character review references unknown frozen subjects: {sorted(unknown)}"
            )


__all__ = [
    "ChapterSceneGenerationRequest",
    "ChapterEvidenceRequest",
    "ChapterEvidenceResult",
    "ChapterReviewRequest",
    "ChapterReviewResult",
    "CoverImageRequest",
    "NarrativeProviderGateway",
    "PlainTextProviderResult",
    "ProposalGenerationRequest",
    "ProviderOperationError",
    "FrozenNarrativeProviderGateway",
    "ReviewFinding",
    "StageGenerationRequest",
    "StructuredProviderResult",
    "compile_provider_input",
    "validate_review_result_contract",
]
