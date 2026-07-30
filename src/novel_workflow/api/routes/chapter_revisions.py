from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.orchestration.chapter_revision import (
    apply_chapter_selection_revision,
    generate_chapter_selection_revision,
    restore_chapter_revision_version,
)
from novel_workflow.orchestration.chapter_revision_model import ChapterRevisionError
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import (
    ChapterSelectionRevisionApplyRequest,
    ChapterSelectionRevisionRequest,
    ChapterVersionRestoreRequest,
    WorkflowDefinition,
)
from novel_workflow.workflows.templates import materialize_workflow_for_execution


router = APIRouter(prefix="/api/runs", tags=["chapter-revisions"])


@router.post("/{run_id}/chapter-selection-revisions")
async def generate_selection_revision(
    request: Request,
    run_id: str,
    payload: ChapterSelectionRevisionRequest,
) -> dict[str, object]:
    runner, workflow = _runner_and_workflow(request, run_id)
    try:
        candidate = await generate_chapter_selection_revision(
            runner, workflow, run_id=run_id, payload=payload
        )
    except ChapterRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, "candidate": candidate}


@router.post("/{run_id}/chapter-selection-revisions/apply")
async def apply_selection_revision(
    request: Request,
    run_id: str,
    payload: ChapterSelectionRevisionApplyRequest,
) -> dict[str, object]:
    runner, workflow = _runner_and_workflow(request, run_id)
    try:
        result = apply_chapter_selection_revision(
            runner, workflow, run_id=run_id, payload=payload
        )
    except ChapterRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, **result}


@router.post("/{run_id}/chapter-versions/restore")
async def restore_version(
    request: Request,
    run_id: str,
    payload: ChapterVersionRestoreRequest,
) -> dict[str, object]:
    runner, workflow = _runner_and_workflow(request, run_id)
    try:
        result = restore_chapter_revision_version(
            runner, workflow, run_id=run_id, payload=payload
        )
    except ChapterRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, **result}


def _runner_and_workflow(
    request: Request,
    run_id: str,
) -> tuple[NovelWorkflowRunner, WorkflowDefinition]:
    try:
        stored = request.app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    workflow = materialize_workflow_for_execution(
        WorkflowDefinition.model_validate(stored["workflow"])
    )
    return (
        NovelWorkflowRunner(
            providers=request.app.state.providers,
            wiki_store=request.app.state.wiki_store,
            run_store=request.app.state.run_store,
        ),
        workflow,
    )
