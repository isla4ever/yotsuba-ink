from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from novel_workflow.providers.base import TextProvider, split_system_prompt
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.openai_sdk import create_openai_client, response_payload, translate_openai_error
from novel_workflow.providers.templates import provider_template


class OpenAICompatibleTextProvider(TextProvider):
    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        top_p: float = 0.95,
        timeout_seconds: int = 120,
        template_id: str = "openai-compatible-text",
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.template_id = template_id
        self.template = provider_template(template_id, "openai-compatible")
        self._client = client or create_openai_client(
            base_url=base_url,
            api_key=api_key,
            max_retries=self.template.max_retries,
        )

    @classmethod
    def from_env(cls) -> "OpenAICompatibleTextProvider | None":
        base_url = os.environ.get("NOVEL_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("NOVEL_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("NOVEL_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
        if not base_url or not api_key:
            return None
        return cls(base_url=base_url, api_key=api_key, model=model)

    @classmethod
    def from_profile(
        cls,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        top_p: float = 0.95,
        timeout_seconds: int = 120,
        template_id: str = "openai-compatible-text",
    ) -> "OpenAICompatibleTextProvider | None":
        if not base_url or not api_key:
            return None
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            template_id=template_id,
        )

    def with_options(
        self,
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        timeout_seconds: int,
    ) -> "OpenAICompatibleTextProvider":
        return OpenAICompatibleTextProvider(
            base_url=self.base_url,
            api_key=self.api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            template_id=self.template_id,
            client=self._client,
        )

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        request_key = _request_key(context, task_name=task_name)
        return await self._complete(prompt, task_name=task_name, json_mode=False, idempotency_key=request_key)

    async def _complete(self, prompt: str, *, task_name: str, json_mode: bool, idempotency_key: str) -> str:
        system, user = split_system_prompt(prompt)
        if not system:
            system = "你是专业小说工作流节点，只输出当前节点所需内容。"
        request: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode and self.template.supports_response_format:
            request["response_format"] = {"type": "json_object"}
        try:
            response = await self._client.chat.completions.create(
                **request,
                extra_headers={"Idempotency-Key": idempotency_key},
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            raise translate_openai_error(exc, timeout_seconds=self.timeout_seconds) from exc
        payload = response_payload(response)
        try:
            choice = payload["choices"][0]
            finish_reason = choice.get("finish_reason")
            content = choice["message"].get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError("response_shape_error", "Provider response missing choices[0].message.content") from exc
        if finish_reason == "length":
            raise ProviderResponseError("output_truncated", "Provider output was truncated by max_tokens")
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("empty_content", "Provider returned empty message content")
        return content

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        contract_hint = ""
        if schema and "## 输出结构" not in prompt:
            contract_hint = f"\n\n请只返回 JSON 对象，字段必须对齐这个结构描述：\n{json.dumps(schema, ensure_ascii=False)}"
        structured_prompt = f"{prompt}{contract_hint}"
        text = await self._complete_structured_with_retries(
            structured_prompt,
            task_name=task_name,
            request_key=_request_key(context, task_name=task_name),
        )
        parsed = _parse_json_object(text)
        if parsed is None:
            raise ProviderResponseError("json_parse_failed", "Provider did not return a JSON object")
        return parsed

    async def _complete_structured_with_retries(self, prompt: str, *, task_name: str, request_key: str) -> str:
        current_prompt = prompt
        for attempt in range(3):
            try:
                return await self._complete(
                    current_prompt,
                    task_name=task_name,
                    json_mode=True,
                    idempotency_key=f"{request_key}-{attempt + 1}",
                )
            except ProviderResponseError as exc:
                if exc.code != "output_truncated" or attempt == 2:
                    if exc.code == "output_truncated" and attempt == 2:
                        raise ProviderResponseError("output_truncated", "Provider output was truncated by max_tokens after compact JSON retries") from exc
                    raise
                current_prompt = _retry_compact_json_prompt(prompt, attempt=attempt + 1)
        raise ProviderResponseError("output_truncated", "Provider output was truncated by max_tokens")


def _request_key(context: dict[str, Any], *, task_name: str) -> str:
    raw = str(context.get("idempotency_key") or f"{task_name}-{uuid4().hex}")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_json_object(text: str) -> Any | None:
    stripped = text.strip()
    candidates = [stripped]
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _retry_compact_json_prompt(prompt: str, *, attempt: int = 1) -> str:
    string_limit = 60 if attempt <= 1 else 32
    array_limit = "每个数组最多 3 项" if attempt <= 1 else "每个数组最多 1-2 项"
    return (
        f"{prompt}\n\n"
        "## 重新输出要求\n"
        "上一次输出过长被截断。请重新返回一个更短的 JSON object："
        f"只保留 schema 中字段，不要解释；数组取{array_limit}；每个字符串控制在 8-{string_limit} 个中文字符；"
        "title_candidates 保留 5 个短标题；characters 至少 2 个；relationships 至少 1 条；"
        "不得输出 Markdown、代码块或补充说明。"
    )
