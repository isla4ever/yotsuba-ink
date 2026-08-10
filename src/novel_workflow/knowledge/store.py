from __future__ import annotations

import math
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from novel_workflow.knowledge.chunking import chunk_document, hash_embedding, keywords
from novel_workflow.knowledge.parsing import parse_document_bytes
from novel_workflow.knowledge.redis_backend import RedisKnowledgeBackend, rewrite_query
from novel_workflow.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeUploadResponse,
)
from novel_workflow.storage.json_store import JsonStore


class KnowledgeBase:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.documents = JsonStore(root / "documents")
        self.chunks = JsonStore(root / "chunks")
        self.backend = os.getenv("KNOWLEDGE_BACKEND", "local").strip().lower()
        self.redis = RedisKnowledgeBackend() if self.backend == "redis" else None

    def upload(
        self,
        *,
        title: str,
        content: bytes,
        filename: str,
        content_type: str = "text/plain",
        project_id: str,
        source_type: str = "upload",
    ) -> KnowledgeUploadResponse:
        doc_id = f"kb-{uuid4().hex[:12]}"
        text, parser, note = parse_document_bytes(content, filename, content_type)
        chunks = chunk_document(doc_id=doc_id, project_id=project_id, title=title.strip() or filename, text=text)
        document = KnowledgeDocument(
            doc_id=doc_id,
            project_id=project_id,
            title=title.strip() or filename,
            source_type="upload",
            filename=filename,
            content_type=content_type or "application/octet-stream",
            char_count=len(text),
            chunk_count=len(chunks),
            status="indexed" if text and chunks else "partial",
            parser=parser,
            backend=self.backend_name,
            capability_note=note,
            preview=_preview(text),
            created_at=datetime.now(UTC).isoformat(),
        )
        self.documents.write(doc_id, document.model_dump())
        for chunk in chunks:
            self.chunks.write(chunk.chunk_id, chunk.model_dump())
        if self.redis and self.redis.available:
            self.redis.upsert_chunks(chunks)
        return KnowledgeUploadResponse(document=document, chunks=chunks)

    def list_documents(self, project_id: str) -> list[KnowledgeDocument]:
        documents = [KnowledgeDocument.model_validate(item) for item in self.documents.list()]
        return [item for item in documents if item.project_id == project_id]

    def read_document(self, doc_id: str) -> KnowledgeDocument:
        return KnowledgeDocument.model_validate(self.documents.read(doc_id))

    def delete_document(self, doc_id: str, project_id: str) -> dict[str, object]:
        document = self.read_document(doc_id)
        if document.project_id != project_id:
            raise FileNotFoundError(doc_id)
        deleted_chunks = 0
        self.documents.delete(doc_id)
        for chunk in list(self.chunks.list()):
            if chunk.get("doc_id") == doc_id:
                self.chunks.delete(str(chunk.get("chunk_id")))
                deleted_chunks += 1
        if self.redis:
            self.redis.delete_document(project_id, doc_id)
        backend_synced = not self.redis or self.redis.available
        return {
            "ok": True,
            "doc_id": doc_id,
            "deleted_chunks": deleted_chunks,
            "backend": self.backend_name,
            "backend_synced": backend_synced,
            "message": "知识库文档与索引已删除。" if backend_synced else self.redis.message if self.redis else "知识库文档已删除。",
        }

    def search(self, request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
        query_rewrite = rewrite_query(request.query, request.intent)
        if self.redis:
            if self.redis.available:
                results = self.redis.search(request)
                return KnowledgeSearchResponse(
                    backend="redis-hybrid",
                    backend_available=True,
                    query_rewrite=query_rewrite,
                    message="Redis hybrid 检索完成。",
                    results=results,
                )
            return KnowledgeSearchResponse(
                backend="redis-hybrid",
                backend_available=False,
                query_rewrite=query_rewrite,
                message=self.redis.message,
                results=[],
            )

        query_keywords = keywords(query_rewrite)
        query_embedding = hash_embedding(query_rewrite)
        chunks = [
            KnowledgeChunk.model_validate(item)
            for item in self.chunks.list()
            if item["project_id"] == request.project_id
        ]
        if request.doc_ids:
            allowed = set(request.doc_ids)
            chunks = [chunk for chunk in chunks if chunk.doc_id in allowed]

        scored = []
        for chunk in chunks:
            vector_score = cosine(query_embedding, chunk.embedding)
            keyword_score = overlap_score(query_keywords, chunk.keywords, chunk.text)
            score = round(vector_score * 0.58 + keyword_score * 0.42, 4)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = [
            KnowledgeSearchResult(
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                section=chunk.section,
                preview=_preview(chunk.text, 220),
                score=score,
                metadata={"index": chunk.index, "tokens_estimate": chunk.tokens_estimate},
            )
            for score, chunk in scored[: request.top_k]
        ]
        message = "本地知识库检索完成；当前使用轻量 hybrid 检索。"
        backend_available = True
        backend = "local-hybrid"
        if not results:
            message = f"{message} 知识库暂无命中。可上传 TXT/MD/HTML，或安装 Docling 后解析 PDF/DOCX 等格式。"
        return KnowledgeSearchResponse(backend=backend, backend_available=backend_available, query_rewrite=query_rewrite, message=message, results=results)

    @property
    def backend_name(self) -> str:
        if self.redis:
            return "redis-hybrid"
        return "local-hybrid"


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right[:size])) or 1.0
    return max(0.0, dot / (left_norm * right_norm))


def overlap_score(query_keywords: list[str], chunk_keywords: list[str], text: str) -> float:
    if not query_keywords:
        return 0.0
    chunk_set = set(chunk_keywords)
    hits = sum(1 for token in query_keywords if token in chunk_set or token in text)
    return min(1.0, hits / max(1, len(query_keywords)))


def _preview(content: str, limit: int = 180) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."
