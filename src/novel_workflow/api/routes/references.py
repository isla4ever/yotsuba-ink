from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.references import ReferenceSearchRequest, ReferenceSearchResponse, ReferenceUploadRequest


router = APIRouter(prefix="/api/references", tags=["references"])


@router.post("/search")
async def search_references(request: Request, payload: ReferenceSearchRequest) -> ReferenceSearchResponse:
    try:
        return request.app.state.reference_search.search(payload)
    except Exception as exc:
        return ReferenceSearchResponse(enabled=False, message=f"联网搜索暂不可用：{exc}", results=[])


@router.post("/upload")
async def upload_reference(request: Request, payload: ReferenceUploadRequest) -> dict[str, object]:
    return request.app.state.reference_store.create(payload).model_dump()


@router.get("/{reference_id}")
async def get_reference(request: Request, reference_id: str) -> dict[str, object]:
    try:
        return request.app.state.reference_store.read(reference_id).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown reference: {reference_id}") from exc
