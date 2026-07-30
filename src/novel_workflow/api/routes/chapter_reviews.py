from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.orchestration.chapter_review import (
    decide_chapter_writeback,
    sync_chapter_summary_and_review,
)
from novel_workflow.orchestration.chapter_review_model import ChapterReviewError
from novel_workflow.orchestration.chapter_revision_model import ChapterRevisionError
from novel_workflow.workflows.schemas import (
    ChapterSummarySyncRequest,
    ChapterWritebackProposalDecisionRequest,
)

from .chapter_revisions import _runner_and_workflow


router = APIRouter(prefix="/api/runs", tags=["chapter-reviews"])


@router.post("/{run_id}/chapters/{chapter_id}/sync-summary")
async def sync_summary(
    request: Request,
    run_id: str,
    chapter_id: str,
    payload: ChapterSummarySyncRequest,
) -> dict[str, object]:
    if payload.chapter_id != chapter_id:
        raise HTTPException(status_code=409, detail="章节路径与请求内容不一致")
    runner, workflow = _runner_and_workflow(request, run_id)
    try:
        result = sync_chapter_summary_and_review(
            runner, workflow, run_id=run_id, payload=payload
        )
    except (ChapterReviewError, ChapterRevisionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, **result}


@router.post("/{run_id}/chapters/{chapter_id}/writeback-proposal")
async def decide_proposal(
    request: Request,
    run_id: str,
    chapter_id: str,
    payload: ChapterWritebackProposalDecisionRequest,
) -> dict[str, object]:
    if payload.chapter_id != chapter_id:
        raise HTTPException(status_code=409, detail="章节路径与请求内容不一致")
    runner, workflow = _runner_and_workflow(request, run_id)
    try:
        result = decide_chapter_writeback(
            runner, workflow, run_id=run_id, payload=payload
        )
    except (ChapterReviewError, ChapterRevisionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, **result}
