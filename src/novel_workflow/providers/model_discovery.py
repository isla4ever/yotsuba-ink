from __future__ import annotations

import re
from typing import Any

import httpx

from novel_workflow.providers.errors import ProviderResponseError, provider_http_error
from novel_workflow.providers.templates import openai_base_url, require_provider_template
from novel_workflow.workflows.schemas import ProviderProfile


MAX_DISCOVERED_MODELS = 500
MODEL_ID_MAX_LENGTH = 240
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+@-]*$")


async def discover_provider_models(
    profile: ProviderProfile,
    *,
    api_key: str,
    timeout_seconds: int = 30,
    client: httpx.AsyncClient | None = None,
) -> list[str]:
    """Read a provider model catalog without invoking text or image generation."""
    template = require_provider_template(profile.template_id, profile.kind)
    endpoint = f"{openai_base_url(profile.base_url)}{template.models_endpoint_path}"
    request_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10)),
        follow_redirects=False,
    )
    should_close = client is None
    try:
        try:
            response = await request_client.get(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise ProviderResponseError("timeout", f"Provider request timed out after {timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise ProviderResponseError("network_error", "Provider model catalog could not be reached") from exc
        if response.status_code >= 400:
            raise provider_http_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("response_json_error", "Provider model catalog is not valid JSON") from exc
        models = _extract_model_ids(payload)
        if not models:
            raise ProviderResponseError("response_shape_error", "Provider model catalog contains no usable model IDs")
        return models
    finally:
        if should_close:
            await request_client.aclose()


def merge_model_options(profile: ProviderProfile, discovered: list[str]) -> tuple[ProviderProfile, list[str]]:
    existing = list(profile.model_options)
    if profile.default_model and profile.default_model not in existing:
        existing.insert(0, profile.default_model)
    seen = set(existing)
    added: list[str] = []
    for model in discovered:
        if model not in seen:
            existing.append(model)
            seen.add(model)
            added.append(model)
    return profile.model_copy(update={"model_options": existing}), added


def _extract_model_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    candidates = payload.get("data")
    if not isinstance(candidates, list):
        candidates = payload.get("models")
    if not isinstance(candidates, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        value = _model_id(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= MAX_DISCOVERED_MODELS:
            break
    return result


def _model_id(item: Any) -> str:
    if isinstance(item, str):
        value = item.strip()
    elif isinstance(item, dict):
        value = str(item.get("id") or item.get("name") or item.get("model") or "").strip()
        if value.startswith("models/"):
            value = value.removeprefix("models/")
    else:
        return ""
    if not value or len(value) > MODEL_ID_MAX_LENGTH or MODEL_ID_PATTERN.fullmatch(value) is None:
        return ""
    return value
