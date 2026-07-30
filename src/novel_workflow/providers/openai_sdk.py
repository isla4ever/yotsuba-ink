from __future__ import annotations

from typing import Any

import httpx
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, AsyncOpenAI

from novel_workflow.providers.errors import ProviderResponseError, provider_http_error
from novel_workflow.providers.templates import openai_base_url


def create_openai_client(
    *,
    base_url: str,
    api_key: str,
    max_retries: int,
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=openai_base_url(base_url),
        max_retries=max_retries,
        timeout=httpx.Timeout(120, connect=15),
    )


def translate_openai_error(error: Exception, *, timeout_seconds: int) -> ProviderResponseError:
    if isinstance(error, APITimeoutError):
        return ProviderResponseError("timeout", f"Provider request timed out after {timeout_seconds}s")
    if isinstance(error, APIStatusError):
        return provider_http_error(error.response)
    if isinstance(error, APIConnectionError):
        return ProviderResponseError("network_error", f"Provider network error: {error.__class__.__name__}")
    if isinstance(error, APIError):
        return ProviderResponseError("response_shape_error", "Provider response is incompatible with the OpenAI SDK contract")
    return ProviderResponseError("network_error", f"Provider request failed: {error.__class__.__name__}")


def response_payload(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    dump = getattr(response, "model_dump", None)
    if callable(dump):
        payload = dump(mode="python")
        if isinstance(payload, dict):
            return payload
    raise ProviderResponseError("response_shape_error", "Provider response is not an object")
