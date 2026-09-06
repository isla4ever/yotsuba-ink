"""Immutable Phase 32 collaboration context receipts and private material."""

from __future__ import annotations

import threading
from pathlib import Path

from novel_workflow.output_contracts.phase32_author_collaboration import (
    Phase32CollaborationContextEnvelope,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32CollaborationContextStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(
        self,
        run_id: str,
        envelope: Phase32CollaborationContextEnvelope,
    ) -> Phase32CollaborationContextEnvelope:
        path = self._path(run_id, envelope.receipt.receipt_id)
        with self._lock:
            if path.exists():
                existing = self.read(run_id, envelope.receipt.receipt_id)
                expected = envelope.model_copy(
                    update={
                        "receipt": envelope.receipt.model_copy(
                            update={"created_at": existing.receipt.created_at}
                        )
                    }
                )
                if existing != expected:
                    raise ValueError("Phase 32 collaboration context is immutable")
                return existing
            atomic_write_json(path, envelope.model_dump(mode="json"))
        return envelope

    def read(
        self,
        run_id: str,
        receipt_id: str,
    ) -> Phase32CollaborationContextEnvelope:
        value = Phase32CollaborationContextEnvelope.model_validate(
            read_json(self._path(run_id, receipt_id))
        )
        if value.receipt.run_id != run_id or value.receipt.receipt_id != receipt_id:
            raise ValueError("Phase 32 collaboration context identity mismatch")
        return value

    def _path(self, run_id: str, receipt_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(receipt_id, label="receipt_id")
        return self.root / run_id / f"{receipt_id}.json"


__all__ = ["Phase32CollaborationContextStore"]
