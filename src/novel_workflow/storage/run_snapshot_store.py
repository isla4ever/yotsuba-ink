from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from novel_workflow.storage.run_store_support import digest, now


class RunSnapshotStoreMixin:
    _SNAPSHOT_LIMIT = 60
    _SNAPSHOT_EVENTS = {
        "stage_checkpoint_ready",
        "stage_artifact_confirmed",
        "artifact_approved",
        "chapter_completed",
        "node_completed",
        "run_export_ready",
        "run_completed",
        "run_failed",
        "run_recovery_required",
        "run_paused",
        "run_checkpoint_recovery_requested",
        "run_snapshot_restored",
        "chapter_version_restored",
        "chapter_selection_revision_applied",
    }
    _NON_RESTORABLE_SNAPSHOT_EVENTS = {"run_failed", "run_recovery_required"}

    def is_snapshot_event(self, event_type: str) -> bool:
        return event_type in self._SNAPSHOT_EVENTS

    def latest_snapshot(self, run_id: str) -> dict[str, Any]:
        snapshots = self.list_snapshots(run_id)
        return next((item for item in snapshots if item.get("restorable")), {})

    def list_snapshots(self, run_id: str) -> list[dict[str, Any]]:
        data = self.read(run_id)
        return list(reversed([copy.deepcopy(item) for item in data.get("snapshots") or []]))

    def load_snapshot(self, run_id: str, snapshot_id: str) -> dict[str, Any]:
        self._validate_snapshot_id(snapshot_id)
        metadata = next((item for item in self.read(run_id).get("snapshots") or [] if item.get("snapshot_id") == snapshot_id), None)
        if metadata is None:
            raise FileNotFoundError(snapshot_id)
        path = self.run_dir(run_id) / "snapshots" / f"{snapshot_id}.json"
        if not path.exists():
            return copy.deepcopy(metadata)
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        state = payload.get("state") if isinstance(payload, dict) else None
        if isinstance(snapshot, dict) and isinstance(state, dict):
            expected_digest = str(snapshot.get("state_digest") or "")
            if expected_digest and digest(state) != expected_digest:
                raise ValueError("快照内容校验失败，不能恢复已损坏的状态")
            artifact_digests = snapshot.get("artifact_digests")
            artifacts = state.get("artifacts")
            if isinstance(artifact_digests, dict) and isinstance(artifacts, dict):
                for key, expected in artifact_digests.items():
                    if key in artifacts and digest(artifacts[key]) != expected:
                        raise ValueError("快照产物校验失败，不能恢复已损坏的状态")
        return payload

    def restore_snapshot(
        self,
        run_id: str,
        snapshot_id: str,
        *,
        request_id: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if not request_id or len(request_id) > 160:
            raise ValueError("恢复请求必须包含有效 request_id")
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            request_digest = digest({"snapshot_id": snapshot_id, "expected_revision": expected_revision})
            previous = (data.get("restore_requests") or {}).get(request_id)
            if previous:
                if previous.get("request_digest") != request_digest:
                    raise ValueError("同一 request_id 不能复用不同的恢复参数")
                return copy.deepcopy(previous.get("result") or {})
            if expected_revision is not None and int(data.get("state_revision") or 0) != expected_revision:
                raise ValueError("运行版本已变化，请刷新历史后再恢复")
            current_state = data.get("state") or {}
            if str(current_state.get("runtime_phase") or "") == "completed":
                raise ValueError("已完成运行不能原地恢复")
            if not data.get("paused") and str(current_state.get("runtime_phase") or "") in {"cockpit_streaming", "stage_streaming", "info_generating"}:
                raise ValueError("运行仍在执行，请先暂停后再恢复快照")
            metadata = next((item for item in data.get("snapshots") or [] if item.get("snapshot_id") == snapshot_id), None)
            if metadata is None:
                raise ValueError("快照不属于当前运行")
            if not metadata.get("restorable"):
                raise ValueError("该快照只可查看，不能作为恢复点")
            latest = next((item for item in reversed(data.get("snapshots") or []) if item.get("restorable")), None)
            if not latest or latest.get("snapshot_id") != snapshot_id:
                raise ValueError("只能恢复当前运行的最新稳定检查点")
            payload = self.load_snapshot(run_id, snapshot_id)
            snapshot_state = payload.get("state") if isinstance(payload, dict) else None
            if not isinstance(snapshot_state, dict):
                raise ValueError("快照缺少可恢复的运行状态")
            restored = copy.deepcopy(snapshot_state)
            # Usage and failure history are monotonic ledgers. Never roll them back with creative state.
            restored["budget_state"] = copy.deepcopy(current_state.get("budget_state") or restored.get("budget_state") or {})
            current_recovery = copy.deepcopy(current_state.get("recovery_state") or {})
            snapshot_recovery = copy.deepcopy(restored.get("recovery_state") or {})
            for key in ("status", "consecutive_failures", "total_failures", "failure_history", "last_failure", "recovery_count"):
                if key in current_recovery:
                    snapshot_recovery[key] = current_recovery[key]
            checkpoint = snapshot_recovery.get("last_stable_checkpoint") or _checkpoint_from_snapshot(metadata)
            snapshot_recovery.update(
                {
                    "status": "open" if snapshot_recovery.get("status") == "open" else "closed",
                    "needs_recovery": False,
                    "last_stable_checkpoint": checkpoint,
                    "last_recovery_at": now(),
                    "budget_recovery_prepared": False,
                }
            )
            restored["recovery_state"] = snapshot_recovery
            restored["errors"] = []
            restored["runtime_phase"] = "checkpoint_recovery"
            restored["run_has_started"] = True
            restored["mode_locked"] = True
            restored["run_completed_at"] = ""
            data["state"] = restored
            data["approval"] = copy.deepcopy(payload.get("approval") or {})
            data["paused"] = True
            data["pause_requested"] = True
            event = {
                "type": "run_snapshot_restored",
                "run_id": run_id,
                "snapshot_id": snapshot_id,
                "message": "已恢复到最新稳定检查点，等待用户明确继续创作。",
            }
            self._append_event(data, event, run_id=run_id)
            result = {
                "run_id": run_id,
                "snapshot_id": snapshot_id,
                "status": "restored_paused",
                "state_revision": int(data.get("state_revision") or 0) + 1,
                "event_seq": event["event_seq"],
            }
            data.setdefault("restore_requests", {})[request_id] = {
                "request_digest": request_digest,
                "snapshot_id": snapshot_id,
                "result": result,
            }
            self._persist(run_id, data)
            return result

    def _append_snapshot(self, data: dict[str, Any], event: dict[str, Any], run_id: str) -> None:
        state = data.get("state") or {}
        state_digest = digest(state)
        snapshot_id = f"snapshot-{int(event['event_seq']):08d}-{state_digest[:12]}"
        event_type = str(event.get("type") or "")
        metadata = {
            "snapshot_id": snapshot_id,
            "schema_version": 1,
            "kind": "stable_checkpoint" if event_type not in self._NON_RESTORABLE_SNAPSHOT_EVENTS else "run_state",
            "restorable": event_type not in self._NON_RESTORABLE_SNAPSHOT_EVENTS,
            "state_revision": int(data.get("state_revision") or 0) + 1,
            "event_seq": event["event_seq"],
            "event_type": event_type,
            "created_at": event["created_at"],
            "node_id": state.get("current_stage_id") or event.get("node_id") or "",
            "node_type": state.get("current_stage_type") or event.get("node_type") or "",
            "stage_label": state.get("current_stage_label") or event.get("label") or "",
            "output_key": event.get("output_key") or "",
            "chapter": event.get("chapter") or "",
            "phase": state.get("runtime_phase") or state.get("current_phase") or "",
            "current_checkpoint_stage_id": state.get("current_checkpoint_stage_id") or "",
            "pending_export_return": bool(state.get("pending_export_return")),
            "state_digest": state_digest,
            "artifact_digests": {
                str(key): digest(value)
                for key, value in (state.get("artifacts") or {}).items()
                if isinstance(state.get("artifacts"), dict)
            },
        }
        data.setdefault("snapshots", []).append(metadata)
        data["snapshots"] = data["snapshots"][-self._SNAPSHOT_LIMIT:]
        payload = {
            "snapshot": metadata,
            "state": copy.deepcopy(state),
            "approval": copy.deepcopy(data.get("approval") or {}),
            "paused": bool(data.get("paused")),
            "pause_requested": bool(data.get("pause_requested")),
        }
        snapshot_dir = self.run_dir(run_id) / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(snapshot_dir / f"{snapshot_id}.json", payload)
        retained = {str(item.get("snapshot_id")) for item in data["snapshots"]}
        for path in snapshot_dir.glob("snapshot-*.json"):
            if path.stem not in retained:
                path.unlink(missing_ok=True)

    @staticmethod
    def _validate_snapshot_id(snapshot_id: str) -> None:
        if not isinstance(snapshot_id, str) or not re.fullmatch(r"snapshot-[A-Za-z0-9-]{8,160}", snapshot_id):
            raise ValueError("Invalid snapshot_id")


def _checkpoint_from_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    node_id = str(metadata.get("node_id") or "")
    output_key = str(metadata.get("output_key") or node_id)
    if not node_id or not output_key:
        return {}
    return {
        "node_id": node_id,
        "node_type": str(metadata.get("node_type") or ""),
        "output_key": output_key,
        "chapter": str(metadata.get("chapter") or ""),
        "status": "restored_snapshot",
        "artifact_signature": str(metadata.get("state_digest") or ""),
        "created_at": str(metadata.get("created_at") or ""),
    }
