from __future__ import annotations

from typing import Any

import httpx
import pytest
import requests
from openai import AsyncOpenAI

from novel_workflow.providers.errors import ProviderResponseError, provider_http_error, public_provider_failure
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from novel_workflow.providers.stage_probe import probe_structured_stage
from novel_workflow.workflows.schemas import ProviderProfile


class FailedResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        raise requests.HTTPError("raw upstream failure", response=self)


def sdk_client(handler) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="secret",
        base_url="https://provider.example/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.parametrize(
    ("status", "payload", "expected_code", "message_fragment"),
    [
        (401, {"error": {"message": "bad key"}}, "authentication_failed", "API Key"),
        (402, {"Response": {"Error": {"Code": "INSUFFICIENT_BALANCE"}}}, "insufficient_balance", "余额"),
        (404, {"error": {"message": "missing model"}}, "endpoint_or_model_unavailable", "模型"),
        (429, {"error": {"message": "too many requests"}}, "rate_limited", "稍后重试"),
    ],
)
def test_http_failures_map_to_stable_actionable_public_errors(
    status: int,
    payload: Any,
    expected_code: str,
    message_fragment: str,
) -> None:
    error = provider_http_error(FailedResponse(status, payload))
    failure = public_provider_failure(error)

    assert error.code == expected_code
    assert error.http_status == status
    assert failure.code == expected_code
    assert message_fragment in failure.message


def test_structured_balance_reason_is_recognized_without_exposing_upstream_body() -> None:
    response = FailedResponse(
        400,
        {
            "error": {
                "code": "INSUFFICIENT_BALANCE",
                "message": "secret upstream explanation",
                "request_id": "upstream-request-id",
            }
        },
    )

    error = provider_http_error(response)

    assert error.code == "insufficient_balance"
    assert "secret upstream explanation" not in str(error)
    assert "upstream-request-id" not in str(error)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raised_error", "internal_code", "public_code"),
    [
        (httpx.ReadTimeout("slow upstream"), "timeout", "provider_timeout"),
        (httpx.ConnectError("private network detail"), "network_error", "provider_unreachable"),
    ],
)
async def test_text_provider_preserves_timeout_and_network_categories(
    monkeypatch,
    raised_error: httpx.HTTPError,
    internal_code: str,
    public_code: str,
) -> None:
    client = sdk_client(lambda request: (_ for _ in ()).throw(raised_error))
    provider = OpenAICompatibleTextProvider("https://provider.example/v1", "secret", "model-a", client=client)

    try:
        with pytest.raises(ProviderResponseError) as raised:
            await provider.generate_text("probe", task_name="provider_smoke_test", context={})
    finally:
        await client.close()

    assert raised.value.code == internal_code
    assert public_provider_failure(raised.value).code == public_code
    assert "private network detail" not in public_provider_failure(raised.value).message


@pytest.mark.asyncio
async def test_stage_probe_returns_public_compatibility_failure(monkeypatch) -> None:
    class IncompatibleProvider:
        async def generate_structured(self, *args, **kwargs):
            del args, kwargs
            raise ProviderResponseError("response_shape_error", "internal response path")

    monkeypatch.setattr(
        "novel_workflow.providers.stage_probe.OpenAICompatibleTextProvider.from_profile",
        lambda **kwargs: IncompatibleProvider(),
    )
    profile = ProviderProfile(
        id="text-provider",
        name="Text Provider",
        kind="openai-compatible",
        base_url="https://provider.example/v1",
        default_model="model-a",
    )

    result = await probe_structured_stage(profile, api_key="secret", stage_id="info", max_tokens=256)

    assert result.ok is False
    assert result.error_code == "incompatible_response"
    assert "OpenAI-compatible" in result.message
    assert "internal response path" not in result.message


@pytest.mark.asyncio
async def test_image_probe_uses_the_same_authentication_mapping() -> None:
    client = sdk_client(lambda request: httpx.Response(403, json={"error": {"message": "private upstream detail"}}))
    provider = OpenAICompatibleImageProvider("https://images.example/v1", "secret", "image-model", client=client)

    try:
        with pytest.raises(ProviderResponseError) as raised:
            await provider.probe()
    finally:
        await client.close()

    assert raised.value.code == "authentication_failed"
    assert "private upstream detail" not in str(raised.value)


def test_provider_test_api_returns_balance_code_without_sensitive_data(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from novel_workflow.api.app import create_app

    upstream_payload = {
        "error": {
            "code": "INSUFFICIENT_BALANCE",
            "message": "private upstream explanation",
            "request_id": "upstream-request-id",
        }
    }
    monkeypatch.chdir(tmp_path)
    class FailingProvider:
        async def generate_text(self, *args, **kwargs):
            del args, kwargs
            raise provider_http_error(FailedResponse(402, upstream_payload))

    monkeypatch.setattr(
        "novel_workflow.api.routes.providers.OpenAICompatibleTextProvider.from_profile",
        lambda **kwargs: FailingProvider(),
    )
    client = TestClient(create_app())
    request_payload = {
        "provider": {
            "id": "text-provider",
            "name": "Text Provider",
            "kind": "openai-compatible",
            "base_url": "https://private-provider.example/v1",
            "default_model": "model-a",
            "enabled": True,
        },
        "api_key": "private-api-key",
    }

    response = client.post("/api/providers/test", json=request_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error_code"] == "insufficient_balance"
    assert "余额" in payload["message"]
    serialized = response.text
    assert "private-api-key" not in serialized
    assert "private-provider.example" not in serialized
    assert "private upstream explanation" not in serialized
    assert "upstream-request-id" not in serialized
