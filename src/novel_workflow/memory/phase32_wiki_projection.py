"""Rebuildable Wiki projection keyed by Phase 32 Canon transaction."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.phase32_writeback import Phase32CanonFact
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32WikiTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_ref: str = Field(pattern=r"^p32-canon-[a-f0-9]{64}$")
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    facts: tuple[Phase32CanonFact, ...] = Field(default=(), max_length=8)


class Phase32WikiProjectionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def project(
        self,
        *,
        run_id: str,
        transaction_ref: str,
        source_artifact_ref: str,
        facts: tuple[Phase32CanonFact, ...],
    ) -> Phase32WikiTransaction:
        safe_run_id = require_safe_id(run_id, label="run_id")
        require_safe_id(transaction_ref, label="transaction_ref")
        projection = Phase32WikiTransaction(
            transaction_ref=transaction_ref,
            source_artifact_ref=source_artifact_ref,
            facts=facts,
        )
        path = self.root / safe_run_id / f"{transaction_ref}.json"
        with self._lock:
            if path.exists():
                existing = Phase32WikiTransaction.model_validate(read_json(path))
                if existing != projection:
                    raise ValueError("Phase 32 Wiki projection is immutable")
                return existing
            atomic_write_json(path, projection.model_dump(mode="json"))
        return projection

    def list(self, run_id: str) -> tuple[Phase32WikiTransaction, ...]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return ()
        return tuple(
            Phase32WikiTransaction.model_validate(read_json(path))
            for path in sorted(directory.glob("p32-canon-*.json"))
        )


__all__ = ["Phase32WikiProjectionStore", "Phase32WikiTransaction"]
