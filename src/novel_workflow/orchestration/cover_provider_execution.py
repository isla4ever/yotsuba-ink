from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.providers.fallback import (
    ProviderRouteTarget,
    fallback_decision,
    image_provider_route,
)
from novel_workflow.usage import queue_budget_event
from novel_workflow.usage.image_budget import authorize_image_call, settle_image_call


@dataclass(frozen=True, slots=True)
class CoverProviderResult:
    image: GeneratedImage
    target: ProviderRouteTarget
    generation_key: str


async def generate_cover_with_fallback(
    runner: Any,
    node: Any,
    state: Any,
    workflow: Any,
    *,
    run_id: str,
    candidate_id: str,
    prompt: str,
    base_generation_key: str,
    primary_model: str,
    size: str,
    quality: str,
    candidate_count: int,
    explicit_retry: bool,
) -> CoverProviderResult:
    route = image_provider_route(node, workflow, primary_model=primary_model)
    previous_failure_code = ""
    for index, target in enumerate(route, start=1):
        generation_key = _route_generation_key(base_generation_key, target, index)
        event_base = {
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "task_name": "cover_asset_generation",
            "candidate_id": candidate_id,
            "provider_profile_id": target.provider_profile_id,
            "model": target.model,
            "attempt": index,
            "is_fallback": target.is_fallback,
        }
        try:
            provider = runner.providers.image_for(target.provider_profile_id)
        except Exception as exc:
            decision = fallback_decision(exc, "image")
            _queue(state, {**event_base, "type": "provider_attempt_failed", "failure_code": decision.code, "message": decision.message, "billed": False})
            _persist(runner, state)
            if decision.allowed and index < len(route):
                previous_failure_code = decision.code
                _schedule(state, event_base, route[index], decision.code)
                _persist(runner, state)
                continue
            raise

        budget = authorize_image_call(
            state,
            node,
            candidate_id=candidate_id,
            generation_key=generation_key,
            estimated_cost_usd=target.estimated_cost_usd,
            retry=explicit_retry and not target.is_fallback,
            fallback=target.is_fallback,
            provider_profile_id=target.provider_profile_id,
            model=target.model,
            fallback_limit=max(0, candidate_count * (len(route) - 1)),
        )
        if not budget.get("allowed"):
            raise CoverProviderBudgetError(budget)

        operation_id = str(budget["operation_id"])
        _queue(state, {
            **event_base,
            "type": "provider_attempt_started",
            "operation_id": operation_id,
            "scope_key": budget["scope_key"],
            "estimated_cost_usd": target.estimated_cost_usd,
            "triggered_by": previous_failure_code,
            "billed": True,
        })
        _persist(runner, state)
        try:
            image = await provider.generate_cover(prompt, context={
                "run_id": run_id,
                "candidate_id": candidate_id,
                "idempotency_key": generation_key,
                "model": target.model,
                "size": size,
                "quality": quality,
            })
        except Exception as exc:
            settle_image_call(
                state,
                scope_key=str(budget["scope_key"]),
                operation_id=operation_id,
                failed=True,
            )
            decision = fallback_decision(exc, "image")
            _queue(state, {
                **event_base,
                "type": "provider_attempt_failed",
                "operation_id": operation_id,
                "failure_code": decision.code,
                "message": decision.message,
                "response_uncertain": decision.response_uncertain,
                "billed": True,
            })
            _persist(runner, state)
            if decision.allowed and index < len(route):
                previous_failure_code = decision.code
                _schedule(state, event_base, route[index], decision.code)
                _persist(runner, state)
                continue
            if index < len(route):
                _queue(state, {
                    **event_base,
                    "type": "provider_fallback_blocked",
                    "failure_code": decision.code,
                    "message": decision.message,
                    "response_uncertain": decision.response_uncertain,
                })
                _persist(runner, state)
            raise

        settle_image_call(
            state,
            scope_key=str(budget["scope_key"]),
            operation_id=operation_id,
            failed=False,
            actual_cost_usd=_actual_cost(image.usage),
        )
        _queue(state, {**event_base, "type": "provider_attempt_succeeded", "operation_id": operation_id, "billed": True})
        _persist(runner, state)
        return CoverProviderResult(image=image, target=target, generation_key=generation_key)

    raise RuntimeError("Image Provider route exhausted without a result")


class CoverProviderBudgetError(RuntimeError):
    def __init__(self, decision: dict[str, Any]) -> None:
        super().__init__(str(decision.get("message") or "图片预算已阻断"))
        self.decision = decision


def _route_generation_key(base_key: str, target: ProviderRouteTarget, index: int) -> str:
    if not target.is_fallback:
        return base_key
    payload = f"{base_key}:fallback:{index}:{target.provider_profile_id}:{target.model}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _schedule(state: Any, event_base: dict[str, Any], target: ProviderRouteTarget, failure_code: str) -> None:
    _queue(state, {
        **event_base,
        "type": "provider_fallback_scheduled",
        "failure_code": failure_code,
        "next_provider_profile_id": target.provider_profile_id,
        "next_model": target.model,
    })


def _queue(state: Any, event: dict[str, Any]) -> None:
    queue_budget_event(state, event)


def _persist(runner: Any, state: Any) -> None:
    runner.run_store.update_state(state.run_id, state)


def _actual_cost(usage: dict[str, Any]) -> float | None:
    for key in ("cost_usd", "estimated_cost_usd"):
        try:
            return max(0.0, float(usage[key])) if key in usage else None
        except (TypeError, ValueError):
            continue
    return None
