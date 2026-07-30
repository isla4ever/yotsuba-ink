from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from pydantic import BaseModel, Field

from novel_workflow.api.bootstrap import list_provider_profiles, refresh_provider_registry
from novel_workflow.providers.errors import ProviderResponseError, public_provider_failure
from novel_workflow.providers.lifecycle import assign_global_default, provider_deletion_references
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from novel_workflow.providers.readiness import ProviderReadinessReport, live_provider_readiness_report
from novel_workflow.providers.stage_probe import StageProbeResult, probe_structured_stage
from novel_workflow.providers.templates import ProviderTemplate, list_provider_templates, require_provider_template
from novel_workflow.workflows.schemas import ProviderKind, ProviderProfile, WorkflowDefinition
from novel_workflow.workflows.templates import materialize_workflow_for_execution


router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderPublicProfile(ProviderProfile):
    has_saved_secret: bool = False
    has_env_secret: bool = False


class ProviderSecretRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ProviderTestRequest(BaseModel):
    provider: ProviderProfile
    api_key: str = ""
    prompt: str = "你好，请用一句话回复。"


class ProviderTestResult(BaseModel):
    ok: bool
    provider_id: str
    kind: str
    model: str = ""
    error_code: str = ""
    message: str
    response_preview: str = ""


class ProviderStageProbeRequest(BaseModel):
    provider_id: str = "openai-compatible"
    stage_id: str = "info"
    api_key: str = ""
    inputs: dict[str, object] = Field(default_factory=dict)
    max_tokens: Optional[int] = Field(default=None, ge=256, le=6000)


class ProviderReadinessRequest(BaseModel):
    workflow_id: str = "default-novel-workflow"


class ProviderDefaultRequest(BaseModel):
    provider_id: str = Field(min_length=1)
    kind: ProviderKind


@router.get("")
async def list_providers(request: Request) -> list[ProviderPublicProfile]:
    secret_store = request.app.state.provider_secret_store
    return [
        ProviderPublicProfile(
            **profile.model_dump(),
            has_saved_secret=secret_store.has_api_key(profile.id),
            has_env_secret=bool(profile.api_key_env and os.environ.get(profile.api_key_env)),
        )
        for profile in list_provider_profiles(request.app)
    ]


@router.get("/templates")
async def provider_templates() -> list[ProviderTemplate]:
    return list_provider_templates()


@router.post("")
async def save_provider(request: Request, provider: ProviderProfile) -> ProviderProfile:
    try:
        require_provider_template(provider.template_id, provider.kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        existing = ProviderProfile.model_validate(request.app.state.provider_store.read(provider.id))
    except FileNotFoundError:
        existing = None
    if existing is not None and existing.kind != provider.kind:
        references = provider_deletion_references(existing, _stored_workflows(request))
        if references:
            raise HTTPException(
                status_code=409,
                detail=_provider_in_use_message("不能更改仍被使用的 Provider 类型", references),
            )
    request.app.state.provider_store.write(provider.id, provider.model_dump())
    refresh_provider_registry(request.app)
    return provider


@router.post("/default")
async def set_default_provider(request: Request, payload: ProviderDefaultRequest) -> list[ProviderProfile]:
    profiles = list_provider_profiles(request.app)
    try:
        updated = assign_global_default(profiles, provider_id=payload.provider_id, kind=payload.kind)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {payload.provider_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.app.state.provider_store.write_many({profile.id: profile.model_dump() for profile in updated})
    refresh_provider_registry(request.app)
    return updated


@router.delete("/{provider_id}")
async def delete_provider(request: Request, provider_id: str) -> dict[str, object]:
    provider = _provider_or_404(request.app, provider_id)
    references = provider_deletion_references(provider, _stored_workflows(request))
    if references:
        raise HTTPException(
            status_code=409,
            detail=_provider_in_use_message("接口仍被工作流使用，无法删除", references),
        )
    request.app.state.provider_store.delete(provider_id)
    try:
        request.app.state.provider_secret_store.delete_api_key(provider_id)
    except Exception as exc:
        request.app.state.provider_store.write(provider.id, provider.model_dump())
        raise HTTPException(status_code=500, detail="Provider 删除失败，原配置已恢复") from exc
    refresh_provider_registry(request.app)
    return {"ok": True, "provider_id": provider_id}


@router.post("/{provider_id}/secret")
async def save_provider_secret(request: Request, provider_id: str, payload: ProviderSecretRequest) -> dict[str, object]:
    _ensure_provider_exists(request.app, provider_id)
    request.app.state.provider_secret_store.set_api_key(provider_id, payload.api_key)
    refresh_provider_registry(request.app)
    return {"ok": True, "provider_id": provider_id, "has_saved_secret": True}


@router.delete("/{provider_id}/secret")
async def delete_provider_secret(request: Request, provider_id: str) -> dict[str, object]:
    _ensure_provider_exists(request.app, provider_id)
    request.app.state.provider_secret_store.delete_api_key(provider_id)
    refresh_provider_registry(request.app)
    return {"ok": True, "provider_id": provider_id, "has_saved_secret": False}


@router.post("/test")
async def test_provider(request: Request, payload: ProviderTestRequest) -> ProviderTestResult:
    provider = payload.provider
    if not provider.enabled:
        return ProviderTestResult(ok=False, provider_id=provider.id, kind=provider.kind, error_code="provider_disabled", message="Provider 未启用")
    api_key = _resolve_api_key(request, provider, payload.api_key)
    if not provider.base_url.strip() or not provider.default_model.strip() or not api_key:
        return ProviderTestResult(
            ok=False,
            provider_id=provider.id,
            kind=provider.kind,
            error_code="provider_incomplete",
            message="请先填写 Base URL 和模型，并保存 API Key 或配置环境变量",
        )
    if provider.kind == "openai-compatible-image":
        image_provider = OpenAICompatibleImageProvider.from_profile(
            base_url=provider.base_url,
            api_key=api_key,
            model=provider.default_model,
            timeout_seconds=30,
            template_id=provider.template_id,
        )
        if image_provider is None:
            raise HTTPException(status_code=400, detail="图片 Provider 配置不完整")
        try:
            await image_provider.probe()
        except ProviderResponseError as exc:
            return _provider_test_failure(provider, exc)
        except Exception as exc:
            return _provider_test_failure(provider, exc)
        return ProviderTestResult(
            ok=True,
            provider_id=provider.id,
            kind=provider.kind,
            model=provider.default_model,
            message="图片接口鉴权检查通过，未产生图片费用",
        )
    model = OpenAICompatibleTextProvider.from_profile(
        base_url=provider.base_url,
        api_key=api_key,
        model=provider.default_model,
        temperature=0,
        max_tokens=32,
        timeout_seconds=30,
        template_id=provider.template_id,
    )
    if model is None:
        raise HTTPException(status_code=400, detail="Provider 配置不完整")
    try:
        text = await model.generate_text(payload.prompt, task_name="provider_smoke_test", context={})
    except ProviderResponseError as exc:
        return _provider_test_failure(provider, exc)
    except Exception as exc:
        return _provider_test_failure(provider, exc)
    return ProviderTestResult(
        ok=True,
        provider_id=provider.id,
        kind=provider.kind,
        model=provider.default_model,
        message="真实模型连通性测试通过",
        response_preview=text[:160],
    )


@router.post("/readiness")
async def provider_readiness(request: Request, payload: ProviderReadinessRequest) -> ProviderReadinessReport:
    try:
        workflow = WorkflowDefinition.model_validate(request.app.state.workflow_store.read(payload.workflow_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {payload.workflow_id}") from exc
    workflow.provider_profiles = list_provider_profiles(request.app)
    workflow = materialize_workflow_for_execution(workflow)
    return live_provider_readiness_report(
        workflow,
        secret_resolver=request.app.state.provider_secret_store.get_api_key,
    )


@router.post("/stage-probe")
async def probe_provider_stage(request: Request, payload: ProviderStageProbeRequest) -> StageProbeResult:
    profile = _provider_or_404(request.app, payload.provider_id)
    if profile.kind != "openai-compatible":
        return StageProbeResult(ok=False, provider_id=profile.id, stage_id=payload.stage_id, stage_type="", error_code="unsupported_provider", message="结构化阶段探针仅支持 OpenAI-compatible 文本模型")
    api_key = _resolve_api_key(request, profile, payload.api_key)
    if not profile.base_url.strip() or not profile.default_model.strip() or not api_key:
        return StageProbeResult(ok=False, provider_id=profile.id, stage_id=payload.stage_id, stage_type="", error_code="provider_incomplete", message="请先填写 Base URL 和模型，并保存 API Key 或配置环境变量")
    return await probe_structured_stage(profile, api_key=api_key, stage_id=payload.stage_id, inputs=payload.inputs, max_tokens=payload.max_tokens)


def _ensure_provider_exists(app, provider_id: str) -> None:
    if not any(profile.id == provider_id for profile in list_provider_profiles(app)):
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")


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


def _provider_test_failure(provider: ProviderProfile, error: Exception) -> ProviderTestResult:
    failure = public_provider_failure(error)
    return ProviderTestResult(
        ok=False,
        provider_id=provider.id,
        kind=provider.kind,
        model=provider.default_model,
        error_code=failure.code,
        message=failure.message,
    )


def _stored_workflows(request: Request) -> list[WorkflowDefinition]:
    return [WorkflowDefinition.model_validate(item) for item in request.app.state.workflow_store.list()]


def _provider_in_use_message(prefix: str, references: list[str]) -> str:
    visible = "；".join(references[:3])
    if len(references) > 3:
        visible += f"；另有 {len(references) - 3} 处引用"
    return f"{prefix}：{visible}。请先更换全局默认和阶段分配。"
