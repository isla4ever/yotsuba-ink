from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.api.dependencies import collaboration_settings_service
from novel_workflow.orchestration.collaboration_settings import (
    CollaborationSettingsError,
    CollaborationSettingsService,
)
from novel_workflow.output_contracts.author_collaboration import (
    CollaborationProviderCapability,
    CollaborationSettings,
    CollaborationSettingsEnvelope,
)


router = APIRouter(prefix="/api/collaboration", tags=["author-collaboration-settings"])


def _service(request: Request) -> CollaborationSettingsService:
    return collaboration_settings_service(request)


@router.get("/settings", response_model=CollaborationSettingsEnvelope)
def read_settings(request: Request) -> CollaborationSettingsEnvelope:
    return _service(request).read()


@router.put("/settings", response_model=CollaborationSettingsEnvelope)
def save_settings(
    request: Request,
    payload: CollaborationSettings,
) -> CollaborationSettingsEnvelope:
    try:
        return _service(request).save(payload)
    except CollaborationSettingsError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/capabilities", response_model=list[CollaborationProviderCapability])
def read_capabilities(request: Request) -> list[CollaborationProviderCapability]:
    return _service(request).capabilities()


__all__ = ["router"]
