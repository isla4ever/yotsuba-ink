from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from novel_workflow.workflows.schemas import NovelRunState, WorkflowDefinition


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def create(self, run_id: str, workflow: WorkflowDefinition, inputs: dict[str, Any]) -> None:
        path = self.run_dir(run_id)
        path.mkdir(parents=True, exist_ok=True)
        self._write_json(path / "run.json", {"run_id": run_id, "workflow": workflow.model_dump(), "inputs": inputs, "events": []})

    def read(self, run_id: str) -> dict[str, Any]:
        path = self.run_dir(run_id) / "run.json"
        if not path.exists():
            raise FileNotFoundError(run_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        data = self.read(run_id)
        data.setdefault("events", []).append(event)
        self._write_json(self.run_dir(run_id) / "run.json", data)

    def request_pause(self, run_id: str) -> None:
        data = self.read(run_id)
        data["pause_requested"] = True
        self._write_json(self.run_dir(run_id) / "run.json", data)

    def mark_paused(self, run_id: str, paused: bool = True) -> None:
        data = self.read(run_id)
        data["paused"] = paused
        data["pause_requested"] = paused
        self._write_json(self.run_dir(run_id) / "run.json", data)

    def resume(self, run_id: str) -> None:
        data = self.read(run_id)
        data["pause_requested"] = False
        data["paused"] = False
        self._write_json(self.run_dir(run_id) / "run.json", data)

    def pause_requested(self, run_id: str) -> bool:
        return bool(self.read(run_id).get("pause_requested"))

    def request_approval(self, run_id: str, node_id: str, output_key: str, artifact: Any) -> None:
        data = self.read(run_id)
        data["approval"] = {
            "required": True,
            "node_id": node_id,
            "output_key": output_key,
            "artifact": artifact,
        }
        self._write_json(self.run_dir(run_id) / "run.json", data)

    def approval_pending(self, run_id: str, node_id: str = "") -> bool:
        approval = self.read(run_id).get("approval") or {}
        if node_id and approval.get("node_id") != node_id:
            return False
        return bool(approval.get("required"))

    def approve_artifact(self, run_id: str, node_id: str, output_key: str, artifact: Any) -> dict[str, Any]:
        data = self.read(run_id)
        approval = data.get("approval") or {}
        if approval.get("node_id") != node_id:
            raise ValueError(f"Run is not waiting for approval on node {node_id}")
        approval.update({
            "required": False,
            "approved": True,
            "output_key": output_key,
            "artifact": artifact,
        })
        data["approval"] = approval
        state = data.get("state") or {}
        artifacts = state.setdefault("artifacts", {})
        artifacts[output_key] = artifact
        state["approval_required"] = False
        approved = state.setdefault("approved_artifacts", {})
        approved[output_key] = artifact
        if output_key == "info_recommend":
            state["story_brief"] = {"source": "approved_artifact", "content": artifact}
        data["state"] = state
        self._write_json(self.run_dir(run_id) / "run.json", data)
        return approval

    def update_state(self, run_id: str, state: NovelRunState) -> None:
        data = self.read(run_id)
        data["state"] = state.model_dump()
        self._write_json(self.run_dir(run_id) / "run.json", data)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
