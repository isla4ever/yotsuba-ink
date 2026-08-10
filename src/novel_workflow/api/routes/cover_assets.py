from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response


router = APIRouter(prefix="/api/runs", tags=["cover-assets"])


def _stores(request: Request):
    return request.app.state.narrative_stores


def _require_run(request: Request, run_id: str) -> None:
    if not _stores(request).runs.exists(run_id):
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")


@router.get("/{run_id}/cover-assets")
async def list_cover_assets(request: Request, run_id: str) -> dict[str, object]:
    _require_run(request, run_id)
    records = _stores(request).cover_assets.list(run_id)
    latest_attempt = max((item.generation_attempt for item in records), default=0)
    active = [item for item in records if item.generation_attempt == latest_attempt]
    return {
        "run_id": run_id,
        "generation_attempt": latest_attempt,
        "items": [
            {
                **record.model_dump(mode="json"),
                "content_url": f"/api/runs/{run_id}/cover-assets/{record.asset_id}",
            }
            for record in active
        ],
    }


@router.get("/{run_id}/cover-assets/{asset_id}")
async def get_cover_asset(request: Request, run_id: str, asset_id: str) -> Response:
    _require_run(request, run_id)
    try:
        record, content = _stores(request).cover_assets.content(run_id, asset_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Unknown cover asset") from exc
    return Response(
        content=content,
        media_type=record.mime_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{record.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


__all__ = ["router"]
