from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterDraftResult,
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ChapterGenerationRequest,
    ChapterReviewRequest,
    ChapterReviewResult,
    CoverImageRequest,
    ProviderOperationError,
    RegistryNarrativeProviderGateway,
    StageGenerationRequest,
)
from novel_workflow.runtime.graph.chapter_writeback import _bind_evidence_spans
from novel_workflow.runtime.graph.evidence_candidates import (
    build_chapter_evidence_candidates,
)
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.workflows.schemas import ModelSettings


class CapturingTextProvider(TextProvider):
    name = "capturing-provider"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.last_usage = {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29}
        self.last_response_diagnostic = {"finish_reason": "stop"}

    async def generate_text(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
    ) -> str:
        raise AssertionError("The Graph gateway must use strict structured output")

    async def generate_strict_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append({
            "prompt": prompt,
            "task_name": task_name,
            "context": context,
            "schema": schema,
        })
        return {
            "title": "雾港母带",
            "premise": "调查失踪母带。",
            "story_promise": {"genre": "悬疑", "audience": "成人", "tone": "克制"},
            "world_rules": ["广播会覆盖记忆"],
            "thematic_question": "真相的代价是什么？",
            "ending_promise": "终章公开来源。",
            "voice": {"viewpoint": "第三人称", "tense": "过去时", "texture": "听觉", "avoid": []},
            "cast_requirements": [],
        }


class InvalidArtifactTextProvider(CapturingTextProvider):
    async def generate_strict_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append({
            "prompt": prompt,
            "task_name": task_name,
            "context": context,
            "schema": schema,
        })
        return {"title": "缺少合同字段"}


class CapturingReviewTextProvider(CapturingTextProvider):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__()
        self.payload = payload

    async def generate_strict_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append({
            "prompt": prompt,
            "task_name": task_name,
            "context": context,
            "schema": schema,
        })
        return self.payload


class CapturingRegistry:
    def __init__(self, provider: TextProvider) -> None:
        self.provider = provider
        self.requests: list[tuple[str, ModelSettings]] = []

    def text_for(self, provider_profile_id: str, settings: ModelSettings) -> TextProvider:
        self.requests.append((provider_profile_id, settings))
        return self.provider


class CapturingImageProvider(ImageProvider):
    name = "capturing-image-provider"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        self.calls.append({"prompt": prompt, "context": context})
        return GeneratedImage(content=b"image", mime_type="image/png")


class CapturingImageRegistry:
    def __init__(self, provider: ImageProvider) -> None:
        self.provider = provider
        self.provider_ids: list[str] = []

    def image_for(self, provider_profile_id: str) -> ImageProvider:
        self.provider_ids.append(provider_profile_id)
        return self.provider


@pytest.mark.asyncio
async def test_graph_gateway_applies_the_frozen_provider_binding_without_fallback() -> None:
    provider = CapturingTextProvider()
    registry = CapturingRegistry(provider)
    binding = ProviderBinding(
        provider_profile_id="provider-primary",
        model="model-frozen",
        temperature=0.31,
        max_tokens=2345,
        top_p=0.73,
        timeout_seconds=87,
        prompt_template="Use the frozen story contract.",
    )

    result = await RegistryNarrativeProviderGateway(registry).generate_stage(  # type: ignore[arg-type]
        StageGenerationRequest(
            operation_key="run-1:info:generate:1",
            run_id="run-1",
            stage_id="info",
            attempt=1,
            binding=binding,
            context={"genre": "悬疑"},
        )
    )

    assert result.payload["title"] == "雾港母带"
    assert result.usage == {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29}
    assert result.diagnostic == {"finish_reason": "stop"}
    assert len(registry.requests) == 1
    provider_id, settings = registry.requests[0]
    assert provider_id == "provider-primary"
    assert settings.model_dump() == {
        "model": "model-frozen",
        "temperature": 0.31,
        "max_tokens": 2345,
        "top_p": 0.73,
        "timeout_seconds": 87,
    }
    assert provider.calls[0]["context"] == {"idempotency_key": "run-1:info:generate:1"}
    assert "Use the frozen story contract." in provider.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_graph_gateway_rejects_invalid_artifacts_with_the_current_operation_receipt() -> None:
    provider = InvalidArtifactTextProvider()
    registry = CapturingRegistry(provider)
    binding = ProviderBinding(provider_profile_id="provider-primary", model="model-frozen")

    with pytest.raises(ProviderOperationError) as raised:
        await RegistryNarrativeProviderGateway(registry).generate_stage(  # type: ignore[arg-type]
            StageGenerationRequest(
                operation_key="run-1:info:generate:1",
                run_id="run-1",
                stage_id="info",
                attempt=1,
                binding=binding,
                context={"genre": "悬疑"},
            )
        )

    assert raised.value.operation_key == "run-1:info:generate:1"
    assert raised.value.usage == {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29}


@pytest.mark.asyncio
async def test_graph_gateway_locks_each_review_schema_to_its_frozen_lane() -> None:
    provider = CapturingReviewTextProvider(
        ChapterReviewResult(role="continuity").model_dump(mode="json")
    )
    registry = CapturingRegistry(provider)
    request = ChapterReviewRequest(
        operation_key="run-1:chapter-1:review:chapter-1-v1:continuity",
        run_id="run-1",
        chapter_id="chapter-1",
        chapter_version_id="chapter-1-v1",
        role="continuity",
        required=True,
        binding=ProviderBinding(
            provider_profile_id="provider-primary",
            model="model-frozen",
        ),
        context={"target": "text.review.continuity"},
    )

    result = await RegistryNarrativeProviderGateway(registry).review_chapter(  # type: ignore[arg-type]
        request
    )

    assert result.payload["role"] == "continuity"
    call = provider.calls[0]
    assert call["task_name"] == "text.review"
    assert call["context"] == {"idempotency_key": request.operation_key}
    assert call["schema"]["properties"]["role"]["const"] == "continuity"
    assert '"const": "continuity"' in call["prompt"]
    assert "Report only violations directly evidenced" in call["prompt"]
    assert "items not required in this chapter" in call["prompt"]
    assert "blocking finding requires a direct conflict" in call["prompt"]
    assert "through dramatized choices, consequences, and behavior" in call["prompt"]
    assert "never require an explicit theme statement" in call["prompt"]


@pytest.mark.asyncio
async def test_graph_gateway_makes_a_targeted_revision_replace_conflicting_source_text() -> None:
    provider = CapturingReviewTextProvider({
        "chapter_id": "chapter-1",
        "title": "退潮的档案",
        "content": "档案系统投影仍在，冲突证据已经删除。",
        "author_status": "candidate",
    })
    registry = CapturingRegistry(provider)
    direction = "删除提前泄露的员工宿舍替换证据，保留档案系统投影。"

    await RegistryNarrativeProviderGateway(registry).generate_chapter(  # type: ignore[arg-type]
        ChapterGenerationRequest(
            operation_key="run-1:chapter-1:generate:3",
            run_id="run-1",
            chapter_id="chapter-1",
            chapter_number=1,
            binding=ProviderBinding(
                provider_profile_id="provider-primary",
                model="model-frozen",
            ),
            context={
                "material": {
                    "revision_request": {
                        "direction": direction,
                        "source_chapter": {
                            "version_id": "chapter-1-v2",
                            "content": "与修订方向冲突的旧正文。",
                        },
                    }
                }
            },
        )
    )

    prompt = provider.calls[0]["prompt"]
    assert "controlling instruction" in prompt
    assert "immutable draft to replace" in prompt
    assert "rewrite or remove every source passage" in prompt
    assert direction in prompt
    assert prompt.rstrip().endswith(direction)
    assert set(provider.calls[0]["schema"]["properties"]) == {
        "chapter_id",
        "title",
        "content",
        "author_status",
    }
    assert "version_id" not in provider.calls[0]["schema"]["properties"]


def test_chapter_provider_draft_excludes_runtime_owned_version_id() -> None:
    with pytest.raises(ValidationError):
        ChapterDraftResult.model_validate({
            "chapter_id": "chapter-1",
            "version_id": "provider-owned-version",
            "title": "退潮的档案",
            "content": "正文。",
            "author_status": "candidate",
        })


@pytest.mark.asyncio
async def test_graph_gateway_evidence_contract_derives_offsets_outside_the_provider_schema() -> None:
    provider = CapturingReviewTextProvider({
        "claims": [{
            "kind": "summary",
            "claim": "林溯决定前往旧港。",
            "span_ids": ["span-0002"],
        }]
    })
    registry = CapturingRegistry(provider)

    await RegistryNarrativeProviderGateway(registry).extract_chapter_evidence(  # type: ignore[arg-type]
        ChapterEvidenceRequest(
            operation_key="run-1:chapter-1:evidence:chapter-1-v1-accepted",
            run_id="run-1",
            chapter_id="chapter-1",
            chapter_version_id="chapter-1-v1-accepted",
            content="潮水正在上涨。\n我必须在那之前，回到旧港。",
            binding=ProviderBinding(
                provider_profile_id="provider-primary",
                model="model-frozen",
            ),
        )
    )

    call = provider.calls[0]
    claim_schema = call["schema"]["$defs"]["EvidenceClaimProposal"]["properties"]
    assert set(claim_schema) == {"kind", "claim", "span_ids"}
    assert "Do not copy quote text" in call["prompt"]
    assert '"span_id": "span-0002"' in call["prompt"]


def test_evidence_candidates_keep_repeated_text_as_distinct_exact_spans() -> None:
    content = "潮水上涨。\n潮水上涨。"

    candidates = build_chapter_evidence_candidates(content)

    assert [(item.span_id, item.start, item.end, item.quote) for item in candidates] == [
        ("span-0001", 0, 5, "潮水上涨。"),
        ("span-0002", 6, 11, "潮水上涨。"),
    ]


@pytest.mark.parametrize(
    ("span_ids", "message"),
    [
        (["span-9999"], "unknown source span"),
        (["span-0001", "span-0001"], "repeats one source span"),
    ],
)
def test_evidence_binding_rejects_invalid_candidate_ids(
    span_ids: list[str],
    message: str,
) -> None:
    result = ChapterEvidenceResult.model_validate({
        "claims": [{
            "kind": "summary",
            "claim": "潮水正在上涨。",
            "span_ids": span_ids,
        }]
    })

    with pytest.raises(ValueError, match=message):
        _bind_evidence_spans("潮水正在上涨。", result)


@pytest.mark.asyncio
async def test_graph_gateway_rejects_a_review_role_outside_its_frozen_lane() -> None:
    provider = CapturingReviewTextProvider(
        ChapterReviewResult(role="character").model_dump(mode="json")
    )
    registry = CapturingRegistry(provider)
    operation_key = "run-1:chapter-1:review:chapter-1-v1:continuity"

    with pytest.raises(ProviderOperationError, match="frozen lane") as raised:
        await RegistryNarrativeProviderGateway(registry).review_chapter(  # type: ignore[arg-type]
            ChapterReviewRequest(
                operation_key=operation_key,
                run_id="run-1",
                chapter_id="chapter-1",
                chapter_version_id="chapter-1-v1",
                role="continuity",
                required=True,
                binding=ProviderBinding(
                    provider_profile_id="provider-primary",
                    model="model-frozen",
                ),
                context={"target": "text.review.continuity"},
            )
        )

    assert raised.value.operation_key == operation_key
    assert raised.value.usage == provider.last_usage
    assert raised.value.diagnostic == provider.last_response_diagnostic


def test_provider_binding_rejects_inherit_and_unknown_fallback_fields() -> None:
    with pytest.raises(ValidationError, match="explicit profile"):
        ProviderBinding(provider_profile_id="inherit", model="model")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProviderBinding.model_validate({
            "provider_profile_id": "provider-primary",
            "model": "model",
            "fallback_targets": [{"provider_profile_id": "provider-backup"}],
        })


@pytest.mark.asyncio
async def test_graph_gateway_applies_the_frozen_image_binding_without_switching() -> None:
    provider = CapturingImageProvider()
    registry = CapturingImageRegistry(provider)
    binding = CoverAssetBinding(
        provider_profile_id="image-primary",
        model="image-frozen",
        candidate_count=3,
        size="1024x1536",
        quality="high",
        timeout_seconds=91,
    )

    result = await RegistryNarrativeProviderGateway(registry).generate_cover_image(  # type: ignore[arg-type]
        CoverImageRequest(
            operation_key="run-1:cover:image:1:candidate:2",
            run_id="run-1",
            candidate_index=2,
            generation_attempt=1,
            binding=binding,
            prompt="literary cover",
        )
    )

    assert result.content == b"image"
    assert registry.provider_ids == ["image-primary"]
    assert provider.calls == [{
        "prompt": "literary cover",
        "context": {
            "idempotency_key": "run-1:cover:image:1:candidate:2",
            "model": "image-frozen",
            "size": "1024x1536",
            "quality": "high",
            "timeout_seconds": 91,
        },
    }]
