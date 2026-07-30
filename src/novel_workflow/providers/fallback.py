from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from novel_workflow.providers.errors import (
    ProviderResponseError,
    public_provider_failure,
)
from novel_workflow.providers.registry import ProviderUnavailableError


ProviderChannel = Literal["text", "image"]

_TEXT_FALLBACK_CODES = {
    "authentication_failed",
    "insufficient_balance",
    "endpoint_or_model_unavailable",
    "rate_limited",
    "timeout",
    "network_error",
    "service_unavailable",
}

# Timeouts and 5xx responses can arrive after an image was created upstream.
# Switching providers in that state risks a second paid image with no stable receipt.
_IMAGE_FALLBACK_CODES = {
    "authentication_failed",
    "insufficient_balance",
    "endpoint_or_model_unavailable",
    "rate_limited",
}


@dataclass(frozen=True, slots=True)
class ProviderRouteTarget:
    provider_profile_id: str
    model: str
    priority: int
    is_fallback: bool
    estimated_cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    allowed: bool
    code: str
    message: str
    response_uncertain: bool = False


def text_provider_route(node: Any) -> list[ProviderRouteTarget]:
    route = [
        ProviderRouteTarget(
            provider_profile_id=str(node.provider_profile_id),
            model=str(node.model_settings.model),
            priority=0,
            is_fallback=False,
        )
    ]
    route.extend(
        ProviderRouteTarget(
            provider_profile_id=str(target.provider_profile_id),
            model=str(target.model),
            priority=int(target.priority),
            is_fallback=True,
        )
        for target in sorted(node.fallback_targets, key=lambda item: item.priority)
        if target.enabled
    )
    return route


def image_provider_route(
    node: Any,
    workflow: Any,
    *,
    primary_model: str,
) -> list[ProviderRouteTarget]:
    profiles = {profile.id: profile for profile in workflow.provider_profiles}
    primary = profiles.get(node.image_provider_profile_id)
    route = [
        ProviderRouteTarget(
            provider_profile_id=str(node.image_provider_profile_id),
            model=primary_model,
            priority=0,
            is_fallback=False,
            estimated_cost_usd=getattr(primary, "estimated_cost_per_output_usd", None),
        )
    ]
    route.extend(
        ProviderRouteTarget(
            provider_profile_id=str(target.provider_profile_id),
            model=str(target.model),
            priority=int(target.priority),
            is_fallback=True,
            estimated_cost_usd=getattr(profiles.get(target.provider_profile_id), "estimated_cost_per_output_usd", None),
        )
        for target in sorted(node.image_fallback_targets, key=lambda item: item.priority)
        if target.enabled
    )
    return route


def fallback_decision(error: Exception, channel: ProviderChannel) -> FallbackDecision:
    if isinstance(error, ProviderUnavailableError):
        return FallbackDecision(
            allowed=True,
            code="provider_unavailable",
            message="Provider 未配置或当前不可用，正在检查已配置的备用来源。",
        )
    if not isinstance(error, ProviderResponseError):
        return FallbackDecision(
            allowed=False,
            code="provider_request_failed",
            message="调用失败，但错误类型不满足自动故障转移条件。",
        )
    failure = public_provider_failure(error)
    allowed_codes = _TEXT_FALLBACK_CODES if channel == "text" else _IMAGE_FALLBACK_CODES
    response_uncertain = channel == "image" and error.code in {
        "timeout",
        "network_error",
        "service_unavailable",
    }
    return FallbackDecision(
        allowed=error.code in allowed_codes,
        code=failure.code,
        message=failure.message,
        response_uncertain=response_uncertain,
    )
