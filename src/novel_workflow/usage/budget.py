from __future__ import annotations

from typing import Any

from novel_workflow.usage.budget_scope import (
    deny_budget_call,
    maybe_budget_warning,
    text_budget_scope,
)
from novel_workflow.usage.budget_state import (
    ensure_budget_state,
    public_budget,
    queue_budget_event,
    utc_now,
)
from novel_workflow.usage.tracker import estimate_text_tokens


class BudgetExceededError(RuntimeError):
    """Raised before a provider call when the persisted budget cannot authorize it."""

    def __init__(self, message: str, *, scope_key: str = "") -> None:
        super().__init__(message)
        self.scope_key = scope_key


def authorize_provider_call(
    state: Any,
    node: Any,
    *,
    prompt_text: str,
    chapter: str = "",
    kind: str = "generation",
    provider_profile_id: str = "",
    model: str = "",
    attempt_limit: int | None = None,
) -> dict[str, Any]:
    budget = ensure_budget_state(state)
    scope = text_budget_scope(state, node, chapter, prompt_text)
    selected_model = model or node.model_settings.model
    predicted = max(1, estimate_text_tokens(prompt_text, selected_model) + int(node.model_settings.max_tokens))
    limit_key = kind if kind in scope["limits"] else "generation"
    if attempt_limit is not None:
        scope["limits"][limit_key] = max(int(scope["limits"].get(limit_key, 0)), max(0, int(attempt_limit)))
    is_recovery_retry = bool(scope.get("recovery_retry_ready")) and limit_key in {"generation", "candidate"}
    if is_recovery_retry and int(scope["attempts"].get("retry", 0)) >= int(scope["limits"].get("retry", 0)):
        return deny_budget_call(state, scope, "budget_attempt_limit", "失败重试已达到预算上限")
    if not is_recovery_retry and int(scope["attempts"].get(limit_key, 0)) >= int(scope["limits"].get(limit_key, 1)):
        return deny_budget_call(state, scope, "budget_attempt_limit", "已达到当前阶段的生成尝试上限")
    if scope["reserved_tokens"] + scope["consumed_tokens"] + predicted > scope["max_tokens"]:
        return deny_budget_call(state, scope, "stage_budget_exceeded", "当前阶段 Token 预算已用尽")
    run_max = budget.get("run_max_tokens")
    if run_max and budget["run_reserved_tokens"] + budget["run_consumed_tokens"] + predicted > run_max:
        return deny_budget_call(state, scope, "run_budget_exceeded", "本次运行 Token 预算已用尽")
    operation = {
        "id": f"budget-op-{len(scope['operations']) + 1}",
        "kind": "retry" if is_recovery_retry else kind,
        "status": "reserved",
        "predicted_tokens": predicted,
        "consumed_tokens": 0,
        "provider_profile_id": provider_profile_id or node.provider_profile_id,
        "model": selected_model,
        "created_at": utc_now(),
    }
    scope["operations"].append(operation)
    if is_recovery_retry:
        scope["attempts"]["retry"] = int(scope["attempts"].get("retry", 0)) + 1
        scope["recovery_retry_ready"] = False
    else:
        scope["attempts"][limit_key] = int(scope["attempts"].get(limit_key, 0)) + 1
    scope["reserved_tokens"] += predicted
    budget["run_reserved_tokens"] += predicted
    maybe_budget_warning(state, scope, 0)
    return {
        "allowed": True,
        "scope_key": scope["scope_key"],
        "operation_id": operation["id"],
        "predicted_tokens": predicted,
        "provider_profile_id": operation["provider_profile_id"],
        "model": selected_model,
    }


def settle_provider_call(
    state: Any,
    *,
    scope_key: str,
    operation_id: str,
    prompt_text: str,
    output_text: Any,
    failed: bool = False,
) -> None:
    budget = ensure_budget_state(state)
    scope = budget["scopes"].get(scope_key)
    if not scope:
        return
    operation = next((item for item in scope["operations"] if item.get("id") == operation_id), None)
    if not operation or operation.get("status") != "reserved":
        return
    predicted = int(operation.get("predicted_tokens") or 0)
    operation_model = str(operation.get("model") or scope.get("model") or "")
    actual = estimate_text_tokens(prompt_text, operation_model) + estimate_text_tokens(str(output_text or ""), operation_model)
    consumed = max(predicted, actual) if not failed else predicted
    operation.update({"status": "failed" if failed else "completed", "consumed_tokens": consumed, "settled_at": utc_now()})
    scope["reserved_tokens"] = max(0, int(scope.get("reserved_tokens") or 0) - predicted)
    scope["consumed_tokens"] = int(scope.get("consumed_tokens") or 0) + consumed
    budget["run_reserved_tokens"] = max(0, int(budget.get("run_reserved_tokens") or 0) - predicted)
    budget["run_consumed_tokens"] = int(budget.get("run_consumed_tokens") or 0) + consumed
    maybe_budget_warning(state, scope, 0)


def record_budget_operation(state: Any, node: Any, *, action: str, chapter: str = "") -> bool:
    budget = ensure_budget_state(state)
    scope = text_budget_scope(state, node, chapter, "")
    if int(scope["attempts"].get(action, 0)) >= int(scope["limits"].get(action, 0)):
        deny_budget_call(state, scope, "budget_attempt_limit", f"{action} 已达到预算上限")
        return False
    scope["attempts"][action] = int(scope["attempts"].get(action, 0)) + 1
    scope["operations"].append({"id": f"budget-op-{len(scope['operations']) + 1}", "kind": action, "status": "completed", "predicted_tokens": 0, "consumed_tokens": 0, "created_at": utc_now()})
    return True


def drain_budget_events(state: Any) -> list[dict[str, Any]]:
    budget = ensure_budget_state(state)
    events = list(budget.get("pending_events") or [])
    budget["pending_events"] = []
    return events


def budget_snapshot(state: Any) -> dict[str, Any]:
    return public_budget(ensure_budget_state(state))


def prepare_budget_recovery(state: Any) -> None:
    from novel_workflow.usage.image_budget import prepare_image_budget_recovery

    budget = ensure_budget_state(state)
    failure = _current_failure(state)
    scopes = _recovery_scopes(budget, failure)
    for scope in scopes:
        retryable_failure = False
        for operation in scope.get("operations", []):
            if operation.get("status") == "reserved":
                predicted = int(operation.get("predicted_tokens") or 0)
                operation.update({"status": "uncertain", "consumed_tokens": predicted, "settled_at": utc_now()})
                scope["reserved_tokens"] = max(0, int(scope.get("reserved_tokens") or 0) - predicted)
                scope["consumed_tokens"] = int(scope.get("consumed_tokens") or 0) + predicted
                budget["run_reserved_tokens"] = max(0, int(budget.get("run_reserved_tokens") or 0) - predicted)
                budget["run_consumed_tokens"] = int(budget.get("run_consumed_tokens") or 0) + predicted
                retryable_failure = True
            elif operation.get("status") in {"failed", "uncertain"}:
                retryable_failure = True
        if failure and failure.get("code") == "artifact_validation":
            retryable_failure = retryable_failure or any(
                operation.get("status") == "completed" and operation.get("kind") != "retry"
                for operation in scope.get("operations", [])
            )
        if not retryable_failure:
            continue
        recovery_id = _recovery_id(failure, scope)
        if scope.get("recovery_retry_failure_id") == recovery_id:
            continue
        attempts = scope.setdefault("attempts", {})
        limits = scope.setdefault("limits", {})
        limits["retry"] = max(1, int(limits.get("retry") or 0))
        if int(attempts.get("retry") or 0) >= int(limits["retry"]):
            continue
        scope["recovery_retry_ready"] = True
        scope["recovery_retry_failure_id"] = recovery_id
    prepare_image_budget_recovery(state)


def _current_failure(state: Any) -> dict[str, Any]:
    recovery = getattr(state, "recovery_state", None)
    if not isinstance(recovery, dict):
        return {}
    failure = recovery.get("last_failure")
    if not isinstance(failure, dict) or not failure.get("retryable", True):
        return {}
    return failure


def _recovery_scopes(budget: dict[str, Any], failure: dict[str, Any]) -> list[dict[str, Any]]:
    scopes = [scope for scope in budget["scopes"].values() if isinstance(scope, dict)]
    if not failure:
        return [scope for scope in scopes if _has_unsettled_failure(scope)]
    node_id = str(failure.get("node_id") or "")
    chapter = str(failure.get("chapter") or "")
    exact_key = f"{node_id}:{chapter}" if chapter else node_id
    exact = budget["scopes"].get(exact_key)
    if isinstance(exact, dict):
        return [exact]
    candidates = [
        scope
        for scope in scopes
        if str(scope.get("node_id") or "") == node_id
        and (not chapter or str(scope.get("chapter") or "") == chapter)
    ]
    return candidates[-1:] if candidates else []


def _has_unsettled_failure(scope: dict[str, Any]) -> bool:
    return any(
        operation.get("status") in {"failed", "reserved", "uncertain"}
        for operation in scope.get("operations", [])
        if isinstance(operation, dict)
    )


def _recovery_id(failure: dict[str, Any], scope: dict[str, Any]) -> str:
    failure_id = str(failure.get("id") or "")
    if failure_id:
        return failure_id
    operations = [item for item in scope.get("operations", []) if isinstance(item, dict)]
    latest = operations[-1] if operations else {}
    return ":".join(
        (
            str(scope.get("scope_key") or ""),
            str(failure.get("code") or latest.get("status") or "failure"),
            str(latest.get("id") or len(operations)),
        )
    )
