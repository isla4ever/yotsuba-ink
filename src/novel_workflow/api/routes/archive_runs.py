from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request


router = APIRouter(prefix="/api/archive/runs", tags=["run-archive"])


@router.get("")
async def list_archived_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, object]:
    items = request.app.state.legacy_run_viewer.list()
    return {"items": items[:limit], "next_cursor": "", "read_only": True}


@router.get("/{run_id}")
async def get_archived_run(request: Request, run_id: str) -> dict[str, object]:
    try:
        return request.app.state.legacy_run_viewer.read(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=f"Unknown archived run: {run_id}") from exc


__all__ = ["router"]
