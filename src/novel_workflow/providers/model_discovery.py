from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from novel_workflow.providers.errors import ProviderResponseError, provider_http_error
from novel_workflow.providers.template_contract import ProviderTemplate
from novel_workflow.providers.templates import openai_base_url, require_provider_template
from novel_workflow.workflows.schemas import ProviderProfile


MAX_DISCOVERED_MODELS = 500
MODEL_ID_MAX_LENGTH = 240
MODEL_ID_PATTERN = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9._:/+@-]*$")
PARAMETER_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,79}$")
MAX_MODEL_PARAMETERS = 128


@dataclass(frozen=True)
class ProviderModelCatalog:
    models: list[str]
    supported_parameters: dict[str, list[str]]


async def discover_provider_models(
    profile: ProviderProfile,
    *,
    api_key: str,
    timeout_seconds: int = 30,
    client: httpx.AsyncClient | None = None,
) -> list[str]:
    """Read a provider model catalog without invoking text or image generation."""
    catalog = await discover_provider_model_catalog(
        profile,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        client=client,
    )
    return catalog.models


async def discover_provider_model_catalog(
    profile: ProviderProfile,
    *,
    api_key: str,
    timeout_seconds: int = 30,
    client: httpx.AsyncClient | None = None,
) -> ProviderModelCatalog:
    """Read model IDs plus sanitized capability hints exposed by the catalog."""
    template = require_provider_template(profile.template_id, profile.kind)
    if not template.execution_allowed:
        raise ProviderResponseError("provider_policy_blocked", template.execution_policy_note or "当前 Provider 不允许用于应用后端")
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
                headers={**_catalog_auth_headers(template, api_key), "Accept": "application/json"},
                params=template.models_query_parameters,
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
        catalog = _extract_model_catalog(payload)
        if not catalog.models:
            raise ProviderResponseError("response_shape_error", "Provider model catalog contains no usable model IDs")
        return catalog
    finally:
        if should_close:
            await request_client.aclose()


def merge_model_options(
    profile: ProviderProfile,
    discovered: list[str],
    *,
    model_supported_parameters: dict[str, list[str]] | None = None,
) -> tuple[ProviderProfile, list[str]]:
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
    update: dict[str, object] = {"model_options": existing}
    if model_supported_parameters is not None:
        update["model_supported_parameters"] = model_supported_parameters
    return profile.model_copy(update=update), added


def _extract_model_ids(payload: Any) -> list[str]:
    return _extract_model_catalog(payload).models


def _extract_model_catalog(payload: Any) -> ProviderModelCatalog:
    if not isinstance(payload, dict):
        return ProviderModelCatalog(models=[], supported_parameters={})
    candidates = payload.get("data")
    if not isinstance(candidates, list):
        candidates = payload.get("models")
    if not isinstance(candidates, list):
        return ProviderModelCatalog(models=[], supported_parameters={})
    result: list[str] = []
    supported_parameters: dict[str, list[str]] = {}
    seen: set[str] = set()
    for item in candidates:
        value = _model_id(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        parameters = _supported_parameters(item)
        if parameters:
            supported_parameters[value] = parameters
        if len(result) >= MAX_DISCOVERED_MODELS:
            break
    return ProviderModelCatalog(models=result, supported_parameters=supported_parameters)


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


def _supported_parameters(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    raw_parameters = item.get("supported_parameters")
    if isinstance(raw_parameters, dict):
        candidates: Iterable[object] = raw_parameters.keys()
    elif isinstance(raw_parameters, list):
        candidates = raw_parameters
    else:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        value = str(raw).strip() if isinstance(raw, str) else ""
        if not value or value in seen or PARAMETER_NAME_PATTERN.fullmatch(value) is None:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= MAX_MODEL_PARAMETERS:
            break
    return result


def _catalog_auth_headers(template: ProviderTemplate, api_key: str) -> dict[str, str]:
    auth_header = (
        template.auth_header
        if template.models_auth_header == "inherit"
        else template.models_auth_header
    )
    if auth_header == "x-portkey-api-key":
        return {"x-portkey-api-key": api_key}
    return {"api-key": api_key} if auth_header == "api-key" else {"Authorization": f"Bearer {api_key}"}
