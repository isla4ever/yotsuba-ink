from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.runtime.graph.provider_gateway import (
    CoverImageRequest,
    RegistryNarrativeProviderGateway,
    StageGenerationRequest,
)
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding
from novel_workflow.workflows.schemas import ModelSettings


class CapturingTextProvider(TextProvider):
    name = "capturing-provider"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

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

    assert result["title"] == "雾港母带"
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
