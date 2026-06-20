from __future__ import annotations

import os
from typing import Any

import requests

from novel_workflow.references.schemas import ReferenceSearchRequest, ReferenceSearchResponse, ReferenceSearchResult


class TavilySearchClient:
    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key_env: str = "TAVILY_API_KEY", timeout_seconds: int = 20) -> None:
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

    def search(self, request: ReferenceSearchRequest) -> ReferenceSearchResponse:
        api_key = os.getenv(self.api_key_env, "").strip()
        if not api_key:
            return ReferenceSearchResponse(
                enabled=False,
                message=f"未配置 {self.api_key_env}，无法执行联网搜索。可先使用手动链接或参考文本。",
            )

        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "query": request.query,
                "max_results": request.max_results,
                "search_depth": request.search_depth,
                "include_answer": True,
                "include_raw_content": False,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return ReferenceSearchResponse(enabled=True, message=str(payload.get("answer") or ""), results=_normalize_results(payload))


def _normalize_results(payload: dict[str, Any]) -> list[ReferenceSearchResult]:
    results = payload.get("results") or []
    normalized: list[ReferenceSearchResult] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        normalized.append(
            ReferenceSearchResult(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                content=str(item.get("content") or item.get("snippet") or ""),
                score=float(item.get("score") or 0.0),
            )
        )
    return normalized
