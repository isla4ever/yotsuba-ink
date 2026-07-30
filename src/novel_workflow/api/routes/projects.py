from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.storage.project_schemas import ProjectCreateRequest, ProjectPatchRequest, ProjectRecord
from novel_workflow.storage.project_store import ProjectStoreError

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(request: Request) -> list[ProjectRecord]:
    return request.app.state.project_store.list()


@router.post("")
async def create_project(request: Request, payload: ProjectCreateRequest) -> ProjectRecord:
    try:
        return request.app.state.project_store.create(
            title=payload.title,
            summary=payload.summary,
            template_workflow_id=payload.template_workflow_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow template: {payload.template_workflow_id}") from exc


@router.get("/{project_id}")
async def get_project(request: Request, project_id: str) -> ProjectRecord:
    try:
        return request.app.state.project_store.get(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}") from exc


@router.patch("/{project_id}")
async def patch_project(request: Request, project_id: str, payload: ProjectPatchRequest) -> ProjectRecord:
    try:
        return request.app.state.project_store.patch(project_id, payload.changes())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}") from exc


@router.delete("/{project_id}")
async def delete_project(request: Request, project_id: str) -> dict[str, object]:
    try:
        request.app.state.project_store.delete(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}") from exc
    except ProjectStoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "project_id": project_id}


@router.get("/{project_id}/summary")
async def project_summary(request: Request, project_id: str) -> dict[str, object]:
    try:
        return request.app.state.project_store.summary(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_id}") from exc
