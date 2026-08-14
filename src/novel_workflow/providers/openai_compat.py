from __future__ import annotations

import hashlib
import logging
import os
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from novel_workflow.providers.base import TextProvider, split_system_prompt
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.openai_completion import (
    collect_stream_content,
    read_completion_content,
)
from novel_workflow.providers.openai_request import (
    build_chat_request_plan,
    ensure_structured_prompt,
)
from novel_workflow.providers.openai_sdk import (
    create_openai_client,
    translate_openai_error,
)
from novel_workflow.providers.structured_parsing import (
    parse_exact_json_object_result,
)
from novel_workflow.providers.templates import provider_template
from novel_workflow.providers.frozen_contract import FrozenProviderTemplate

logger = logging.getLogger(__name__)


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
        template: FrozenProviderTemplate | None = None,
        client: AsyncOpenAI | None = None,
        prefill_client: AsyncOpenAI | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds
        self.template_id = template_id
        self.template = template or provider_template(template_id, "openai-compatible")
        if self.template.id != template_id or self.template.kind != "openai-compatible":
            raise ValueError("Text Provider template snapshot does not match its binding")
        self.last_usage: dict[str, int] = {}
        self.last_response_diagnostic: dict[str, Any] = {}
        self._client = client or create_openai_client(
            base_url=base_url,
            api_key=api_key,
            max_retries=self.template.max_retries,
            auth_header=self.template.auth_header,
        )
        self._prefill_client = prefill_client

    @classmethod
    def from_env(cls) -> OpenAICompatibleTextProvider | None:
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
    ) -> OpenAICompatibleTextProvider | None:
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
    ) -> OpenAICompatibleTextProvider:
        return OpenAICompatibleTextProvider(
            base_url=self.base_url,
            api_key=self.api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            template_id=self.template_id,
            template=(
                self.template
                if isinstance(self.template, FrozenProviderTemplate)
                else None
            ),
            client=self._client,
            prefill_client=self._prefill_client,
        )

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        request_key = _request_key(context, task_name=task_name)
        return await self._complete(
            prompt,
            task_name=task_name,
            json_mode=False,
            idempotency_key=request_key,
            assistant_prefill=_assistant_prefill(context),
            prompt_cache_key=_prompt_cache_key(context),
            disable_thinking=_disable_thinking(context),
        )

    async def _complete(
        self,
        prompt: str,
        *,
        task_name: str,
        json_mode: bool,
        idempotency_key: str,
        schema: dict[str, Any] | None = None,
        assistant_prefill: str = "",
        prompt_cache_key: str = "",
        disable_thinking: bool = False,
    ) -> str:
        self.last_usage = {}
        self.last_response_diagnostic = {}
        system, user = split_system_prompt(prompt)
        if not system:
            system = "你是专业小说工作流节点，只输出当前节点所需内容。"
        plan = build_chat_request_plan(
            template=self.template,
            model=self.model,
            system=system,
            user=user,
            task_name=task_name,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            structured_schema=(schema or {"type": "object"}) if json_mode else None,
            assistant_prefill=assistant_prefill,
            prompt_cache_key=prompt_cache_key,
            disable_thinking=disable_thinking,
        )
        token_field = "max_completion_tokens" if "max_completion_tokens" in plan.request else (
            "max_tokens" if "max_tokens" in plan.request else "omitted"
        )
        logger.info(
            "Provider request prepared",
            extra={
                "provider_template": self.template_id,
                "request_protocol": "chat_completions",
                "model": self.model,
                "task_name": task_name,
                "output_mode": "structured" if json_mode else "text",
                "structured_mode": (
                    plan.structured_decision.effective_mode
                    if plan.structured_decision is not None
                    else "none"
                ),
                "prompt_chars": len(prompt),
                "thinking_enabled": _request_thinking_enabled(plan.request),
                "stream": plan.request.get("stream") is True,
                "token_field": token_field,
            },
        )
        try:
            request_headers = {"Idempotency-Key": idempotency_key}
            if plan.request_headers:
                request_headers.update(plan.request_headers)
            response = await self._request_client(assistant_prefill).chat.completions.create(
                **plan.request,
                extra_headers=request_headers,
                timeout=self.timeout_seconds,
            )
            completion = (
                await collect_stream_content(response)
                if plan.request.get("stream") is True
                else read_completion_content(response)
            )
            self.last_usage = dict(completion.usage)
        except ProviderResponseError:
            raise
        except Exception as exc:
            raise translate_openai_error(exc, timeout_seconds=self.timeout_seconds) from exc
        self.last_response_diagnostic = {
            "finish_reason": completion.finish_reason,
            "response_chars": len(completion.content),
            "reasoning_chars": completion.reasoning_chars,
        }
        if completion.finish_reason == "length":
            raise ProviderResponseError(
                "output_truncated",
                "Provider output was truncated by max_tokens",
                diagnostic_details=self.last_response_diagnostic,
                partial_content=completion.content,
            )
        content = completion.content
        if not isinstance(content, str) or not content.strip():
            diagnostic_code = (
                "reasoning_only_content_empty"
                if completion.reasoning_chars
                else ""
            )
            if json_mode and self.template.empty_content_policy == "documented_structured_empty":
                raise ProviderResponseError(
                    "structured_empty_content",
                    "Provider returned documented empty content in structured output mode",
                    diagnostic_code=diagnostic_code,
                    diagnostic_details=self.last_response_diagnostic,
                )
            raise ProviderResponseError(
                "empty_content",
                "Provider returned empty message content",
                diagnostic_code=diagnostic_code,
                diagnostic_details=self.last_response_diagnostic,
            )
        logger.info(
            "Provider response received",
            extra={
                "provider_template": self.template_id,
                "request_protocol": "chat_completions",
                "model": self.model,
                "task_name": task_name,
                "output_mode": "structured" if json_mode else "text",
                "finish_reason": completion.finish_reason,
                "output_chars": len(content),
                "usage_available": bool(self.last_usage),
            },
        )
        if assistant_prefill and self.template.assistant_prefill_mode == "kimi_partial":
            return assistant_prefill + content
        return content

    async def generate_strict_structured(
        self,
        prompt: str,
        *,
        task_name: str,
        context: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        policy = resolve_request_policy(self.template, model=self.model, task_name=task_name)
        structured_prompt = ensure_structured_prompt(
            prompt,
            task_name=task_name,
            schema=schema,
            policy=policy,
        )
        text = await self._complete(
            structured_prompt,
            task_name=task_name,
            json_mode=True,
            idempotency_key=_request_key(context, task_name=task_name),
            schema=schema,
            assistant_prefill=_assistant_prefill(context),
            prompt_cache_key=_prompt_cache_key(context),
            disable_thinking=_disable_thinking(context),
        )
        parse_result = parse_exact_json_object_result(text, schema=schema)
        self.last_response_diagnostic = {
            **self.last_response_diagnostic,
            "structured_parse": parse_result.diagnostic.as_dict(),
        }
        parsed = parse_result.value
        if parsed is None:
            raise ProviderResponseError(
                "json_parse_failed",
                "Provider did not return exactly one complete JSON object",
                diagnostic_details=self.last_response_diagnostic,
                partial_content=text,
            )
        return parsed

    def _request_client(self, assistant_prefill: str) -> AsyncOpenAI:
        if not assistant_prefill or not self.template.assistant_prefill_base_url:
            return self._client
        if self._prefill_client is None:
            self._prefill_client = create_openai_client(
                base_url=self.template.assistant_prefill_base_url,
                api_key=self.api_key,
                max_retries=self.template.max_retries,
                auth_header=self.template.auth_header,
            )
        return self._prefill_client


def _request_key(context: dict[str, Any], *, task_name: str) -> str:
    raw = str(context.get("idempotency_key") or f"{task_name}-{uuid4().hex}")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _assistant_prefill(context: dict[str, Any]) -> str:
    value = context.get("_assistant_prefill")
    return value if isinstance(value, str) and value.strip() else ""


def _prompt_cache_key(context: dict[str, Any]) -> str:
    value = context.get("_prompt_cache_key")
    if not isinstance(value, str) or not value.strip():
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _disable_thinking(context: dict[str, Any]) -> bool:
    return context.get("_thinking_override") == "disabled"


def _request_thinking_enabled(request: dict[str, Any]) -> bool:
    extra_body = request.get("extra_body")
    if isinstance(extra_body, dict):
        thinking = extra_body.get("thinking")
        if isinstance(thinking, dict) and thinking.get("type") == "enabled":
            return True
        if extra_body.get("enable_thinking") is True:
            return True
    effort = request.get("reasoning_effort")
    return isinstance(effort, str) and effort not in {"", "none"}
