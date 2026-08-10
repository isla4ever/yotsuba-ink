from __future__ import annotations

import threading
from pathlib import Path

from novel_workflow.memory.canon_store import CanonFact
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class WikiProjectionStore:
    """Rebuildable user-facing projection keyed by Canon transaction."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def project(self, run_id: str, transaction_id: str, facts: list[CanonFact]) -> dict[str, object]:
        require_safe_id(run_id, label="run_id")
        require_safe_id(transaction_id, label="transaction_id")
        path = self.root / run_id / f"{transaction_id}.json"
        value = {"transaction_id": transaction_id, "facts": [item.model_dump(mode="json") for item in facts]}
        with self._lock:
            if path.exists():
                existing = read_json(path)
                if existing != value:
                    raise ValueError("Wiki projection transaction is immutable")
                return existing
            atomic_write_json(path, value)
            return value

    def list(self, run_id: str) -> list[dict[str, object]]:
        require_safe_id(run_id, label="run_id")
        return [read_json(path) for path in sorted((self.root / run_id).glob("*.json"))]
