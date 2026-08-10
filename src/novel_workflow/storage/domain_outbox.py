from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from novel_workflow.memory.canon_store import CanonFact, CanonStore
from novel_workflow.memory.wiki_projection import WikiProjectionStore
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class OutboxOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    run_id: str
    transaction_id: str
    facts: list[CanonFact]
    status: Literal["queued", "committed", "failed"] = "queued"
    created_at: str
    committed_at: str = ""
    error: str = ""


class DomainOutbox:
    def __init__(self, root: Path, *, canon: CanonStore, wiki: WikiProjectionStore) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.canon = canon
        self.wiki = wiki
        self._lock = threading.RLock()

    def enqueue(self, run_id: str, operation_id: str, transaction_id: str, facts: list[CanonFact]) -> OutboxOperation:
        path = self._path(run_id, operation_id)
        with self._lock:
            if path.exists():
                existing = OutboxOperation.model_validate(read_json(path))
                if existing.transaction_id != transaction_id or existing.facts != facts:
                    raise ValueError("Outbox operation is immutable")
                return existing
            operation = OutboxOperation(
                operation_id=operation_id,
                run_id=run_id,
                transaction_id=transaction_id,
                facts=facts,
                created_at=_now(),
            )
            atomic_write_json(path, operation.model_dump(mode="json"))
            return operation

    def flush(self, run_id: str, operation_id: str) -> OutboxOperation:
        path = self._path(run_id, operation_id)
        with self._lock:
            operation = OutboxOperation.model_validate(read_json(path))
            if operation.status == "committed":
                return operation
            try:
                self.canon.commit(run_id, operation.transaction_id, operation.facts)
                self.wiki.project(run_id, operation.transaction_id, operation.facts)
            except Exception as exc:
                failed = operation.model_copy(update={"status": "failed", "error": str(exc)})
                atomic_write_json(path, failed.model_dump(mode="json"))
                raise
            committed = operation.model_copy(update={"status": "committed", "committed_at": _now(), "error": ""})
            atomic_write_json(path, committed.model_dump(mode="json"))
            return committed

    def read(self, run_id: str, operation_id: str) -> OutboxOperation:
        return OutboxOperation.model_validate(read_json(self._path(run_id, operation_id)))

    def _path(self, run_id: str, operation_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(operation_id, label="operation_id")
        return self.root / run_id / f"{operation_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
