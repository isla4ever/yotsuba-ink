from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.storage.atomic_json import require_safe_id


class RunEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    sequence: int = Field(ge=1)
    occurred_at: str
    run_id: str
    thread_id: str
    type: str
    stage_id: StageId | None = None
    node_id: str = ""
    chapter_id: str = ""
    status: str = ""
    payload: dict[str, Any] | None = None
    payload_ref: str = ""
    checkpoint_id: str = ""


class EventProjection:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def append(
        self,
        run_id: str,
        *,
        event_id: str,
        type: str,
        stage_id: StageId | None = None,
        node_id: str = "",
        chapter_id: str = "",
        status: str = "",
        payload: dict[str, Any] | None = None,
        payload_ref: str = "",
        checkpoint_id: str = "",
    ) -> RunEventEnvelope:
        require_safe_id(run_id, label="run_id")
        require_safe_id(event_id, label="event_id")
        with self._lock:
            events = self.read(run_id)
            existing = next((item for item in events if item.event_id == event_id), None)
            if existing is not None:
                return existing
            event = RunEventEnvelope(
                event_id=event_id,
                sequence=len(events) + 1,
                occurred_at=_now(),
                run_id=run_id,
                thread_id=run_id,
                type=type,
                stage_id=stage_id,
                node_id=node_id,
                chapter_id=chapter_id,
                status=status,
                payload=payload,
                payload_ref=payload_ref,
                checkpoint_id=checkpoint_id,
            )
            path = self._path(run_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
            return event

    def read(self, run_id: str, *, after: int = 0) -> list[RunEventEnvelope]:
        path = self._path(run_id)
        if not path.exists():
            return []
        events = [
            RunEventEnvelope.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [event for event in events if event.sequence > after]

    def _path(self, run_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        return self.root / run_id / "events.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
