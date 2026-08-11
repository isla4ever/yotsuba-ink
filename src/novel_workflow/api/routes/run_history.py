from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

router = APIRouter(prefix="/api/runs", tags=["run-history"])


@router.get("/history")
async def list_run_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    project_id: str = Query(default="", max_length=240),
    status: str = Query(default="", max_length=64),
) -> dict[str, object]:
    items = request.app.state.run_history.list(
        project_id=project_id,
        status=status,
        limit=limit,
    )
    return {"items": items, "next_cursor": ""}


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
