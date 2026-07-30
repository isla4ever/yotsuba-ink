from __future__ import annotations

import copy
from typing import Any

from novel_workflow.storage.run_store_support import now


class RunControlStoreMixin:
    def update_fields(self, run_id: str, **fields: Any) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            data.update(copy.deepcopy(fields))
            self._persist(run_id, data)

    def request_pause(self, run_id: str) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            data["pause_requested"] = True
            self._persist(run_id, data)

    def mark_paused(self, run_id: str, paused: bool = True) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            data["paused"] = paused
            data["pause_requested"] = paused
            self._persist(run_id, data)

    def resume(self, run_id: str) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            data["pause_requested"] = False
            data["paused"] = False
            self._persist(run_id, data)

    def pause_requested(self, run_id: str) -> bool:
        return bool(self.read(run_id).get("pause_requested"))

    def request_approval(self, run_id: str, node_id: str, output_key: str, artifact: Any) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            data["approval"] = {
                "required": True,
                "node_id": node_id,
                "output_key": output_key,
                "artifact": copy.deepcopy(artifact),
            }
            self._persist(run_id, data)

    def approval_pending(self, run_id: str, node_id: str = "") -> bool:
        approval = self.read(run_id).get("approval") or {}
        if node_id and approval.get("node_id") != node_id:
            return False
        return bool(approval.get("required"))

    def approve_artifact(self, run_id: str, node_id: str, output_key: str, artifact: Any) -> dict[str, Any]:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            approval = data.get("approval") or {}
            if approval.get("node_id") != node_id:
                raise ValueError(f"Run is not waiting for approval on node {node_id}")
            approval.update({
                "required": False,
                "approved": True,
                "output_key": output_key,
                "artifact": copy.deepcopy(artifact),
            })
            data["approval"] = approval
            state = data.get("state") or {}
            state.setdefault("artifacts", {})[output_key] = copy.deepcopy(artifact)
            state["approval_required"] = False
            state.setdefault("approved_artifacts", {})[output_key] = copy.deepcopy(artifact)
            stage_confirmations = state.setdefault("stage_confirmation_state", {})
            if node_id:
                stage_confirmations[node_id] = {
                    "status": "confirmed",
                    "node_id": node_id,
                    "node_type": state.get("current_stage_type") or "",
                    "output_key": output_key,
                }
                completed = state.setdefault("completed_stage_ids", [])
                if node_id not in completed:
                    completed.append(node_id)
                state["current_checkpoint_stage_id"] = node_id
                state["runtime_phase"] = "stage_ready_to_continue"
            if output_key == "info_recommend":
                state["story_brief"] = {"source": "approved_artifact", "content": copy.deepcopy(artifact)}
            data["state"] = state
            self._persist(run_id, data)
            return approval

    def mark_stage_completed(self, run_id: str, node_id: str, *, pending_export_return: bool = False) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            state = data.get("state") or {}
            completed = state.setdefault("completed_stage_ids", [])
            if node_id and node_id not in completed:
                completed.append(node_id)
            state["current_stage_id"] = node_id
            state["current_checkpoint_stage_id"] = node_id
            state["pending_export_return"] = pending_export_return
            data["state"] = state
            self._persist(run_id, data)

    def set_runtime_phase(self, run_id: str, phase: str, *, stage_id: str = "", stage_type: str = "") -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            state = data.get("state") or {}
            state["runtime_phase"] = phase
            if stage_id:
                state["current_stage_id"] = stage_id
                state["current_checkpoint_stage_id"] = stage_id
            if stage_type:
                state["current_stage_type"] = stage_type
            if phase == "completed":
                state["run_completed_at"] = now()
                data["completed_at"] = state["run_completed_at"]
            data["state"] = state
            self._persist(run_id, data)
