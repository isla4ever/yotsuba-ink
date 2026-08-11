from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderUsageSummary(BaseModel):
    """Rebuildable projection of receipted Provider work for one Run."""

    model_config = ConfigDict(extra="forbid")

    provider_operations: int = Field(default=0, ge=0)
    succeeded_operations: int = Field(default=0, ge=0)
    failed_operations: int = Field(default=0, ge=0)
    pending_operations: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)


def provider_usage_snapshot(provider: Any) -> dict[str, int]:
    return normalize_provider_usage(getattr(provider, "last_usage", None))


def normalize_provider_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    aliases = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
        "reasoning_tokens": ("reasoning_tokens",),
    }
    for key, candidates in aliases.items():
        raw = next((value.get(candidate) for candidate in candidates if candidate in value), None)
        try:
            number = int(raw)
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


__all__ = [
    "ProviderUsageSummary",
    "normalize_provider_usage",
    "provider_total_tokens",
    "provider_usage_snapshot",
]
