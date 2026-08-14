from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterGenerationRequest,
    ChapterReviewRequest,
    ChapterReviewResult,
    CoverImageRequest,
    PlainTextProviderResult,
    ProposalGenerationRequest,
    ProviderOperationError,
    FrozenNarrativeProviderGateway,
    StageGenerationRequest,
    StructuredProviderResult,
)
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from tests.phase27_bindings import cover_asset_binding, provider_binding


def brief() -> dict[str, Any]:
    return {
        "title": "雾港旧声", "premise": "修复师追查母带", "promise": "真相伴随代价", "world_rules": ["广播覆盖记忆"],
        "theme": "真相的代价", "ending_promise": "真相公开", "voice": "克制", "length_envelope": {"word_target_soft": 10000, "chapter_target_soft": 2},
    }


class CapturingTextProvider(TextProvider):
    name = "capturing"

    def __init__(self, *, structured: dict[str, Any] | None = None) -> None:
        self.structured = structured or brief()
        self.calls: list[tuple[str, str]] = []

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        self.calls.append((task_name, prompt))
        return "第一章正文。"

    async def generate_strict_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((task_name, prompt))
        return self.structured


class CapturingImageProvider(ImageProvider):
    name = "image"

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        return GeneratedImage(content=b"image", mime_type="image/png", provider_asset_id="asset-1")


def binding(stage_id: str = "brief") -> ProviderBinding:
    return provider_binding(
        stage_id,
        provider_profile_id="provider-primary",
        model="model-frozen",
        max_tokens=1000,
    )


def chapter_context_manifest() -> dict[str, Any]:
    text = "chapter script"
    payload: dict[str, Any] = {
        "task": "chapter-1",
        "required": ["detail.chapter"],
        "optional": [],
        "forbidden": ["full_canon"],
        "snippets": [{
            "ref": "detail.chapter",
            "purpose": "chapter_script",
            "text": text,
            "source_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }],
        "budget": {"input_chars": len(text), "output_tokens": 100},
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload["manifest_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return payload


def gateway(
    text: TextProvider,
    *,
    image: ImageProvider | None = None,
) -> FrozenNarrativeProviderGateway:
    return FrozenNarrativeProviderGateway(
        lambda secret_ref: f"saved-secret-for-{secret_ref}",
        text_provider_factory=lambda frozen, secret: text,
        image_provider_factory=lambda frozen, secret: image or CapturingImageProvider(),
    )


@pytest.mark.asyncio
async def test_stage_gateway_uses_exact_frozen_binding_and_current_contract() -> None:
    provider = CapturingTextProvider()
    result = await gateway(provider).generate_stage(StageGenerationRequest(operation_key="run:brief:1", run_id="run", stage_id="brief", attempt=1, binding=binding(), context={"target": "brief", "material": {"project_brief": {}, "length_envelope": {}}}))
    assert result.payload["title"] == "雾港旧声"
    assert provider.calls[0][0] == "brief"


@pytest.mark.asyncio
async def test_stage_gateway_rejects_invalid_json_shape_without_repair() -> None:
    provider = CapturingTextProvider(structured={"title": "missing"})
    with pytest.raises(ProviderOperationError):
        await gateway(provider).generate_stage(StageGenerationRequest(operation_key="run:brief:1", run_id="run", stage_id="brief", attempt=1, binding=binding(), context={"target": "brief", "material": {"project_brief": {}, "length_envelope": {}}}))


@pytest.mark.asyncio
async def test_schema_digest_drift_stops_before_secret_or_provider_resolution() -> None:
    frozen = binding()
    structured_tasks = dict(frozen.structured_tasks)
    structured_tasks["brief"] = structured_tasks["brief"].model_copy(
        update={"schema_digest": "0" * 64}
    )
    drifted = frozen.model_copy(update={"structured_tasks": structured_tasks})
    secret_calls: list[str] = []
    factory_calls: list[tuple[ProviderBinding, str]] = []

    def secret_resolver(secret_ref: str) -> str:
        secret_calls.append(secret_ref)
        return "offline-secret"

    def provider_factory(
        provider_binding: ProviderBinding,
        secret: str,
    ) -> TextProvider:
        factory_calls.append((provider_binding, secret))
        return CapturingTextProvider()

    frozen_gateway = FrozenNarrativeProviderGateway(
        secret_resolver,
        text_provider_factory=provider_factory,
    )

    with pytest.raises(ProviderOperationError) as captured:
        await frozen_gateway.generate_stage(
            StageGenerationRequest(
                operation_key="run:brief:drift",
                run_id="run",
                stage_id="brief",
                attempt=1,
                binding=drifted,
                context={
                    "target": "brief",
                    "material": {"project_brief": {}, "length_envelope": {}},
                },
            )
        )

    assert captured.value.diagnostic["code"] == "schema_digest_mismatch"
    assert secret_calls == []
    assert factory_calls == []


@pytest.mark.asyncio
async def test_chapter_gateway_is_plain_text_and_never_parses_json() -> None:
    provider = CapturingTextProvider()
    result = await gateway(provider).generate_chapter(ChapterGenerationRequest(operation_key="run:chapter-1:1", run_id="run", chapter_id="chapter-1", chapter_number=1, binding=binding("text"), context={"target": "text", "material": {"chapter_context_manifest": chapter_context_manifest()}}))
    assert isinstance(result, PlainTextProviderResult)
    assert result.content == "第一章正文。"
    assert provider.calls[0][0] == "text"


@pytest.mark.asyncio
async def test_review_gateway_locks_role_to_the_requested_lane() -> None:
    provider = CapturingTextProvider(structured=ChapterReviewResult(role="continuity").model_dump(mode="json"))
    request = ChapterReviewRequest(operation_key="run:review", run_id="run", chapter_id="chapter-1", chapter_version_id="chapter-1-v1", role="continuity", required=True, binding=binding("text"), context={"target": "text.review", "material": {"chapter": {"content": "正文"}}})
    result = await gateway(provider).review_chapter(request)
    assert result.payload["role"] == "continuity"


@pytest.mark.asyncio
async def test_character_review_finding_without_a_frozen_subject_is_rejected() -> None:
    provider = CapturingTextProvider(
        structured={
            "role": "character",
            "available": True,
            "findings": [
                {"code": "early_appearance", "severity": "blocking", "claim": "提前出场", "evidence": "王建国走进值班室", "subject_ids": []}
            ],
        }
    )
    request = ChapterReviewRequest(
        operation_key="run:review",
        run_id="run",
        chapter_id="chapter-1",
        chapter_version_id="chapter-1-v1",
        role="character",
        required=True,
        binding=binding("text"),
        context={
            "target": "text.review",
            "material": {
                "chapter": {"content": "王建国走进值班室"},
                "appearance_policy": {"eligible_subject_ids": ["subject-1"], "not_yet_eligible_subject_ids": ["subject-2"]},
            },
        },
    )
    with pytest.raises(ProviderOperationError):
        await gateway(provider).review_chapter(request)


@pytest.mark.asyncio
async def test_proposal_gateway_validates_narrow_json_contract() -> None:
    provider = CapturingTextProvider(structured={"proposals": [{"demand_key": "demand-a", "function": "取证", "required_change": "作证", "active_turn_refs": ["turn-1"]}]})
    result = await gateway(provider).generate_proposal(ProposalGenerationRequest(operation_key="run:proposal", run_id="run", proposal_type="role_demand", binding=binding("spine"), context={"target": "cast", "material": {}}))
    assert result.payload["proposals"][0]["demand_key"] == "demand-a"


@pytest.mark.asyncio
async def test_image_gateway_keeps_explicit_profile_and_binding() -> None:
    provider = CapturingImageProvider()
    request = CoverImageRequest(operation_key="run:cover:image:1", run_id="run", candidate_index=1, generation_attempt=1, binding=cover_asset_binding(provider_profile_id="image-primary", model="image-model"), prompt="封面")
    image = await gateway(CapturingTextProvider(), image=provider).generate_cover_image(request)
    assert image.provider_asset_id == "asset-1"
