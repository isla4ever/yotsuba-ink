from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from novel_workflow.storage.phase32_story_bible_projection import (
    Phase32StoryBibleCursorInvalid,
    Phase32StoryBibleCursorStale,
    Phase32StoryBibleProjection,
    Phase32StoryBibleProjectionError,
    StoryBibleSection,
)


router = APIRouter(prefix="/api/runs", tags=["story-bible"])


@router.get("/{run_id}/story-bible")
def get_story_bible(
    request: Request,
    run_id: str,
    section: StoryBibleSection = "overview",
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> dict[str, object]:
    projection: Phase32StoryBibleProjection = request.app.state.phase32_story_bible
    try:
        page = projection.page(
            run_id,
            section=section,
            limit=limit,
            cursor=cursor,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown Phase 32 Run: {run_id}") from exc
    except Phase32StoryBibleCursorStale as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "message": "故事圣经来源已更新，请从第一页重新读取。",
            },
        ) from exc
    except Phase32StoryBibleCursorInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": exc.code,
                "message": "故事圣经分页位置无效。",
            },
        ) from exc
    except (Phase32StoryBibleProjectionError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": getattr(
                    exc,
                    "code",
                    "phase32_story_bible_projection_invalid",
                ),
                "message": "故事圣经投影存在损坏或不完整来源，当前只读页面已暂停展示。",
            },
        ) from exc
    return page.model_dump(mode="json")


__all__ = ["router"]
