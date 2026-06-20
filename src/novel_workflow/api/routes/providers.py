from __future__ import annotations

from fastapi import APIRouter, Request

from novel_workflow.api.state import list_provider_profiles
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.workflows.schemas import ProviderProfile


router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
async def list_providers(request: Request) -> list[ProviderProfile]:
    return list_provider_profiles(request.app)


@router.post("")
async def save_provider(request: Request, provider: ProviderProfile) -> ProviderProfile:
    request.app.state.provider_store.write(provider.id, provider.model_dump())
    request.app.state.providers = ProviderRegistry.from_profiles(list_provider_profiles(request.app))
    return provider


@router.post("/test")
async def test_provider(provider: ProviderProfile) -> dict[str, object]:
    return {
        "ok": provider.enabled,
        "provider_id": provider.id,
        "kind": provider.kind,
        "message": "本地演示通道可用" if provider.kind in {"mock", "image-mock"} else "配置已保存；真实连通性将在运行阶段验证",
    }
