from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from novel_workflow.usage import prepare_budget_recovery


MAX_CONSECUTIVE_FAILURES = 3


def ensure_recovery_state(state: Any) -> dict[str, Any]:
    current = state.recovery_state if isinstance(getattr(state, "recovery_state", None), dict) else {}
    recovery = {
        "status": str(current.get("status") or "closed"),
        "needs_recovery": bool(current.get("needs_recovery", False)),
        "consecutive_failures": int(current.get("consecutive_failures") or 0),
        "total_failures": int(current.get("total_failures") or 0),
        "max_consecutive_failures": int(current.get("max_consecutive_failures") or MAX_CONSECUTIVE_FAILURES),
        "last_failure": copy.deepcopy(current.get("last_failure") or {}),
        "failure_history": [item for item in current.get("failure_history", []) if isinstance(item, dict)][-40:],
        "last_stable_checkpoint": copy.deepcopy(current.get("last_stable_checkpoint") or {}),
        "recovery_count": int(current.get("recovery_count") or 0),
        "last_recovery_at": str(current.get("last_recovery_at") or ""),
        "budget_recovery_prepared": bool(current.get("budget_recovery_prepared", False)),
    }
    if recovery["status"] not in {"closed", "degraded", "open"}:
        recovery["status"] = "closed"
    state.recovery_state = recovery
    return recovery


def mark_stable_checkpoint(
    state: Any,
    *,
    node_id: str,
    node_type: str,
    output_key: str,
    status: str,
    artifact: Any = None,
    chapter: str = "",
) -> dict[str, Any]:
    recovery = ensure_recovery_state(state)
    checkpoint = {
        "node_id": node_id,
        "node_type": node_type,
        "output_key": output_key,
        "chapter": chapter,
        "status": status,
        "artifact_signature": artifact_signature(artifact),
        "created_at": _now(),
    }
    recovery.update(
        {
            "status": "closed",
            "needs_recovery": False,
            "consecutive_failures": 0,
            "last_stable_checkpoint": checkpoint,
            "budget_recovery_prepared": False,
        }
    )
    state.recovery_state = recovery
    return checkpoint


def register_failure(
    state: Any,
    *,
    node_id: str,
    node_type: str,
    code: str,
    message: str,
    retryable: bool = True,
    chapter: str = "",
) -> dict[str, Any]:
    recovery = ensure_recovery_state(state)
    previous = recovery.get("last_failure") or {}
    same_scope = previous.get("node_id") == node_id and previous.get("chapter", "") == chapter
    consecutive = int(recovery.get("consecutive_failures") or 0) + 1 if same_scope else 1
    total = int(recovery.get("total_failures") or 0) + 1
    record = {
        "id": f"failure-{total}-{node_id}-{chapter or 'stage'}",
        "node_id": node_id,
        "node_type": node_type,
        "chapter": chapter,
        "code": code,
        "message": message,
        "retryable": retryable,
        "consecutive": consecutive,
        "created_at": _now(),
    }
    threshold = int(recovery.get("max_consecutive_failures") or MAX_CONSECUTIVE_FAILURES)
    recovery.update(
        {
            "status": "open" if consecutive >= threshold else "degraded",
            "needs_recovery": True,
            "consecutive_failures": consecutive,
            "total_failures": total,
            "last_failure": record,
            "failure_history": [*recovery.get("failure_history", []), record][-40:],
            "budget_recovery_prepared": False,
        }
    )
    state.recovery_state = recovery
    return record


def prepare_checkpoint_recovery(state: Any) -> dict[str, Any]:
    recovery = ensure_recovery_state(state)
    if recovery.get("status") == "open":
        raise ValueError("连续失败已达到熔断上限，请修复配置后重新开始")
    checkpoint = copy.deepcopy(recovery.get("last_stable_checkpoint") or {})
    if not checkpoint.get("node_id") or not checkpoint.get("output_key"):
        raise ValueError("没有可恢复的稳定检查点，请重新开始")
    already_prepared = bool(
        recovery.get("budget_recovery_prepared") and state.runtime_phase == "checkpoint_recovery"
    )
    recovery.update(
        {
            "status": "closed",
            "needs_recovery": False,
            "recovery_count": int(recovery.get("recovery_count") or 0) + (0 if already_prepared else 1),
            "last_recovery_at": str(recovery.get("last_recovery_at") or "") if already_prepared else _now(),
        }
    )
    if not already_prepared:
        prepare_budget_recovery(state)
    state.errors = []
    for node_id, progress in state.progress.items():
        if isinstance(progress, dict) and progress.get("status") == "failed":
            state.progress[node_id] = {**progress, "status": "planned", "error": ""}
    state.runtime_phase = "checkpoint_recovery"
    recovery["budget_recovery_prepared"] = True
    state.recovery_state = recovery
    return checkpoint


def recovery_required(state: Any) -> bool:
    recovery = ensure_recovery_state(state)
    return bool(
        recovery.get("needs_recovery")
        or state.errors
        or state.runtime_phase == "recovery_required"
        or (state.runtime_phase == "checkpoint_recovery" and not recovery.get("budget_recovery_prepared"))
        or (state.runtime_phase == "failed" and recovery.get("last_failure"))
    )


def artifact_signature(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest() if payload else ""


def failure_code(message: str, *, validation: bool = False, quality: bool = False) -> str:
    if validation:
        return "artifact_validation"
    if quality:
        return "quality_blocking"
    lowered = message.casefold()
    if any(token in lowered for token in ("timeout", "provider", "api", "连接", "超时")):
        return "provider_error"
    return "execution_error"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
