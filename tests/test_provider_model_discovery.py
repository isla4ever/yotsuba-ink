from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from novel_workflow.providers.model_discovery import (
    ProviderModelCatalog,
    discover_provider_model_catalog,
    discover_provider_models,
    merge_model_options,
)
from novel_workflow.workflows.schemas import ProviderProfile


def _profile(**updates: object) -> ProviderProfile:
    payload: dict[str, object] = {
        "id": "provider-a",
        "name": "Provider A",
        "kind": "openai-compatible",
        "template_id": "openai-compatible-text",
        "base_url": "https://provider.example/v1/chat/completions",
        "api_key_env": "",
        "default_model": "model-default",
        "model_options": ["model-default", "manual-model"],
        "enabled": True,
    }
    payload.update(updates)
    return ProviderProfile.model_validate(payload)


@pytest.mark.asyncio
async def test_model_discovery_reads_openai_catalog_without_generation() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [
                {"id": "model-b"},
                {"id": "model-a"},
                {"id": "model-b"},
                {"id": "<script>"},
                {"id": "model\nforged"},
            ]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await discover_provider_models(_profile(), api_key="private-key", client=client)

    assert models == ["model-b", "model-a"]
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://provider.example/v1/models"
    assert requests[0].headers["authorization"] == "Bearer private-key"
    assert b"private-key" not in requests[0].content


@pytest.mark.asyncio
async def test_model_discovery_accepts_native_models_shape() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "models/gemini-flash"}, "custom-model"]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await discover_provider_models(_profile(), api_key="private-key", client=client)

    assert models == ["gemini-flash", "custom-model"]


@pytest.mark.asyncio
async def test_model_catalog_sanitizes_supported_parameter_hints() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{
            "id": "openai/gpt-5.6",
            "supported_parameters": [
                "structured_outputs",
                "response_format",
                "structured_outputs",
                "<script>",
                42,
            ],
        }]})

    profile = _profile(
        template_id="openrouter-text",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-5.6",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        catalog = await discover_provider_model_catalog(profile, api_key="private-key", client=client)

    assert catalog.models == ["openai/gpt-5.6"]
    assert catalog.supported_parameters == {
        "openai/gpt-5.6": ["structured_outputs", "response_format"],
    }


@pytest.mark.asyncio
async def test_mimo_api_model_discovery_uses_api_key_header() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.5-pro"}, {"id": "mimo-v2.5"}]})

    profile = _profile(
        template_id="xiaomi-mimo-api-text",
        base_url="https://api.xiaomimimo.com/v1",
        default_model="mimo-v2.5-pro",
        model_options=["mimo-v2.5-pro", "mimo-v2.5"],
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        models = await discover_provider_models(profile, api_key="sk-test", client=client)

    assert models == ["mimo-v2.5-pro", "mimo-v2.5"]
    assert requests[0].headers["api-key"] == "sk-test"
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_token_plan_model_discovery_is_policy_blocked() -> None:
    profile = _profile(template_id="xiaomi-mimo-text", base_url="https://token-plan-cn.xiaomimimo.com/v1")
    with pytest.raises(Exception) as raised:
        await discover_provider_models(profile, api_key="tp-test")
    assert getattr(raised.value, "code", "") == "provider_policy_blocked"


def test_model_options_merge_preserves_default_and_manual_entries() -> None:
    updated, added = merge_model_options(_profile(), ["manual-model", "live-model"])

    assert updated.default_model == "model-default"
    assert updated.model_options == ["model-default", "manual-model", "live-model"]
    assert added == ["live-model"]


def test_model_discovery_api_persists_candidates_without_creating_run(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")
    provider.update({
        "base_url": "https://private-provider.example/v1",
        "default_model": "model-default",
        "model_options": ["model-default", "manual-model"],
    })
    client.post("/api/providers", json=provider)
    client.post(f"/api/providers/{provider['id']}/secret", json={"api_key": "private-key"})

    async def fake_discovery(profile: ProviderProfile, *, api_key: str) -> ProviderModelCatalog:
        assert profile.id == provider["id"]
        assert api_key == "private-key"
        return ProviderModelCatalog(models=["model-default", "live-model"], supported_parameters={})

    monkeypatch.setattr("novel_workflow.api.routes.provider_models.discover_provider_model_catalog", fake_discovery)

    response = client.post(f"/api/providers/{provider['id']}/models/discover", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["models"] == ["model-default", "live-model"]
    assert payload["added_models"] == ["live-model"]
    assert "未触发内容生成" in payload["message"]
    refreshed = next(item for item in client.get("/api/providers").json() if item["id"] == provider["id"])
    assert refreshed["model_options"] == ["model-default", "manual-model", "live-model"]
    runs_dir = tmp_path / "runtime" / "novel_workflow" / "runs"
    assert not runs_dir.exists() or not any(runs_dir.iterdir())
    assert "private-key" not in response.text
    assert "private-provider.example" not in response.text


def test_model_discovery_api_rejects_incomplete_provider_without_external_call(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")
    called = False

    async def fake_discovery(*_: object, **__: object) -> ProviderModelCatalog:
        nonlocal called
        called = True
        return ProviderModelCatalog(models=[], supported_parameters={})

    monkeypatch.setattr("novel_workflow.api.routes.provider_models.discover_provider_model_catalog", fake_discovery)
    response = client.post(f"/api/providers/{provider['id']}/models/discover", json={})

    assert response.status_code == 200
    assert response.json()["error_code"] == "provider_incomplete"
    assert called is False


def test_transient_discovery_key_is_not_persisted(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = next(item for item in client.get("/api/providers").json() if item["kind"] == "openai-compatible")
    provider["base_url"] = "https://provider.example/v1"
    client.post("/api/providers", json=provider)

    async def fake_discovery(_: ProviderProfile, *, api_key: str) -> ProviderModelCatalog:
        assert api_key == "transient-only"
        return ProviderModelCatalog(models=["model-a"], supported_parameters={})

    monkeypatch.setattr("novel_workflow.api.routes.provider_models.discover_provider_model_catalog", fake_discovery)
    response = client.post(
        f"/api/providers/{provider['id']}/models/discover",
        json={"api_key": "transient-only"},
    )

    assert response.json()["ok"] is True
    refreshed = next(item for item in client.get("/api/providers").json() if item["id"] == provider["id"])
    assert refreshed["has_saved_secret"] is False
    assert "transient-only" not in response.text


def test_openrouter_catalog_parameters_are_server_owned_and_cleared_on_template_change(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    provider = {
        "id": "openrouter-catalog",
        "name": "OpenRouter",
        "kind": "openai-compatible",
        "template_id": "openrouter-text",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-5.6",
        "model_options": ["openai/gpt-5.6"],
        "model_supported_parameters": {"forged/model": ["structured_outputs"]},
        "enabled": True,
    }
    saved = client.post("/api/providers", json=provider).json()
    assert saved["model_supported_parameters"] == {}
    client.post(f"/api/providers/{provider['id']}/secret", json={"api_key": "private-key"})

    async def fake_discovery(_: ProviderProfile, *, api_key: str) -> ProviderModelCatalog:
        assert api_key == "private-key"
        return ProviderModelCatalog(
            models=["openai/gpt-5.6"],
            supported_parameters={"openai/gpt-5.6": ["response_format", "temperature"]},
        )

    monkeypatch.setattr(
        "novel_workflow.api.routes.provider_models.discover_provider_model_catalog",
        fake_discovery,
    )
    discovered = client.post(f"/api/providers/{provider['id']}/models/discover", json={}).json()
    assert discovered["model_supported_parameters"] == {
        "openai/gpt-5.6": ["response_format", "temperature"],
    }

    forged = client.post(
        "/api/providers",
        json={**provider, "model_supported_parameters": {"openai/gpt-5.6": ["structured_outputs"]}},
    ).json()
    assert forged["model_supported_parameters"] == discovered["model_supported_parameters"]

    switched = client.post(
        "/api/providers",
        json={
            **forged,
            "template_id": "openai-compatible-text",
            "model_supported_parameters": discovered["model_supported_parameters"],
        },
    ).json()
    assert switched["model_supported_parameters"] == {}
