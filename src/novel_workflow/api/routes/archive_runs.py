from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from novel_workflow.archive import (
    Phase27ArchiveArchitectureError,
    Phase27ArchiveEventPage,
    Phase27ArchiveFormatError,
    Phase27ArchiveRunDetail,
    Phase27ArchiveRunPage,
)


router = APIRouter(prefix="/api/archive/runs", tags=["run-archive"])


@router.get("", response_model=Phase27ArchiveRunPage)
async def list_archived_runs(
    request: Request,
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
) -> Phase27ArchiveRunPage:
    try:
        return request.app.state.phase27_archive_reader.list(
            cursor=cursor,
            limit=limit,
        )
    except (Phase27ArchiveArchitectureError, Phase27ArchiveFormatError) as exc:
        raise _archive_conflict(exc) from exc


@router.get("/{run_id}", response_model=Phase27ArchiveRunDetail)
async def get_archived_run(request: Request, run_id: str) -> Phase27ArchiveRunDetail:
    try:
        return request.app.state.phase27_archive_reader.read(run_id)
    except (FileNotFoundError, ValueError) as exc:
        if isinstance(exc, Phase27ArchiveFormatError):
            raise _archive_conflict(exc) from exc
        raise HTTPException(status_code=404, detail=f"Unknown archived run: {run_id}") from exc


@router.get("/{run_id}/events", response_model=Phase27ArchiveEventPage)
async def get_archived_run_events(
    request: Request,
    run_id: str,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> Phase27ArchiveEventPage:
    try:
        return request.app.state.phase27_archive_reader.events(
            run_id,
            after=after,
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        if isinstance(exc, Phase27ArchiveFormatError):
            raise _archive_conflict(exc) from exc
        raise HTTPException(status_code=404, detail=f"Unknown archived run: {run_id}") from exc


def _archive_conflict(exc: Phase27ArchiveFormatError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": exc.code, "message": str(exc)},
    )


__all__ = ["router"]
