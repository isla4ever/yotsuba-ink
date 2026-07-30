from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


WARNING_RATIO = 0.8


def ensure_budget_state(state: Any) -> dict[str, Any]:
    current = getattr(state, "budget_state", None)
    current = current if isinstance(current, dict) else {}
    budget = {
        "version": 1,
        "status": str(current.get("status") or "active"),
        "warning_ratio": float(current.get("warning_ratio") or configured_warning_ratio(state)),
        "run_max_tokens": optional_int(current.get("run_max_tokens")) or configured_run_limit(state),
        "run_consumed_tokens": int(current.get("run_consumed_tokens") or 0),
        "run_reserved_tokens": int(current.get("run_reserved_tokens") or 0),
        "run_warning_emitted": bool(current.get("run_warning_emitted", False)),
        "scopes": {key: value for key, value in (current.get("scopes") or {}).items() if isinstance(value, dict)},
        "manual_intervention": dict(current.get("manual_intervention") or {}),
        "pending_events": [item for item in current.get("pending_events", []) if isinstance(item, dict)],
        "deferred_provider_events": [item for item in current.get("deferred_provider_events", []) if isinstance(item, dict)],
        "image": copy.deepcopy(current.get("image") or {}),
    }
    if budget["status"] not in {"active", "warning", "exceeded", "manual_intervention"}:
        budget["status"] = "active"
    state.budget_state = budget
    return budget


def queue_budget_event(state: Any, event: dict[str, Any]) -> None:
    ensure_budget_state(state)["pending_events"].append(copy.deepcopy(event))


def public_budget(budget: dict[str, Any]) -> dict[str, Any]:
    snapshot = copy.deepcopy(budget)
    snapshot.pop("pending_events", None)
    snapshot.pop("deferred_provider_events", None)
    return snapshot


def configured_run_limit(state: Any) -> int | None:
    configured = state.inputs.get("budget_limits") if isinstance(state.inputs, dict) else None
    return optional_int(configured.get("run_max_tokens")) if isinstance(configured, dict) else None


def configured_warning_ratio(state: Any) -> float:
    configured = state.inputs.get("budget_limits") if isinstance(state.inputs, dict) else None
    value = configured.get("warning_ratio") if isinstance(configured, dict) else None
    try:
        return min(0.99, max(0.5, float(value))) if value is not None else WARNING_RATIO
    except (TypeError, ValueError):
        return WARNING_RATIO


def optional_int(value: Any) -> int | None:
    try:
        number = int(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
