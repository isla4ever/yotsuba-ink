from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from novel_workflow.memory.story_bible_read_model import (
    StoryBibleCursorInvalid,
    StoryBibleCursorStale,
)


router = APIRouter(prefix="/api/runs", tags=["story-bible"])


@router.get("/{run_id}/story-bible")
def get_story_bible(
    request: Request,
    run_id: str,
    section: Literal["facts", "foreshadow"] = "facts",
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
) -> dict[str, object]:
    stores = request.app.state.narrative_stores
    if not stores.runs.exists(run_id):
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    try:
        stores.runs.definition(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "run_contract_retired",
                "message": "该运行不符合当前生产合同，已从主线历史中隔离。",
            },
        ) from exc
    try:
        projection = stores.story_bible.page(
            run_id,
            section=section,
            limit=limit,
            cursor=cursor,
        )
    except StoryBibleCursorStale as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "story_bible_cursor_stale",
                "message": "故事事实已更新，请从第一页重新读取。",
            },
        ) from exc
    except StoryBibleCursorInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "story_bible_cursor_invalid",
                "message": "故事圣经分页位置无效。",
            },
        ) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "story_bible_projection_invalid",
                "message": "故事圣经投影存在损坏或不完整来源，当前只读页面已暂停展示。",
            },
        ) from exc
    return projection.model_dump(mode="json")


__all__ = ["router"]
