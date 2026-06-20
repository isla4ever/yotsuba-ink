from __future__ import annotations

from fastapi import APIRouter, Request

from novel_workflow.workflows.schemas import WorkflowDefinition
from novel_workflow.workflows.templates import default_workflow


router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
async def list_workflows(request: Request) -> list[WorkflowDefinition]:
    return [WorkflowDefinition.model_validate(item) for item in request.app.state.workflow_store.list()]


@router.post("")
async def save_workflow(request: Request, workflow: WorkflowDefinition) -> WorkflowDefinition:
    request.app.state.workflow_store.write(workflow.id, workflow.model_dump())
    return workflow


@router.get("/default")
async def get_default_workflow(request: Request) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(request.app.state.workflow_store.read(default_workflow().id))
