from __future__ import annotations

import os
from typing import Any

import requests

from novel_workflow.providers.base import TextProvider


class OpenAICompatibleTextProvider(TextProvider):
    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @classmethod
    def from_env(cls) -> "OpenAICompatibleTextProvider | None":
        base_url = os.environ.get("NOVEL_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("NOVEL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("NOVEL_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
        if not base_url or not api_key:
            return None
        return cls(base_url=base_url, api_key=api_key, model=model)

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions" if self.base_url.endswith("/v1") else f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "task_name": task_name,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "你是专业小说工作流节点，只输出当前节点所需内容。"},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"])
