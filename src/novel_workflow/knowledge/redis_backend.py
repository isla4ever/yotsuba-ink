from __future__ import annotations

import os
import math
from typing import Any

from novel_workflow.knowledge.schemas import KnowledgeChunk, KnowledgeSearchRequest, KnowledgeSearchResult
from novel_workflow.knowledge.chunking import hash_embedding, keywords


class RedisKnowledgeBackend:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: Any | None = None
        self.available, self.message = self._connect()

    def _connect(self) -> tuple[bool, str]:
        try:
            import redis  # type: ignore
        except Exception:
            return False, "未安装 redis Python 客户端，已回退本地 hybrid 检索。"
        try:
            client = redis.Redis.from_url(self.url, decode_responses=True)
            client.ping()
            self._client = client
            return True, "Redis hybrid backend 可用。"
        except Exception as exc:
            return False, f"Redis 不可用：{exc}；已回退本地 hybrid 检索。"

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not self._client:
            return
        pipe = self._client.pipeline()
        for chunk in chunks:
            key = self._key(chunk.project_id, chunk.chunk_id)
            pipe.hset(
                key,
                mapping={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "project_id": chunk.project_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "text": chunk.text,
                    "index": chunk.index,
                    "hash": chunk.hash,
                    "tokens_estimate": chunk.tokens_estimate,
                    "keywords": "\n".join(chunk.keywords),
                    "embedding": ",".join(str(value) for value in chunk.embedding),
                },
            )
            pipe.sadd(self._project_key(chunk.project_id), key)
        pipe.execute()

    def delete_document(self, project_id: str, doc_id: str) -> None:
        if not self._client:
            return
        keys = list(self._client.smembers(self._project_key(project_id)))
        for key in keys:
            if self._client.hget(key, "doc_id") == doc_id:
                self._client.delete(key)
                self._client.srem(self._project_key(project_id), key)

    def search(self, request: KnowledgeSearchRequest) -> list[KnowledgeSearchResult]:
        if not self._client:
            return []
        rewritten = rewrite_query(request.query, request.intent)
        query_keywords = keywords(rewritten)
        query_embedding = hash_embedding(rewritten)
        allowed = set(request.doc_ids)
        scored: list[tuple[float, dict[str, str]]] = []
        for key in self._client.smembers(self._project_key(request.project_id)):
            item = self._client.hgetall(key)
            if not item:
                continue
            if allowed and item.get("doc_id") not in allowed:
                continue
            chunk_keywords = str(item.get("keywords") or "").splitlines()
            embedding = [float(value) for value in str(item.get("embedding") or "").split(",") if value]
            vector_score = cosine(query_embedding, embedding)
            keyword_score = overlap_score(query_keywords, chunk_keywords, str(item.get("text") or ""))
            score = round(vector_score * 0.58 + keyword_score * 0.42, 4)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            KnowledgeSearchResult(
                doc_id=str(item.get("doc_id") or ""),
                chunk_id=str(item.get("chunk_id") or ""),
                title=str(item.get("title") or ""),
                section=str(item.get("section") or ""),
                preview=_preview(str(item.get("text") or ""), 220),
                score=score,
                metadata={"index": int(item.get("index") or 0), "tokens_estimate": int(item.get("tokens_estimate") or 0)},
            )
            for score, item in scored[: request.top_k]
        ]

    def _project_key(self, project_id: str) -> str:
        return f"novel:knowledge:{project_id}:chunks"

    def _key(self, project_id: str, chunk_id: str) -> str:
        return f"novel:knowledge:{project_id}:chunk:{chunk_id}"


def rewrite_query(query: str, intent: str = "") -> str:
    parts = [intent.strip(), query.strip()]
    merged = "\n".join(part for part in parts if part)
    return merged or "小说参考资料检索"


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
