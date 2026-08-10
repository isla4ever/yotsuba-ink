from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from novel_workflow.output_contracts.artifacts_vnext import stage_pointer


router = APIRouter(prefix="/api/runs", tags=["run-history"])


@router.get("/history")
async def list_run_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    project_id: str = Query(default="", max_length=240),
    status: str = Query(default="", max_length=64),
) -> dict[str, object]:
    repository = request.app.state.narrative_stores.runs
    items = []
    for projection in repository.list():
        if project_id and projection.project_id != project_id:
            continue
        definition = repository.definition(projection.run_id)
        completed = [stage for stage, value in projection.stage_status.items() if value == "completed"]
        exports = request.app.state.narrative_stores.exports.list(projection.run_id)
        items.append({
            "run_id": projection.run_id,
            "project_id": projection.project_id,
            "title": str(definition.inputs.get("title") or "未命名小说"),
            "quality_mode": definition.quality_mode,
            "status": projection.status,
            "current_stage": stage_pointer(projection.active_stage_id),
            "completed_stage_ids": completed,
            "created_at": definition.created_at,
            "updated_at": projection.updated_at,
            "completed_at": projection.updated_at if projection.status == "completed" else "",
            "words": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0,
            "summary": "LangGraph 运行读模型",
            "can_branch": projection.status == "awaiting_decision" and bool(projection.checkpoint_id and projection.pending_decisions),
            "checkpoint_id": projection.checkpoint_id,
            "export_ready": "export" in completed,
            "export_count": len(exports),
            "latest_export": exports[0].model_dump(mode="json") if exports else None,
        })
    if status:
        items = [item for item in items if item.get("status") == status]
    return {"items": items[:limit], "next_cursor": ""}


@router.get("/{run_id}/exports")
async def list_run_exports(request: Request, run_id: str) -> dict[str, object]:
    stores = request.app.state.narrative_stores
    if not stores.runs.exists(run_id):
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return {
        "run_id": run_id,
        "items": [record.model_dump(mode="json") for record in stores.exports.list(run_id)],
        "capabilities": {"download": True},
    }


@router.get("/{run_id}/exports/{export_id}")
async def download_run_export(request: Request, run_id: str, export_id: str) -> Response:
    stores = request.app.state.narrative_stores
    if not stores.runs.exists(run_id):
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    try:
        record, content = stores.exports.content(run_id, export_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Unknown export") from exc
    disposition = (
        'attachment; filename="yotsuba-ink-export.'
        f'{record.format}"; filename*=UTF-8\'\'{quote(record.filename)}'
    )
    return Response(
        content=content,
        media_type=record.media_type,
        headers={
            "Content-Disposition": disposition,
            "X-Export-Sha256": record.sha256,
        },
    )


__all__ = ["router"]
