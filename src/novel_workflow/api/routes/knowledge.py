from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.knowledge import KnowledgeSearchRequest, KnowledgeUploadRequest


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/documents/upload")
async def upload_knowledge_document(request: Request, payload: KnowledgeUploadRequest) -> dict[str, object]:
    content = payload.content.encode("utf-8")
    if payload.encoding == "base64":
        try:
            content = base64.b64decode(payload.content)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 content") from exc
    response = request.app.state.knowledge_base.upload(
        title=payload.title,
        content=content,
        filename=payload.filename,
        content_type=payload.content_type,
        project_id=payload.project_id,
    )
    return response.model_dump()


@router.get("/documents")
async def list_knowledge_documents(request: Request, project_id: str = "default") -> list[dict[str, object]]:
    return [document.model_dump() for document in request.app.state.knowledge_base.list_documents(project_id)]


@router.get("/documents/{doc_id}")
async def get_knowledge_document(request: Request, doc_id: str) -> dict[str, object]:
    try:
        return request.app.state.knowledge_base.read_document(doc_id).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown knowledge document: {doc_id}") from exc


@router.post("/search")
async def search_knowledge(request: Request, payload: KnowledgeSearchRequest) -> dict[str, object]:
    return request.app.state.knowledge_base.search(payload).model_dump()


@router.delete("/documents/{doc_id}")
async def delete_knowledge_document(request: Request, doc_id: str) -> dict[str, object]:
    return request.app.state.knowledge_base.delete_document(doc_id)
