from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
    Phase32CreationConflict,
    Phase32CreationError,
)
from novel_workflow.workflows.phase32_creation_catalog import route_catalog
from novel_workflow.workflows.phase32_creation_wizard import (
    CreationIntent,
    WorkflowSelection,
    official_workflow_catalog,
    recommend_workflows,
    resolve_workflow_selection,
)


router = APIRouter(prefix="/api/creation-wizard", tags=["creation-wizard"])


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: CreationIntent


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: WorkflowSelection


@router.get("/catalog")
async def get_creation_wizard_catalog() -> dict[str, Any]:
    entries = official_workflow_catalog()
    return {
        "routes": list(route_catalog()),
        "workflow_catalog": [entry.model_dump(mode="json") for entry in entries],
    }


@router.post("/recommend")
async def recommend_creation_workflows(
    request: Request,
    payload: RecommendRequest,
) -> dict[str, Any]:
    entries = official_workflow_catalog()
    recommendations = recommend_workflows(payload.intent, entries)
    return {
        "creation_route_id": payload.intent.creation_route_id,
        "scale_profile": payload.intent.scale_profile().model_dump(mode="json"),
        "recommendations": [item.model_dump(mode="json") for item in recommendations],
    }


@router.post("/resolve")
async def resolve_creation_workflow(
    request: Request,
    payload: ResolveRequest,
) -> dict[str, Any]:
    entries = official_workflow_catalog()
    try:
        resolved = resolve_workflow_selection(payload.selection, entries)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "creation_route_id": payload.selection.intent.creation_route_id,
        "scale_profile": payload.selection.intent.scale_profile().model_dump(mode="json"),
        "selection": resolved.model_dump(mode="json"),
        "selection_kind": "existing",
    }


def _prepared_payload(prepared) -> dict[str, Any]:
    """Project the frozen definition and read model without exposing secrets."""

    definition = prepared.record.definition
    return {
        "reused": prepared.reused,
        "preparation": prepared.preparation.model_dump(mode="json"),
        "definition": definition.model_dump(mode="json"),
        "read_model": prepared.record.read_model.model_dump(mode="json"),
    }


@router.post("/prepare")
async def prepare_creation_run(
    payload: CreationPreparationRequest,
) -> None:
    """Reject the retired pre-Project writer after the Phase 32 cutover."""

    raise HTTPException(
        status_code=410,
        detail={
            "code": "phase32_project_creation_required",
            "message": "Create Phase 32 work through POST /api/projects.",
        },
    )


@router.get("/preparations/{idempotency_key}")
async def read_creation_preparation(
    request: Request,
    idempotency_key: str,
) -> dict[str, Any]:
    """Read a prepared Run or report an interrupted reservation explicitly."""

    try:
        prepared = request.app.state.phase32_creation_service.read(idempotency_key)
    except Phase32CreationConflict as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    except Phase32CreationError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": str(exc)}) from exc
    return _prepared_payload(prepared)


__all__ = ["router"]
