from __future__ import annotations

import threading
from pathlib import Path

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationContextEnvelope,
)
from novel_workflow.storage.atomic_json import (
    atomic_write_json,
    read_json,
    require_safe_id,
)


class CollaborationContextReceiptStore:
    """Immutable, private context material plus its public trace receipt."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(
        self,
        run_id: str,
        envelope: CollaborationContextEnvelope,
    ) -> CollaborationContextEnvelope:
        path = self._path(run_id, envelope.receipt.receipt_id)
        with self._lock:
            if path.exists():
                existing = CollaborationContextEnvelope.model_validate(read_json(path))
                expected = envelope.model_copy(
                    update={
                        "receipt": envelope.receipt.model_copy(
                            update={"created_at": existing.receipt.created_at}
                        )
                    }
                )
                if existing != expected:
                    raise ValueError("Collaboration context receipts are immutable")
                return existing
            atomic_write_json(path, envelope.model_dump(mode="json"))
        return envelope

    def read(self, run_id: str, receipt_id: str) -> CollaborationContextEnvelope:
        value = CollaborationContextEnvelope.model_validate(
            read_json(self._path(run_id, receipt_id))
        )
        if value.receipt.receipt_id != receipt_id:
            raise ValueError("Collaboration context receipt identity mismatch")
        return value

    def _path(self, run_id: str, receipt_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(receipt_id, label="collaboration receipt_id")
        return self.root / run_id / f"{receipt_id}.json"


__all__ = ["CollaborationContextReceiptStore"]
