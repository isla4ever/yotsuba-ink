from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from novel_workflow.api.bootstrap import list_provider_profiles
from novel_workflow.orchestration.cover_asset_retry import CoverAssetRetryError, retry_cover_asset_candidate
from novel_workflow.workflows.runner import NovelWorkflowRunner
from novel_workflow.workflows.schemas import WorkflowDefinition
from novel_workflow.workflows.templates import materialize_workflow_for_execution


router = APIRouter(prefix="/api/runs", tags=["cover-assets"])


class CoverAssetRetryRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=120)
    request_id: str = Field(min_length=1, max_length=160)


@router.get("/{run_id}/cover-assets/{asset_id}")
async def get_cover_asset(request: Request, run_id: str, asset_id: str) -> Response:
    try:
        metadata, content = request.app.state.run_store.read_cover_asset(run_id, asset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="封面资产不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type=str(metadata["mime_type"]),
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{metadata["sha256"]}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{run_id}/cover-assets/retry")
async def retry_cover_asset(request: Request, run_id: str, payload: CoverAssetRetryRequest) -> dict[str, Any]:
    try:
        stored = request.app.state.run_store.read(run_id)
        workflow = WorkflowDefinition.model_validate(stored["workflow"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="运行不存在") from exc
    workflow.provider_profiles = list_provider_profiles(request.app)
    workflow = materialize_workflow_for_execution(workflow)
    runner = NovelWorkflowRunner(
        providers=request.app.state.providers,
        wiki_store=request.app.state.wiki_store,
        run_store=request.app.state.run_store,
    )
    try:
        result = await retry_cover_asset_candidate(
            runner,
            workflow,
            run_id=run_id,
            candidate_id=payload.candidate_id,
            request_id=payload.request_id,
        )
    except CoverAssetRetryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "run_id": run_id, **result}
