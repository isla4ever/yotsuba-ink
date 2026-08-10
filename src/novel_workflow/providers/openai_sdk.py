from __future__ import annotations

import errno
import ssl
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
    auth_header: str = "authorization",
) -> AsyncOpenAI:
    if auth_header == "api-key":
        # Leave api_key empty so the SDK does not synthesize a Bearer header.
        # MiMo authenticates this compatibility endpoint with `api-key`.
        return AsyncOpenAI(
            api_key="",
            base_url=openai_base_url(base_url),
            max_retries=max_retries,
            timeout=httpx.Timeout(120, connect=15),
            default_headers={"api-key": api_key},
            _enforce_credentials=False,
        )
    return AsyncOpenAI(
        api_key=api_key,
        base_url=openai_base_url(base_url),
        max_retries=max_retries,
        timeout=httpx.Timeout(120, connect=15),
    )


def translate_openai_error(error: Exception, *, timeout_seconds: int) -> ProviderResponseError:
    if isinstance(error, APITimeoutError):
        return ProviderResponseError(
            "timeout",
            f"Provider request timed out after {timeout_seconds}s",
            diagnostic_code=_connection_diagnostic_code(error, fallback="request_timeout"),
        )
    if isinstance(error, APIStatusError):
        return provider_http_error(error.response)
    if isinstance(error, APIConnectionError):
        return ProviderResponseError(
            "network_error",
            f"Provider network error: {error.__class__.__name__}",
            diagnostic_code=_connection_diagnostic_code(error),
        )
    if isinstance(error, APIError):
        return ProviderResponseError("response_shape_error", "Provider response is incompatible with the OpenAI SDK contract")
    return ProviderResponseError(
        "network_error",
        f"Provider request failed: {error.__class__.__name__}",
        diagnostic_code=_connection_diagnostic_code(error),
    )


def _connection_diagnostic_code(error: Exception, *, fallback: str = "connection_error") -> str:
    current: BaseException | None = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, httpx.ConnectTimeout):
            return "connect_timeout"
        if isinstance(current, httpx.ReadTimeout):
            return "read_timeout"
        if isinstance(current, httpx.WriteTimeout):
            return "write_timeout"
        if isinstance(current, httpx.PoolTimeout):
            return "connection_pool_timeout"
        if isinstance(current, httpx.ProxyError):
            return "proxy_error"
        if isinstance(current, ssl.SSLError):
            return "tls_error"
        if isinstance(current, OSError):
            if current.errno in {errno.EAI_AGAIN, errno.EAI_FAIL, errno.EAI_NONAME}:
                return "dns_error"
            if current.errno in {errno.ECONNREFUSED}:
                return "connection_refused"
            if current.errno in {errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE}:
                return "connection_reset"
            if current.errno in {errno.ETIMEDOUT}:
                return "connect_timeout"
        if isinstance(current, httpx.ConnectError):
            return "connect_error"
        next_error = current.__cause__ or current.__context__
        current = next_error if isinstance(next_error, BaseException) else None
    return fallback


def response_payload(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    dump = getattr(response, "model_dump", None)
    if callable(dump):
        payload = dump(mode="python")
        if isinstance(payload, dict):
            return payload
    raise ProviderResponseError("response_shape_error", "Provider response is not an object")
