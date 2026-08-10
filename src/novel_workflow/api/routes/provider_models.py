from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from novel_workflow.api.bootstrap import list_provider_profiles, refresh_provider_registry
from novel_workflow.providers.errors import public_provider_failure
from novel_workflow.providers.model_discovery import discover_provider_model_catalog, merge_model_options
from novel_workflow.providers.templates import require_provider_template
from novel_workflow.workflows.schemas import ProviderKind, ProviderProfile


router = APIRouter(prefix="/api/providers", tags=["provider-models"])


class ProviderModelDiscoveryRequest(BaseModel):
    api_key: str = ""


class ProviderModelDiscoveryResult(BaseModel):
    ok: bool
    provider_id: str
    kind: ProviderKind
    models: list[str] = Field(default_factory=list)
    added_models: list[str] = Field(default_factory=list)
    model_supported_parameters: dict[str, list[str]] = Field(default_factory=dict)
    error_code: str = ""
    message: str


@router.post("/{provider_id}/models/discover")
async def discover_models(
    request: Request,
    provider_id: str,
    payload: ProviderModelDiscoveryRequest,
) -> ProviderModelDiscoveryResult:
    profile = _provider_or_404(request.app, provider_id)
    if not profile.enabled:
        return _failure(profile, "provider_disabled", "Provider 未启用")
    api_key = _resolve_api_key(request, profile, payload.api_key)
    if not profile.base_url.strip() or not api_key:
        return _failure(
            profile,
            "provider_incomplete",
            "请先填写 Base URL，并保存 API Key 或配置环境变量",
        )
    try:
        template = require_provider_template(profile.template_id, profile.kind)
    except ValueError:
        return _failure(profile, "provider_template_invalid", "厂商模板无效，请重新选择模板并保存")
    if not template.execution_allowed:
        return _failure(profile, "provider_policy_blocked", template.execution_policy_note or "当前 Provider 不允许用于应用后端")
    try:
        catalog = await discover_provider_model_catalog(profile, api_key=api_key)
    except Exception as exc:
        failure = public_provider_failure(exc)
        return _failure(profile, failure.code, failure.message)
    model_parameters = catalog.supported_parameters if template.discovers_model_parameters else {}
    updated, added = merge_model_options(
        profile,
        catalog.models,
        model_supported_parameters=model_parameters,
    )
    request.app.state.provider_store.write(updated.id, updated.model_dump())
    refresh_provider_registry(request.app)
    capability_note = "；图片生成能力仍以厂商文档和最小产物验证为准" if profile.kind == "openai-compatible-image" else ""
    if model_parameters:
        structured_count = sum(
            bool({"structured_outputs", "response_format"} & set(parameters))
            for parameters in model_parameters.values()
        )
        capability_note += f"；{structured_count} 个模型声明结构化输出参数"
    return ProviderModelDiscoveryResult(
        ok=True,
        provider_id=profile.id,
        kind=profile.kind,
        models=catalog.models,
        added_models=added,
        model_supported_parameters=model_parameters,
        message=f"已读取 {len(catalog.models)} 个上游模型，新增 {len(added)} 个候选；未触发内容生成{capability_note}。",
    )


def _provider_or_404(app, provider_id: str) -> ProviderProfile:
    for profile in list_provider_profiles(app):
        if profile.id == provider_id:
            return profile
    raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")


def _resolve_api_key(request: Request, provider: ProviderProfile, transient_key: str) -> str:
    if transient_key.strip():
        return transient_key.strip()
    saved = request.app.state.provider_secret_store.get_api_key(provider.id)
    if saved:
        return saved
    return os.environ.get(provider.api_key_env) if provider.api_key_env else ""


def _failure(provider: ProviderProfile, code: str, message: str) -> ProviderModelDiscoveryResult:
    return ProviderModelDiscoveryResult(
        ok=False,
        provider_id=provider.id,
        kind=provider.kind,
        error_code=code,
        message=message,
    )
