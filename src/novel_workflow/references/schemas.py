from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SearchDepth = Literal["basic", "advanced"]


class ReferenceSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=10)
    search_depth: SearchDepth = "basic"


class ReferenceSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    score: float = 0.0


class ReferenceSearchResponse(BaseModel):
    enabled: bool
    provider: str = "tavily"
    message: str = ""
    results: list[ReferenceSearchResult] = Field(default_factory=list)


class ReferenceUploadRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_type: str = "pasted_text"


class ReferenceDocument(BaseModel):
    reference_id: str
    title: str
    content: str
    preview: str
    char_count: int
    source_type: str = "pasted_text"
