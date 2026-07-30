from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from novel_workflow.storage.run_store_support import decode_cursor, encode_cursor, legacy_time


class RunHistoryStoreMixin:
    def list_history(
        self,
        *,
        limit: int = 20,
        cursor: str = "",
        project_id: str = "",
        status: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        limit = max(1, min(int(limit or 20), 50))
        cursor_key = decode_cursor(cursor)
        summaries: list[dict[str, Any]] = []
        for path in sorted(self.root.iterdir(), key=lambda item: item.name):
            run_path = path / "run.json"
            if not path.is_dir() or not run_path.exists():
                continue
            try:
                run_id = path.name
                self._validate_run_id(run_id)
                run_data = json.loads(run_path.read_text(encoding="utf-8"))
                if not isinstance(run_data, dict):
                    continue
                metadata_path = path / "run_meta.json"
                summary: dict[str, Any] | None = None
                if metadata_path.exists():
                    candidate = json.loads(metadata_path.read_text(encoding="utf-8"))
                    if isinstance(candidate, dict):
                        summary = candidate
                if summary is None or _metadata_is_stale(summary, metadata_path, run_path, run_data):
                    summary = self._summary(run_data)
                summary = _normalise_summary_times(summary, run_path)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if project_id and summary.get("project_id") != project_id:
                continue
            if status and summary.get("status") != status:
                continue
            if cursor_key and (str(summary.get("updated_at") or ""), run_id) >= cursor_key:
                continue
            summaries.append(summary)
        summaries.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("run_id") or "")), reverse=True)
        page = summaries[:limit]
        next_cursor = ""
        if len(summaries) > limit and page:
            tail = page[-1]
            next_cursor = encode_cursor((str(tail.get("updated_at") or ""), str(tail.get("run_id") or "")))
        return page, next_cursor

    def _summary(self, data: dict[str, Any]) -> dict[str, Any]:
        state = data.get("state") or {}
        events = data.get("events") or []
        runtime_phase = str(state.get("runtime_phase") or "")
        recovery = state.get("recovery_state") or {}
        approval = data.get("approval") or {}
        snapshots = data.get("snapshots") or []
        latest = next((item for item in reversed(snapshots) if isinstance(item, dict) and item.get("restorable")), {})
        if runtime_phase == "completed" or any(item.get("type") == "run_completed" for item in events if isinstance(item, dict)):
            status = "completed"
        else:
            has_restorable_snapshot = bool(latest)
            if runtime_phase == "checkpoint_recovery":
                # A restored checkpoint is deliberately paused until the user explicitly resumes.
                status = "paused"
            elif runtime_phase in {"failed", "recovery_required"} or recovery.get("needs_recovery"):
                status = "recovery_required" if has_restorable_snapshot else "failed"
            elif approval.get("required") or state.get("approval_required") or runtime_phase in {"awaiting_stage_confirmation", "stage_ready_to_continue"}:
                status = "awaiting_confirmation"
            elif data.get("paused"):
                status = "paused"
            elif state.get("run_has_started"):
                status = "running"
            else:
                status = "created"
        progress = [item for item in state.get("chapter_progress") or [] if isinstance(item, dict)]
        words = sum(_integer(item.get("words")) for item in progress)
        usage = state.get("stage_usage_summaries") or state.get("token_estimates") or {}
        total_tokens = 0
        estimated_cost = 0.0
        for item in usage.values() if isinstance(usage, dict) else []:
            if not isinstance(item, dict):
                continue
            snapshot = item.get("usage") if isinstance(item.get("usage"), dict) else item
            total_tokens += _integer(snapshot.get("estimated_input_tokens")) + _integer(snapshot.get("estimated_output_tokens"))
            estimated_cost += _number(snapshot.get("estimated_cost_usd"))
        inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
        workflow = data.get("workflow") if isinstance(data.get("workflow"), dict) else {}
        state_inputs = state.get("inputs") if isinstance(state.get("inputs"), dict) else {}
        artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), dict) else {}
        exports = data.get("exports") if isinstance(data.get("exports"), list) else []
        return {
            "run_id": str(data.get("run_id") or ""),
            "project_id": str(state.get("project_id") or data.get("project_id") or inputs.get("project_id") or data.get("run_id") or ""),
            "title": str(inputs.get("title") or workflow.get("name") or "未命名小说"),
            "quality_mode": str(state_inputs.get("quality_mode") or workflow.get("quality_mode") or "balanced"),
            "status": status,
            "current_stage": {
                "id": str(state.get("current_stage_id") or ""),
                "label": str(state.get("current_stage_label") or ""),
                "type": str(state.get("current_stage_type") or ""),
            },
            "completed_stage_ids": list(state.get("completed_stage_ids") or []),
            "created_at": str(data.get("created_at") or legacy_time(events)),
            "updated_at": str(data.get("updated_at") or legacy_time(events)),
            "completed_at": str(data.get("completed_at") or state.get("run_completed_at") or ""),
            "words": words,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "summary": _summary_text(status, state, recovery),
            "can_resume": status in {"running", "paused", "awaiting_confirmation", "recovery_required"},
            "recovery_required": status == "recovery_required",
            "latest_snapshot_id": latest.get("snapshot_id") or "",
            "export_ready": bool(artifacts.get("export")),
            "export_count": len(exports),
            "latest_export": copy.deepcopy(exports[-1]) if exports else None,
            "state_revision": int(data.get("state_revision") or 0),
        }


def _summary_text(status: str, state: dict[str, Any], recovery: dict[str, Any]) -> str:
    if status == "recovery_required":
        return str((recovery.get("last_failure") or {}).get("message") or "运行停在最后稳定检查点，等待明确恢复。")
    if status == "awaiting_confirmation":
        return "当前阶段产物已落盘，等待人工确认后继续。"
    if status == "completed":
        return "本次创作运行已完成，可查看产物并从交付记录重新下载。"
    if status == "failed":
        errors = state.get("errors") if isinstance(state.get("errors"), list) else []
        last_error = errors[-1] if errors and isinstance(errors[-1], dict) else {}
        return str(last_error.get("error") or "运行失败，未找到可恢复检查点。")
    return "运行状态已保存，可从服务端历史继续查看。"


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _metadata_is_stale(
    metadata: dict[str, Any],
    metadata_path: Path,
    run_path: Path,
    run_data: dict[str, Any],
) -> bool:
    if metadata.get("run_id") and metadata.get("run_id") != run_data.get("run_id"):
        return True
    if _integer(metadata.get("state_revision")) < _integer(run_data.get("state_revision")):
        return True
    if not _valid_time(metadata.get("created_at")) or not _valid_time(metadata.get("updated_at")):
        return True
    try:
        return metadata_path.stat().st_mtime_ns < run_path.stat().st_mtime_ns
    except OSError:
        return True


def _normalise_summary_times(summary: dict[str, Any], run_path: Path) -> dict[str, Any]:
    result = copy.deepcopy(summary)
    try:
        fallback = datetime.fromtimestamp(run_path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        fallback = ""
    for key in ("created_at", "updated_at"):
        if not _valid_time(result.get(key)):
            result[key] = fallback
    if result.get("completed_at") and not _valid_time(result.get("completed_at")):
        result["completed_at"] = fallback
    return result


def _valid_time(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True
