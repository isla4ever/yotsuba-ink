from __future__ import annotations

from typing import Any

from novel_workflow.providers.frozen_contract import prompt_digest, schema_digest
from novel_workflow.providers.structured_tasks import contract_for_task
from novel_workflow.runtime.graph.evidence_candidates import build_chapter_evidence_candidates
from novel_workflow.runtime.graph.provider_contract_compiler import (
    schema_for_proposal,
    schema_for_review_role,
    schema_for_stage,
    schema_with_frozen_context_bounds,
    validate_frozen_structured_task,
)
from novel_workflow.runtime.graph.provider_prompt_compiler import (
    render_structured_prompt,
    render_text_prompt,
)
from novel_workflow.runtime.graph.provider_requests import (
    ChapterEvidenceRequest,
    ChapterSceneGenerationRequest,
    ChapterReviewRequest,
    ProposalGenerationRequest,
    ProviderRequest,
    StageGenerationRequest,
)
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.storage.provider_input_store import (
    ProviderInputPayload,
    ProviderOutputContract,
)


def compile_provider_input(request: ProviderRequest) -> ProviderInputPayload:
    """Compile the deterministic, secret-free input that the Provider will see."""

    if isinstance(request, StageGenerationRequest):
        return _structured_provider_input(
            request,
            stage_id=request.stage_id,
            task_name=request.stage_id,
            frozen_task_name=request.stage_id,
            schema=schema_for_stage(request.stage_id),
            context=request.context,
        )
    if isinstance(request, ProposalGenerationRequest):
        schema, _ = schema_for_proposal(request.proposal_type)
        task_name = f"{request.proposal_type}.proposal"
        return _structured_provider_input(
            request,
            stage_id=request.stage_id,
            task_name=task_name,
            frozen_task_name=task_name,
            schema=schema,
            context=request.context,
        )
    if isinstance(request, ChapterReviewRequest):
        return _structured_provider_input(
            request,
            stage_id="text",
            task_name="text.review",
            frozen_task_name=f"text.review.{request.role}",
            schema=schema_for_review_role(request.role),
            context=request.context,
        )
    if isinstance(request, ChapterEvidenceRequest):
        context = {
            "chapter_id": request.chapter_id,
            "chapter_version_id": request.chapter_version_id,
            "frozen_state": request.context,
            "evidence_candidates": [
                candidate.prompt_payload()
                for candidate in build_chapter_evidence_candidates(request.content)
            ],
        }
        return _structured_provider_input(
            request,
            stage_id="text",
            task_name="text.evidence",
            frozen_task_name="text.evidence",
            schema=contract_for_task("text.evidence").schema,
            context=context,
        )
    if isinstance(request, ChapterSceneGenerationRequest):
        plain_text_contract = (
            "One bounded replacement passage for the masked rejected scene segment; "
            "no full-scene rewrite, heading, JSON, Markdown, metadata, analysis, or commentary."
            if request.mode == "fact_repair"
            else (
                "One complete scene segment as plain prose only; no scene heading, JSON, "
                "Markdown fences, metadata, analysis, commentary, or truncation."
            )
        )
        return ProviderInputPayload(
            stage_id="text",
            task_name="text.scene",
            attempt=request.scene_attempt,
            chapter_id=request.chapter_id,
            provider_binding=_secret_free_binding(request.binding),
            prompt_template_id=request.binding.prompt_template_id,
            prompt_digest=request.binding.prompt_digest,
            rendered_prompt=render_text_prompt(request.binding, request.context),
            structured_context=request.context,
            output_contract=ProviderOutputContract(
                kind="plain_text",
                plain_text_contract=plain_text_contract,
            ),
        )
    binding = request.binding
    return ProviderInputPayload(
        stage_id="cover",
        task_name="cover.image",
        attempt=request.generation_attempt,
        provider_binding=_secret_free_binding(binding),
        prompt_template_id="cover-image-prompt",
        prompt_digest=prompt_digest(request.prompt),
        rendered_prompt=request.prompt,
        structured_context={
            "candidate_index": request.candidate_index,
            "generation_attempt": request.generation_attempt,
        },
        output_contract=ProviderOutputContract(
            kind="image",
            image_contract={
                "model": binding.model,
                "size": binding.size,
                "quality": binding.quality,
                "timeout_seconds": binding.timeout_seconds,
            },
        ),
    )


def _structured_provider_input(
    request: StageGenerationRequest | ProposalGenerationRequest | ChapterReviewRequest | ChapterEvidenceRequest,
    *,
    stage_id: str,
    task_name: str,
    frozen_task_name: str,
    schema: dict[str, Any],
    context: dict[str, Any],
) -> ProviderInputPayload:
    binding = request.binding
    validate_frozen_structured_task(
        binding,
        frozen_task_name=frozen_task_name,
        provider_task_name=task_name,
        schema=schema,
    )
    effective_schema = schema_with_frozen_context_bounds(
        frozen_task_name,
        schema,
        context,
    )
    frozen = binding.structured_tasks[frozen_task_name]
    return ProviderInputPayload(
        stage_id=stage_id,
        task_name=task_name,
        attempt=request.attempt,
        chapter_id=str(getattr(request, "chapter_id", "")),
        chapter_version_id=str(getattr(request, "chapter_version_id", "")),
        provider_binding=_secret_free_binding(binding),
        prompt_template_id=binding.prompt_template_id,
        prompt_digest=binding.prompt_digest,
        rendered_prompt=render_structured_prompt(
            binding,
            task_name,
            context,
            effective_schema,
        ),
        structured_context=context,
        output_contract=ProviderOutputContract(
            kind="structured_json",
            json_schema_contract=effective_schema,
            schema_digest=schema_digest(effective_schema),
            structured_mode=frozen.effective_mode,
        ),
    )


def _secret_free_binding(binding: ProviderBinding | CoverAssetBinding) -> dict[str, Any]:
    return _without_secret_or_header_config(binding.model_dump(mode="json"))


def secret_free_provider_binding(
    binding: ProviderBinding | CoverAssetBinding,
) -> dict[str, Any]:
    """Public compiler boundary for secret-free sidecar Provider snapshots."""

    return _secret_free_binding(binding)


def _without_secret_or_header_config(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_secret_or_header_config(item)
            for key, item in value.items()
            if not _is_secret_or_header_key(key)
        }
    if isinstance(value, list):
        return [_without_secret_or_header_config(item) for item in value]
    return value


def _is_secret_or_header_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized
        in {
            "api_key",
            "authorization",
            "header",
            "headers",
            "secret",
            "secret_ref",
        }
        or normalized.endswith("_header")
        or normalized.endswith("_headers")
    )


__all__ = ["compile_provider_input", "secret_free_provider_binding"]
