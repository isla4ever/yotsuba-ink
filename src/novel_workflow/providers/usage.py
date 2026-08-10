from __future__ import annotations

from typing import Any


def provider_usage_snapshot(provider: Any) -> dict[str, int]:
    value = getattr(provider, "last_usage", None)
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "reasoning_tokens",
    ):
        try:
            number = int(value.get(key))
        except (TypeError, ValueError):
            continue
        if number >= 0:
            result[key] = number
    if "total_tokens" not in result and result:
        result["total_tokens"] = result.get("prompt_tokens", 0) + result.get(
            "completion_tokens",
            0,
        )
    return result


def provider_total_tokens(provider: Any) -> int | None:
    usage = provider_usage_snapshot(provider)
    total = usage.get("total_tokens")
    return total if isinstance(total, int) and total > 0 else None
