from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.openai_sdk import response_payload


@dataclass(frozen=True)
class CompletionContent:
    content: str
    finish_reason: str
    usage: dict[str, int]
    reasoning_chars: int = 0


def read_completion_content(response: Any) -> CompletionContent:
    payload = response_payload(response)
    try:
        choice = payload["choices"][0]
        content = choice["message"].get("content")
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderResponseError(
            "response_shape_error",
            "Provider response missing choices[0].message.content",
        ) from exc
    return CompletionContent(
        content=content if isinstance(content, str) else "",
        finish_reason=str(choice.get("finish_reason") or ""),
        usage=_usage(payload.get("usage")),
        reasoning_chars=_text_length(choice["message"].get("reasoning_content")),
    )


async def collect_stream_content(response: Any) -> CompletionContent:
    if not hasattr(response, "__aiter__"):
        raise ProviderResponseError(
            "response_shape_error",
            "Provider streaming response is not async iterable",
        )
    parts: list[str] = []
    reasoning_chars = 0
    finish_reason = ""
    usage: dict[str, int] = {}
    async for chunk in response:
        payload = response_payload(chunk)
        current_usage = _usage(payload.get("usage"))
        if current_usage:
            usage = current_usage
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0]
        if not isinstance(choice, dict):
            continue
        current_finish = choice.get("finish_reason")
        if isinstance(current_finish, str) and current_finish:
            finish_reason = current_finish
        delta = choice.get("delta")
        content = delta.get("content") if isinstance(delta, dict) else None
        if isinstance(content, str):
            parts.append(content)
        reasoning = delta.get("reasoning_content") if isinstance(delta, dict) else None
        if isinstance(reasoning, str):
            reasoning_chars += len(reasoning)
    return CompletionContent(
        content="".join(parts),
        finish_reason=finish_reason,
        usage=usage,
        reasoning_chars=reasoning_chars,
    )


def _text_length(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def _usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    keys_by_metric = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
    }
    result: dict[str, int] = {}
    for target, keys in keys_by_metric.items():
        raw = next((value.get(key) for key in keys if value.get(key) is not None), None)
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number >= 0:
            result[target] = number
    if "total_tokens" not in result and result:
        result["total_tokens"] = result.get("prompt_tokens", 0) + result.get(
            "completion_tokens",
            0,
        )
    details = value.get("completion_tokens_details")
    raw_reasoning = value.get("reasoning_tokens")
    if raw_reasoning is None and isinstance(details, dict):
        raw_reasoning = details.get("reasoning_tokens")
    try:
        reasoning_tokens = int(raw_reasoning)
    except (TypeError, ValueError):
        reasoning_tokens = -1
    if reasoning_tokens >= 0:
        result["reasoning_tokens"] = reasoning_tokens
    return result
