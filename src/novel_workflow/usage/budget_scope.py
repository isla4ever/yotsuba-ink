from __future__ import annotations

from typing import Any

from novel_workflow.usage.budget_state import (
    WARNING_RATIO,
    ensure_budget_state,
    optional_int,
    public_budget,
    queue_budget_event,
    utc_now,
)
from novel_workflow.usage.tracker import estimate_text_tokens


SCOPE_HEADROOM = 1.25


def text_budget_scope(state: Any, node: Any, chapter: str, prompt_text: str) -> dict[str, Any]:
    budget = ensure_budget_state(state)
    scope_key = f"{node.id}:{chapter}" if chapter else node.id
    existing = budget["scopes"].get(scope_key)
    if existing:
        existing.setdefault("operations", [])
        attempts = existing.setdefault("attempts", {})
        limits = existing.setdefault("limits", {})
        for key in ("generation", "candidate", "regeneration", "revision", "fallback", "judge", "model_review", "retry"):
            attempts.setdefault(key, 0)
            limits.setdefault(key, 0)
        existing.setdefault("recovery_retry_ready", False)
        return existing
    policy = getattr(node, "variant_policy", None)
    candidate_limit = max(1, int(getattr(policy, "candidate_count", 1) or 1)) if getattr(policy, "enabled", False) else 1
    mode = str(state.inputs.get("quality_mode") or "balanced") if isinstance(state.inputs, dict) else "balanced"
    revision_limit = 0 if node.type != "chapter_text" else {"fast": 0, "balanced": 1, "deep": 2}.get(mode, 1)
    judge_limit = 1 if getattr(policy, "enabled", False) else 0
    # Quality L2 model review is billed separately (roadmap §10.3): one review per
    # chapter version — the allowance covers the initial pass plus re-reviews after
    # regeneration; beyond the cap reviews degrade to "unavailable" without blocking.
    model_review_limit = 0 if node.type != "chapter_text" else {"fast": 0, "balanced": 2, "deep": 3}.get(mode, 2)
    retry_limit = 1 if bool(getattr(getattr(node, "quality_policy", None), "retry_on_fail", False) or getattr(policy, "retry_on_fail", False)) else 0
    prompt_tokens = estimate_text_tokens(prompt_text, node.model_settings.model)
    per_call = max(1, prompt_tokens + int(node.model_settings.max_tokens))
    override = stage_override(state, node)
    regeneration_limit = 0 if node.type == "export_artifact" else 12
    enabled_fallbacks = sum(1 for target in getattr(node, "fallback_targets", []) if target.enabled)
    primary_call_limit = max(candidate_limit, 1)
    fallback_limit = enabled_fallbacks * (primary_call_limit + regeneration_limit + revision_limit)
    call_slots = primary_call_limit + regeneration_limit + revision_limit + model_review_limit + fallback_limit + retry_limit
    max_tokens = override or max(int(per_call * call_slots * SCOPE_HEADROOM), int(node.generation_budget.max_tokens if node.generation_budget else per_call))
    scope = {
        "scope_key": scope_key,
        "node_id": node.id,
        "node_type": node.type,
        "chapter": chapter,
        "model": node.model_settings.model,
        "max_tokens": max_tokens,
        "consumed_tokens": 0,
        "reserved_tokens": 0,
        "attempts": {"generation": 0, "candidate": 0, "regeneration": 0, "revision": 0, "fallback": 0, "judge": 0, "model_review": 0, "retry": 0},
        "limits": {
            "generation": 1,
            "candidate": candidate_limit,
            "regeneration": regeneration_limit,
            "revision": revision_limit,
            "fallback": fallback_limit,
            "judge": judge_limit,
            "model_review": model_review_limit,
            "retry": retry_limit,
        },
        "operations": [],
        "status": "active",
        "recovery_retry_ready": False,
    }
    budget["scopes"][scope_key] = scope
    return scope


def deny_budget_call(state: Any, scope: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    budget = ensure_budget_state(state)
    budget["status"] = "manual_intervention" if code == "budget_attempt_limit" else "exceeded"
    scope["status"] = budget["status"]
    budget["manual_intervention"] = {"scope_key": scope["scope_key"], "code": code, "message": message}
    event_type = "run_budget_exceeded" if code == "run_budget_exceeded" else "stage_budget_exceeded"
    snapshot = public_budget(budget)
    event_base = {"node_id": scope["node_id"], "node_type": scope["node_type"], "chapter": scope.get("chapter", "")}
    queue_budget_event(state, {**event_base, "type": event_type, "scope_key": scope["scope_key"], "message": message, "budget_state": snapshot})
    queue_budget_event(state, {**event_base, "type": "manual_intervention_required", "reason": message, "budget_state": snapshot})
    return {"allowed": False, "scope_key": scope["scope_key"], "code": code, "message": message}


def maybe_budget_warning(state: Any, scope: dict[str, Any], pending: int) -> None:
    budget = ensure_budget_state(state)
    used = int(scope.get("consumed_tokens") or 0) + int(scope.get("reserved_tokens") or 0) + pending
    ratio = float(budget.get("warning_ratio") or WARNING_RATIO)
    if used >= int(scope.get("max_tokens") or 1) * ratio and scope.get("status") == "active":
        scope["status"] = "warning"
        budget["status"] = "warning"
        queue_budget_event(state, {"type": "stage_budget_warning", "node_id": scope["node_id"], "node_type": scope["node_type"], "chapter": scope.get("chapter", ""), "scope_key": scope["scope_key"], "used_tokens": used, "max_tokens": scope["max_tokens"], "budget_state": public_budget(budget)})
    run_max = budget.get("run_max_tokens")
    run_used = int(budget.get("run_consumed_tokens") or 0) + int(budget.get("run_reserved_tokens") or 0)
    if run_max and run_used >= int(run_max * ratio) and not budget.get("run_warning_emitted"):
        budget["run_warning_emitted"] = True
        budget["status"] = "warning"
        queue_budget_event(state, {"type": "run_budget_warning", "used_tokens": run_used, "max_tokens": run_max, "budget_state": public_budget(budget)})


def stage_override(state: Any, node: Any) -> int | None:
    configured = (state.inputs.get("budget_limits") or {}).get("stages", {}) if isinstance(state.inputs, dict) else {}
    value = configured.get(node.id) or configured.get(node.type)
    if isinstance(value, dict):
        value = value.get("max_tokens") or value.get("total_tokens")
    return optional_int(value)
