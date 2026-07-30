from __future__ import annotations

from typing import Any

from novel_workflow.providers.fallback import fallback_decision, text_provider_route
from novel_workflow.usage import (
    BudgetExceededError,
    authorize_provider_call,
    queue_budget_event,
    settle_provider_call,
)


async def execute_text_provider_call(
    runner_or_registry: Any,
    node: Any,
    state: Any,
    *,
    prompt: str,
    task_name: str,
    context: dict[str, Any],
    schema: dict[str, Any] | None,
    kind: str,
    chapter: str = "",
    idempotency_root: str,
    primary_attempt_limit: int | None = None,
    run_store: Any | None = None,
) -> Any:
    providers = getattr(runner_or_registry, "providers", runner_or_registry)
    route = text_provider_route(node)
    fallback_limit = max(0, (primary_attempt_limit or _primary_limit(node, kind)) * (len(route) - 1))
    previous_failure_code = ""

    for index, target in enumerate(route, start=1):
        event_base = {
            "run_id": state.run_id,
            "node_id": node.id,
            "node_type": node.type,
            "task_name": task_name,
            "provider_profile_id": target.provider_profile_id,
            "model": target.model,
            "attempt": index,
            "is_fallback": target.is_fallback,
        }
        try:
            settings = node.model_settings.model_copy(update={"model": target.model})
            provider = providers.text_for(target.provider_profile_id, settings)
        except Exception as exc:
            decision = fallback_decision(exc, "text")
            _queue(state, {**event_base, "type": "provider_attempt_failed", "failure_code": decision.code, "message": decision.message, "billed": False})
            _persist(run_store, state)
            if decision.allowed and index < len(route):
                previous_failure_code = decision.code
                _schedule_fallback(state, event_base, route[index], decision.code)
                _persist(run_store, state)
                continue
            raise

        operation_kind = "fallback" if target.is_fallback else kind
        operation_limit = fallback_limit if target.is_fallback else primary_attempt_limit
        budget = authorize_provider_call(
            state,
            node,
            prompt_text=prompt,
            chapter=chapter,
            kind=operation_kind,
            provider_profile_id=target.provider_profile_id,
            model=target.model,
            attempt_limit=operation_limit,
        )
        if not budget.get("allowed"):
            _persist(run_store, state)
            raise BudgetExceededError(
                str(budget.get("message") or "预算阻断 Provider 调用"),
                scope_key=str(budget.get("scope_key") or ""),
            )

        operation_id = str(budget["operation_id"])
        request_key = f"{idempotency_root}:{target.provider_profile_id}:{operation_id}"
        _queue(state, {
            **event_base,
            "type": "provider_attempt_started",
            "operation_id": operation_id,
            "scope_key": budget["scope_key"],
            "predicted_tokens": budget["predicted_tokens"],
            "triggered_by": previous_failure_code,
            "billed": True,
        })
        _persist(run_store, state)
        try:
            result = await provider.generate_structured(
                prompt,
                task_name=task_name,
                context={**context, "idempotency_key": request_key},
                schema=schema,
            )
        except Exception as exc:
            settle_provider_call(
                state,
                scope_key=str(budget["scope_key"]),
                operation_id=operation_id,
                prompt_text=prompt,
                output_text="",
                failed=True,
            )
            decision = fallback_decision(exc, "text")
            _queue(state, {
                **event_base,
                "type": "provider_attempt_failed",
                "operation_id": operation_id,
                "failure_code": decision.code,
                "message": decision.message,
                "billed": True,
            })
            _persist(run_store, state)
            if decision.allowed and index < len(route):
                previous_failure_code = decision.code
                _schedule_fallback(state, event_base, route[index], decision.code)
                _persist(run_store, state)
                continue
            if index < len(route):
                _queue(state, {
                    **event_base,
                    "type": "provider_fallback_blocked",
                    "failure_code": decision.code,
                    "message": decision.message,
                    "response_uncertain": decision.response_uncertain,
                })
                _persist(run_store, state)
            raise

        settle_provider_call(
            state,
            scope_key=str(budget["scope_key"]),
            operation_id=operation_id,
            prompt_text=prompt,
            output_text=result,
        )
        _queue(state, {
            **event_base,
            "type": "provider_attempt_succeeded",
            "operation_id": operation_id,
            "billed": True,
        })
        _persist(run_store, state)
        return result

    raise RuntimeError("Provider route exhausted without a result")


def _primary_limit(node: Any, kind: str) -> int:
    if kind == "candidate":
        return max(1, int(node.variant_policy.candidate_count or 1))
    if kind == "regeneration":
        return 12
    if kind == "revision":
        return 2
    return 1


def _schedule_fallback(state: Any, event_base: dict[str, Any], target: Any, failure_code: str) -> None:
    _queue(state, {
        **event_base,
        "type": "provider_fallback_scheduled",
        "failure_code": failure_code,
        "next_provider_profile_id": target.provider_profile_id,
        "next_model": target.model,
    })


def _queue(state: Any, event: dict[str, Any]) -> None:
    queue_budget_event(state, event)


def _persist(run_store: Any | None, state: Any) -> None:
    if run_store is not None:
        run_store.update_state(state.run_id, state)
