from __future__ import annotations

import copy
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from novel_workflow.storage.run_control_store import RunControlStoreMixin
from novel_workflow.storage.run_cover_asset_store import RunCoverAssetStoreMixin
from novel_workflow.storage.run_export_store import RunExportStoreMixin
from novel_workflow.storage.run_history_store import RunHistoryStoreMixin
from novel_workflow.storage.run_snapshot_store import RunSnapshotStoreMixin
from novel_workflow.storage.run_stream_store import RunStreamLeaseStoreMixin
from novel_workflow.storage.run_store_support import next_legacy_event_seq, now
from novel_workflow.workflows.schemas import NovelRunState, WorkflowDefinition


class RunStore(
    RunControlStoreMixin,
    RunCoverAssetStoreMixin,
    RunExportStoreMixin,
    RunHistoryStoreMixin,
    RunSnapshotStoreMixin,
    RunStreamLeaseStoreMixin,
):
    _RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()
        self._init_stream_leases()

    def run_dir(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        return self.root / run_id

    def create(self, run_id: str, workflow: WorkflowDefinition, inputs: dict[str, Any], *, project_id: str = "") -> None:
        with self._lock_for(run_id):
            path = self.run_dir(run_id)
            path.mkdir(parents=True, exist_ok=True)
            if (path / "run.json").exists():
                raise FileExistsError(run_id)
            created_at = now()
            self._persist(
                run_id,
                {
                    "run_id": run_id,
                    "project_id": str(project_id or inputs.get("project_id") or run_id),
                    "workflow": workflow.model_dump(),
                    "inputs": copy.deepcopy(inputs),
                    "events": [],
                    "event_index": {},
                    "event_seq_index": {},
                    "next_event_seq": 1,
                    "state_revision": 0,
                    "state": None,
                    "snapshots": [],
                    "exports": [],
                    "export_requests": {},
                    "restore_requests": {},
                    "created_at": created_at,
                    "updated_at": created_at,
                    "completed_at": "",
                    "parent_run_id": "",
                    "restored_from_snapshot_id": "",
                },
                bump_revision=False,
            )

    def read(self, run_id: str) -> dict[str, Any]:
        with self._lock_for(run_id):
            return self._read_unlocked(run_id)

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            self._append_event(data, event, run_id=run_id)
            self._persist(run_id, data)

    def commit_state_event(
        self,
        run_id: str,
        state: NovelRunState,
        event: dict[str, Any],
        *,
        approval: dict[str, Any] | None = None,
    ) -> None:
        self.commit_state_events(run_id, state, [event], approval=approval)

    def commit_state_events(
        self,
        run_id: str,
        state: NovelRunState,
        events: list[dict[str, Any]],
        *,
        approval: dict[str, Any] | None = None,
    ) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            if state.runtime_phase == "completed" and not state.run_completed_at:
                state.run_completed_at = now()
            data["state"] = state.model_dump()
            if state.runtime_phase == "completed":
                data["completed_at"] = state.run_completed_at
            if approval is not None:
                data["approval"] = copy.deepcopy(approval)
            for event in events:
                self._append_event(data, event, run_id=run_id)
            self._persist(run_id, data)

    def update_state(self, run_id: str, state: NovelRunState) -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            if state.runtime_phase == "completed" and not state.run_completed_at:
                state.run_completed_at = now()
            data["state"] = state.model_dump()
            if state.runtime_phase == "completed" and not data.get("completed_at"):
                data["completed_at"] = state.run_completed_at
            self._persist(run_id, data)

    def _append_event(self, data: dict[str, Any], event: dict[str, Any], *, run_id: str) -> None:
        event.setdefault("created_at", now())
        next_event_seq = int(data.get("next_event_seq") or next_legacy_event_seq(data.get("events") or []))
        event["event_seq"] = next_event_seq
        data["next_event_seq"] = next_event_seq + 1
        data.setdefault("events", []).append(event)
        event_position = len(data["events"]) - 1
        data.setdefault("event_seq_index", {})[str(next_event_seq)] = event_position
        node_id = str(event.get("node_id") or "")
        if node_id:
            data.setdefault("event_index", {})[node_id] = event_position
        if self.is_snapshot_event(str(event.get("type") or "")) and data.get("state"):
            self._append_snapshot(data, event, run_id)

    def _persist(self, run_id: str, data: dict[str, Any], *, bump_revision: bool = True) -> None:
        if bump_revision:
            data["state_revision"] = int(data.get("state_revision") or 0) + 1
        data["updated_at"] = now()
        self._write_json(self.run_dir(run_id) / "run.json", data)
        self._write_json(self.run_dir(run_id) / "run_meta.json", self._summary(data))

    def _read_unlocked(self, run_id: str) -> dict[str, Any]:
        path = self.run_dir(run_id) / "run.json"
        if not path.exists():
            raise FileNotFoundError(run_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _lock_for(self, run_id: str) -> threading.RLock:
        self._validate_run_id(run_id)
        with self._locks_guard:
            return self._locks.setdefault(run_id, threading.RLock())

    @classmethod
    def _validate_run_id(cls, run_id: str) -> None:
        if not isinstance(run_id, str) or not cls._RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid run_id")

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

    def _write_bytes(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_bytes(content)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
