from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.api.bootstrap import list_provider_profiles
from novel_workflow.workflows.schemas import WorkflowDefinition, WorkflowDuplicateRequest
from novel_workflow.workflows.templates import default_workflow, materialize_workflow_for_execution


router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
async def list_workflows(request: Request) -> list[WorkflowDefinition]:
    return [_with_live_profiles(request, item) for item in request.app.state.workflow_store.list()]


@router.post("")
async def save_workflow(request: Request, workflow: WorkflowDefinition) -> WorkflowDefinition:
    canonical = workflow.model_copy(update={"provider_profiles": list_provider_profiles(request.app)})
    request.app.state.workflow_store.write(canonical.id, canonical.model_dump())
    return canonical


@router.get("/default")
async def get_default_workflow(request: Request) -> WorkflowDefinition:
    return _with_live_profiles(request, request.app.state.workflow_store.read(default_workflow().id))


@router.get("/{workflow_id}")
async def get_workflow(request: Request, workflow_id: str) -> WorkflowDefinition:
    return _with_live_profiles(request, _read_or_404(request, workflow_id))


@router.post("/{workflow_id}/duplicate")
async def duplicate_workflow(request: Request, workflow_id: str, payload: WorkflowDuplicateRequest) -> WorkflowDefinition:
    source = _read_or_404(request, workflow_id)
    new_id = payload.new_id or f"wf-copy-{uuid4().hex[:10]}"
    try:
        request.app.state.workflow_store.read(new_id)
    except FileNotFoundError:
        pass
    else:
        raise HTTPException(status_code=409, detail=f"Workflow already exists: {new_id}")
    copied = WorkflowDefinition.model_validate({**source, "id": new_id})
    if payload.name:
        copied.name = payload.name
    if payload.is_template is not None:
        copied.is_template = payload.is_template
    request.app.state.workflow_store.write(copied.id, copied.model_dump())
    return _with_live_profiles(request, copied.model_dump())


@router.delete("/{workflow_id}")
async def delete_workflow(request: Request, workflow_id: str) -> dict[str, object]:
    if workflow_id == default_workflow().id:
        raise HTTPException(status_code=409, detail="默认工作流不可删除。")
    referencing = request.app.state.project_store.projects_referencing_workflow(workflow_id)
    if referencing:
        titles = "、".join(f"「{record.title}」" for record in referencing)
        raise HTTPException(status_code=409, detail=f"该工作流仍被作品 {titles} 使用，不可删除。")
    _read_or_404(request, workflow_id)
    request.app.state.workflow_store.delete(workflow_id)
    return {"ok": True, "workflow_id": workflow_id}


def _read_or_404(request: Request, workflow_id: str) -> dict:
    try:
        return request.app.state.workflow_store.read(workflow_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {workflow_id}") from exc


def _with_live_profiles(request: Request, raw: dict) -> WorkflowDefinition:
    workflow = WorkflowDefinition.model_validate(raw)
    workflow.provider_profiles = list_provider_profiles(request.app)
    return materialize_workflow_for_execution(workflow)
