from __future__ import annotations

import copy
from typing import Any

from novel_workflow.usage.budget import ensure_budget_state


def authorize_image_call(
    state: Any,
    node: Any,
    *,
    candidate_id: str,
    generation_key: str,
    estimated_cost_usd: float | None,
    retry: bool = False,
    fallback: bool = False,
    provider_profile_id: str = "",
    model: str = "",
    fallback_limit: int | None = None,
) -> dict[str, Any]:
    image = _image_budget(state)
    scope = _scope(state, node)
    existing = next((item for item in scope["operations"] if item.get("generation_key") == generation_key), None)
    if existing and existing.get("status") == "completed":
        return {"allowed": False, "reused": True, "operation_id": existing["id"], "scope_key": scope["scope_key"]}
    if existing and existing.get("status") == "uncertain" and scope.get("recovery_retry_ready"):
        existing["status"] = "recovery_reserved"
        scope["recovery_retry_ready"] = False
        return {"allowed": True, "recovery": True, "operation_id": existing["id"], "scope_key": scope["scope_key"]}
    call_limit = int(scope["limits"]["calls"])
    retry_limit = int(scope["limits"]["retries"])
    if fallback_limit is not None:
        scope["limits"]["fallbacks"] = max(int(scope["limits"].get("fallbacks") or 0), max(0, int(fallback_limit)))
    fallback_attempt_limit = int(scope["limits"].get("fallbacks") or 0)
    if not retry and int(scope["attempts"]["calls"]) >= call_limit:
        if not fallback:
            return _deny(state, scope, "image_call_limit", "封面图片生成次数已达到预算上限")
    if retry and int(scope["attempts"]["retries"]) >= retry_limit:
        return _deny(state, scope, "image_retry_limit", "封面候选重试次数已达到预算上限")
    if fallback and int(scope["attempts"].get("fallbacks") or 0) >= fallback_attempt_limit:
        return _deny(state, scope, "image_fallback_limit", "封面备用 Provider 尝试次数已达到预算上限")
    reserved = max(0.0, float(estimated_cost_usd or 0))
    stage_max = scope.get("max_cost_usd")
    if stage_max is not None and scope["consumed_cost_usd"] + scope["reserved_cost_usd"] + reserved > stage_max:
        return _deny(state, scope, "image_stage_cost_exceeded", "封面图片预计费用将超过阶段预算")
    run_max = image.get("run_max_cost_usd")
    if run_max is not None and image["consumed_cost_usd"] + image["reserved_cost_usd"] + reserved > run_max:
        return _deny(state, scope, "image_run_cost_exceeded", "封面图片预计费用将超过本次运行预算")
    operation = {
        "id": f"image-op-{len(scope['operations']) + 1}",
        "candidate_id": candidate_id,
        "generation_key": generation_key,
        "kind": "fallback" if fallback else "retry" if retry else "generation",
        "provider_profile_id": provider_profile_id,
        "model": model,
        "status": "reserved",
        "reserved_cost_usd": reserved,
        "consumed_cost_usd": 0.0,
    }
    scope["operations"].append(operation)
    scope["attempts"]["fallbacks" if fallback else "retries" if retry else "calls"] += 1
    scope["reserved_cost_usd"] += reserved
    image["reserved_cost_usd"] += reserved
    return {"allowed": True, "operation_id": operation["id"], "scope_key": scope["scope_key"]}


def settle_image_call(
    state: Any,
    *,
    scope_key: str,
    operation_id: str,
    failed: bool,
    actual_cost_usd: float | None = None,
) -> None:
    image = _image_budget(state)
    scope = image["scopes"].get(scope_key)
    if not scope:
        return
    operation = next((item for item in scope["operations"] if item.get("id") == operation_id), None)
    if not operation or operation.get("status") not in {"reserved", "recovery_reserved"}:
        return
    previous_consumed = float(operation.get("consumed_cost_usd") or 0)
    reserved = float(operation.get("reserved_cost_usd") or 0) if operation["status"] == "reserved" else 0.0
    actual = max(0.0, float(actual_cost_usd)) if actual_cost_usd is not None else reserved
    consumed = max(previous_consumed, actual, reserved if failed else 0.0)
    delta = max(0.0, consumed - previous_consumed)
    operation.update({"status": "failed" if failed else "completed", "consumed_cost_usd": consumed, "reserved_cost_usd": 0.0})
    scope["reserved_cost_usd"] = max(0.0, scope["reserved_cost_usd"] - reserved)
    image["reserved_cost_usd"] = max(0.0, image["reserved_cost_usd"] - reserved)
    scope["consumed_cost_usd"] += delta
    image["consumed_cost_usd"] += delta
    scope["completed_count" if not failed else "failed_count"] += 1


def prepare_image_budget_recovery(state: Any) -> None:
    image = _image_budget(state)
    failure = (getattr(state, "recovery_state", {}) or {}).get("last_failure") or {}
    node_id = str(failure.get("node_id") or "")
    for scope in image["scopes"].values():
        if node_id and scope.get("node_id") != node_id:
            continue
        prepared = False
        for operation in scope.get("operations", []):
            if operation.get("status") != "reserved":
                continue
            reserved = float(operation.get("reserved_cost_usd") or 0)
            operation.update({"status": "uncertain", "consumed_cost_usd": reserved, "reserved_cost_usd": 0.0})
            scope["reserved_cost_usd"] = max(0.0, scope["reserved_cost_usd"] - reserved)
            image["reserved_cost_usd"] = max(0.0, image["reserved_cost_usd"] - reserved)
            scope["consumed_cost_usd"] += reserved
            image["consumed_cost_usd"] += reserved
            prepared = True
        if prepared:
            scope["recovery_retry_ready"] = True


def image_budget_snapshot(state: Any, node_id: str) -> dict[str, Any]:
    image = _image_budget(state)
    scope = image["scopes"].get(node_id, {})
    return {
        "status": image["status"],
        "run_max_cost_usd": image.get("run_max_cost_usd"),
        "run_consumed_cost_usd": image["consumed_cost_usd"],
        "scope": copy.deepcopy(scope),
    }


def _image_budget(state: Any) -> dict[str, Any]:
    budget = ensure_budget_state(state)
    current = budget.get("image") if isinstance(budget.get("image"), dict) else {}
    image = {
        "version": 1,
        "status": str(current.get("status") or "active"),
        "run_max_cost_usd": _cost_limit(state, "run_image_max_cost_usd"),
        "consumed_cost_usd": float(current.get("consumed_cost_usd") or 0),
        "reserved_cost_usd": float(current.get("reserved_cost_usd") or 0),
        "scopes": {key: value for key, value in (current.get("scopes") or {}).items() if isinstance(value, dict)},
    }
    budget["image"] = image
    return image


def _scope(state: Any, node: Any) -> dict[str, Any]:
    image = _image_budget(state)
    existing = image["scopes"].get(node.id)
    if existing:
        existing.setdefault("attempts", {}).setdefault("fallbacks", 0)
        existing.setdefault("limits", {}).setdefault("fallbacks", 0)
        return existing
    config = ((state.inputs.get("stage_configs") or {}).get(node.id) or {}) if isinstance(state.inputs, dict) else {}
    candidate_count = max(1, min(4, _integer(config.get("candidate_count"), 3)))
    retry_limit = max(0, min(3, _integer(config.get("asset_retry_limit"), 2)))
    enabled_fallbacks = sum(1 for target in getattr(node, "image_fallback_targets", []) if target.enabled)
    scope = {
        "scope_key": node.id,
        "node_id": node.id,
        "max_cost_usd": _stage_cost_limit(state, node.id, config),
        "consumed_cost_usd": 0.0,
        "reserved_cost_usd": 0.0,
        "attempts": {"calls": 0, "retries": 0, "fallbacks": 0},
        "limits": {"calls": candidate_count, "retries": retry_limit, "fallbacks": candidate_count * enabled_fallbacks},
        "completed_count": 0,
        "failed_count": 0,
        "operations": [],
        "recovery_retry_ready": False,
    }
    image["scopes"][node.id] = scope
    return scope


def _deny(state: Any, scope: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    image = _image_budget(state)
    image["status"] = "exceeded"
    snapshot = image_budget_snapshot(state, scope["node_id"])
    budget = ensure_budget_state(state)
    budget["pending_events"].extend([
        {"type": "stage_budget_exceeded", "node_id": scope["node_id"], "scope_key": scope["scope_key"], "message": message, "budget_state": snapshot},
        {"type": "manual_intervention_required", "node_id": scope["node_id"], "reason": message, "budget_state": snapshot},
    ])
    return {"allowed": False, "code": code, "message": message, "scope_key": scope["scope_key"]}


def _stage_cost_limit(state: Any, node_id: str, config: dict[str, Any]) -> float | None:
    direct = _optional_float(config.get("image_budget_usd"))
    if direct is not None:
        return direct
    limits = state.inputs.get("budget_limits") if isinstance(state.inputs, dict) else None
    stages = limits.get("stages") if isinstance(limits, dict) else None
    value = stages.get(node_id) if isinstance(stages, dict) else None
    return _optional_float(value.get("image_max_cost_usd")) if isinstance(value, dict) else None


def _cost_limit(state: Any, key: str) -> float | None:
    limits = state.inputs.get("budget_limits") if isinstance(state.inputs, dict) else None
    return _optional_float(limits.get(key)) if isinstance(limits, dict) else None


def _optional_float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
