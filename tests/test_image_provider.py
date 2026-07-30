from __future__ import annotations

import base64
import json
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI

from novel_workflow.providers.openai_compat import ProviderResponseError
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from tests.fakes import fake_png_bytes


def sdk_client(handler, *, base_url: str = "https://images.example/v1") -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="secret",
        base_url=base_url,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_openai_image_provider_returns_binary_and_sends_idempotency_key() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"url": str(request.url), "headers": dict(request.headers), "json": json.loads(request.content)})
        encoded = base64.b64encode(fake_png_bytes()).decode("ascii")
        return httpx.Response(200, json={"id": "response-1", "data": [{"b64_json": encoded}], "usage": {"cost_usd": 0.04}})

    client = sdk_client(handler)
    provider = OpenAICompatibleImageProvider("https://images.example/v1", "secret", "gpt-image-1", client=client)

    try:
        result = await provider.generate_cover("mist harbor", context={"idempotency_key": "stable-key", "size": "1024x1536", "quality": "high"})
    finally:
        await client.close()

    assert result.content == fake_png_bytes()
    assert result.mime_type == ""
    assert result.usage == {"cost_usd": 0.04}
    assert calls[0]["url"] == "https://images.example/v1/images/generations"
    assert calls[0]["headers"]["idempotency-key"] == "stable-key"
    assert calls[0]["json"]["size"] == "1024x1536"


@pytest.mark.asyncio
async def test_openai_image_provider_rejects_unsafe_asset_url() -> None:
    client = sdk_client(lambda request: httpx.Response(200, json={"data": [{"url": "http://127.0.0.1/private.png"}]}))
    provider = OpenAICompatibleImageProvider("https://images.example/v1", "secret", "gpt-image-1", client=client)

    try:
        with pytest.raises(ProviderResponseError, match="public HTTPS"):
            await provider.generate_cover("mist harbor", context={})
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tokenhub_template_uses_vendor_image_contract() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        encoded = base64.b64encode(fake_png_bytes()).decode("ascii")
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    client = sdk_client(handler)
    provider = OpenAICompatibleImageProvider(
        "https://tokenhub.tencentmaas.com/v1",
        "secret",
        "hy-image-v3.0",
        template_id="tokenhub-hunyuan-image",
        client=client,
    )
    try:
        await provider.generate_cover("mist harbor", context={"size": "1024x1536", "quality": "high"})
    finally:
        await client.close()

    assert calls[0] == {
        "model": "hy-image-v3.0",
        "prompt": "mist harbor",
        "size": "1024:1536",
        "images": 1,
    }


@pytest.mark.asyncio
async def test_siliconflow_template_uses_custom_fields_and_response_collection() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"url": str(request.url), "body": json.loads(request.content)})
        encoded = base64.b64encode(fake_png_bytes()).decode("ascii")
        return httpx.Response(200, json={"images": [{"b64_json": encoded}]})

    client = sdk_client(handler, base_url="https://api.siliconflow.cn/v1")
    provider = OpenAICompatibleImageProvider(
        "https://api.siliconflow.cn/v1",
        "secret",
        "Kwai-Kolors/Kolors",
        template_id="siliconflow-image",
        client=client,
    )
    try:
        result = await provider.generate_cover("mist harbor", context={"size": "1024x1536", "quality": "high"})
    finally:
        await client.close()

    assert result.content == fake_png_bytes()
    assert calls[0] == {
        "url": "https://api.siliconflow.cn/v1/images/generations",
        "body": {
            "model": "Kwai-Kolors/Kolors",
            "prompt": "mist harbor",
            "image_size": "1024x1536",
        },
    }


@pytest.mark.asyncio
async def test_openrouter_template_uses_dedicated_image_endpoint() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"url": str(request.url), "body": json.loads(request.content)})
        encoded = base64.b64encode(fake_png_bytes()).decode("ascii")
        return httpx.Response(200, json={"data": [{"b64_json": encoded, "media_type": "image/png"}]})

    client = sdk_client(handler, base_url="https://openrouter.ai/api/v1")
    provider = OpenAICompatibleImageProvider(
        "https://openrouter.ai/api/v1",
        "secret",
        "image-model",
        template_id="openrouter-image",
        client=client,
    )
    try:
        result = await provider.generate_cover("mist harbor", context={"size": "1024x1536", "quality": "medium"})
    finally:
        await client.close()

    assert result.content == fake_png_bytes()
    assert calls[0] == {
        "url": "https://openrouter.ai/api/v1/images",
        "body": {
            "model": "image-model",
            "prompt": "mist harbor",
            "resolution": "1024x1536",
            "n": 1,
            "quality": "medium",
        },
    }


@pytest.mark.asyncio
async def test_xai_template_maps_dimensions_to_aspect_ratio() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        encoded = base64.b64encode(fake_png_bytes()).decode("ascii")
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    client = sdk_client(handler, base_url="https://api.x.ai/v1")
    provider = OpenAICompatibleImageProvider(
        "https://api.x.ai/v1",
        "secret",
        "grok-imagine-image",
        template_id="xai-image",
        client=client,
    )
    try:
        result = await provider.generate_cover("mist harbor", context={"size": "1024x1536", "quality": "high"})
    finally:
        await client.close()

    assert result.content == fake_png_bytes()
    assert calls[0] == {
        "model": "grok-imagine-image",
        "prompt": "mist harbor",
        "aspect_ratio": "2:3",
        "n": 1,
        "resolution": "1k",
        "response_format": "b64_json",
    }


@pytest.mark.asyncio
async def test_together_template_sends_width_height_and_base64_contract() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        encoded = base64.b64encode(fake_png_bytes()).decode("ascii")
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    client = sdk_client(handler, base_url="https://api.together.ai/v1")
    provider = OpenAICompatibleImageProvider(
        "https://api.together.ai/v1",
        "secret",
        "google/imagen-4.0-fast",
        template_id="together-image",
        client=client,
    )
    try:
        result = await provider.generate_cover("mist harbor", context={"size": "1024:1536", "quality": "high"})
    finally:
        await client.close()

    assert result.content == fake_png_bytes()
    assert calls[0] == {
        "model": "google/imagen-4.0-fast",
        "prompt": "mist harbor",
        "width": 1024,
        "height": 1536,
        "n": 1,
        "response_format": "base64",
        "output_format": "png",
    }
