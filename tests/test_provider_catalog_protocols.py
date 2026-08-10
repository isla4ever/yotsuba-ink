from __future__ import annotations

import httpx
import pytest

from novel_workflow.providers.model_discovery import (
    discover_provider_model_catalog,
    discover_provider_models,
)
from novel_workflow.workflows.schemas import ProviderProfile


def _profile(**updates: object) -> ProviderProfile:
    payload: dict[str, object] = {
        "id": "provider-a",
        "name": "Provider A",
        "kind": "openai-compatible",
        "template_id": "openai-compatible-text",
        "base_url": "https://provider.example/v1",
        "api_key_env": "",
        "default_model": "",
        "model_options": [],
        "enabled": True,
    }
    payload.update(updates)
    return ProviderProfile.model_validate(payload)


@pytest.mark.asyncio
async def test_openrouter_image_catalog_reads_descriptor_keys() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{
            "id": "bytedance-seed/seedream-4.5",
            "supported_parameters": {
                "resolution": {"type": "enum", "values": ["1K", "2K"]},
                "aspect_ratio": {"type": "enum", "values": ["1:1", "16:9"]},
                "<script>": {"type": "boolean"},
            },
        }]})

    profile = _profile(
        kind="openai-compatible-image",
        template_id="openrouter-image",
        base_url="https://openrouter.ai/api/v1",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        catalog = await discover_provider_model_catalog(profile, api_key="private-key", client=client)

    assert str(requests[0].url) == "https://openrouter.ai/api/v1/images/models"
    assert catalog.supported_parameters == {
        "bytedance-seed/seedream-4.5": ["resolution", "aspect_ratio"],
    }


@pytest.mark.asyncio
async def test_portkey_catalog_accepts_scoped_ids_and_uses_catalog_auth() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "@anthropic-prod/claude-sonnet"}]})

    profile = _profile(
        template_id="portkey-gateway-text",
        base_url="https://api.portkey.ai/v1",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await discover_provider_models(profile, api_key="private-key", client=client)

    assert models == ["@anthropic-prod/claude-sonnet"]
    assert requests[0].headers["x-portkey-api-key"] == "private-key"
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_siliconflow_image_catalog_filters_image_models() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "Kwai-Kolors/Kolors"}]})

    profile = _profile(
        kind="openai-compatible-image",
        template_id="siliconflow-image",
        base_url="https://api.siliconflow.cn/v1",
        default_model="Kwai-Kolors/Kolors",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await discover_provider_models(profile, api_key="private-key", client=client)

    assert models == ["Kwai-Kolors/Kolors"]
    assert requests[0].url.params["type"] == "image"
