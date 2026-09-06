from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
    Phase32CreationConflict,
    Phase32CreationError,
    Phase32ProviderBindingError,
    Phase32WorkflowUnavailable,
)
from novel_workflow.storage.phase32_project_catalog_store import (
    Phase32ProjectCatalogError,
)
from novel_workflow.storage.phase32_run_repository import Phase32PersistenceError
from novel_workflow.storage.project_schemas import ProjectOrderRequest

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(request: Request) -> list[dict[str, object]]:
    try:
        return request.app.state.phase32_project_service.list()
    except (Phase32ProjectCatalogError, Phase32PersistenceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("")
async def create_project(
    request: Request,
    payload: CreationPreparationRequest,
) -> dict[str, object]:
    try:
        return request.app.state.phase32_project_service.create(payload)
    except Phase32CreationConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except (Phase32WorkflowUnavailable, Phase32ProviderBindingError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except (Phase32CreationError, Phase32ProjectCatalogError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.put("/order")
async def reorder_projects(
    request: Request,
    payload: ProjectOrderRequest,
) -> list[dict[str, object]]:
    try:
        return request.app.state.phase32_project_service.reorder(payload.project_ids)
    except (Phase32ProjectCatalogError, Phase32PersistenceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}")
async def get_project(request: Request, project_id: str) -> dict[str, object]:
    try:
        return request.app.state.phase32_project_service.get(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown Phase 32 Project: {project_id}") from exc
    except (Phase32ProjectCatalogError, Phase32PersistenceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{project_id}")
async def patch_project(project_id: str) -> None:
    raise HTTPException(
        status_code=405,
        detail={
            "code": "phase32_project_mutation_not_supported",
            "message": "Phase 32 Project metadata must be changed through its Artifact or archive action.",
        },
    )


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> None:
    raise HTTPException(
        status_code=405,
        detail={
            "code": "phase32_project_delete_requires_archive",
            "message": "Phase 32 Projects and Runs are immutable; use an explicit archive action.",
        },
    )
