from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


KnowledgeSourceType = Literal["upload", "url", "pasted_text"]
KnowledgeParseStatus = Literal["indexed", "partial", "failed"]


class KnowledgeDocument(BaseModel):
    doc_id: str
    project_id: str = "default"
    title: str
    source_type: KnowledgeSourceType = "upload"
    filename: str = ""
    content_type: str = "text/plain"
    char_count: int = 0
    chunk_count: int = 0
    status: KnowledgeParseStatus = "indexed"
    parser: str = "plain-text"
    backend: str = "local-hybrid"
    capability_note: str = ""
    preview: str = ""
    created_at: str


class KnowledgeChunk(BaseModel):
    chunk_id: str
    doc_id: str
    project_id: str = "default"
    title: str
    section: str = ""
    text: str
    index: int
    hash: str
    tokens_estimate: int
    keywords: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)


class KnowledgeUploadResponse(BaseModel):
    document: KnowledgeDocument
    chunks: list[KnowledgeChunk] = Field(default_factory=list)


class KnowledgeUploadRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    filename: str = "reference.txt"
    content_type: str = "text/plain"
    project_id: str = "default"
    encoding: Literal["plain", "base64"] = "plain"


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    intent: str = ""
    project_id: str = "default"
    doc_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=12)


class KnowledgeSearchResult(BaseModel):
    doc_id: str
    chunk_id: str
    title: str
    section: str = ""
    preview: str
    score: float
    source_type: str = "knowledge_base"
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    backend: str = "local-hybrid"
    backend_available: bool = True
    query_rewrite: str = ""
    message: str = ""
    results: list[KnowledgeSearchResult] = Field(default_factory=list)
