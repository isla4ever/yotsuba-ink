"""Immutable Canon transaction authority for Phase 32 Runs."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from novel_workflow.output_contracts.phase32_writeback import (
    Phase32CanonFact,
    Phase32CanonTransaction,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.phase32_evidence_store import phase32_now


class Phase32CanonStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def commit(
        self,
        *,
        run_id: str,
        transaction_ref: str,
        source_artifact_ref: str,
        facts: tuple[Phase32CanonFact, ...],
    ) -> Phase32CanonTransaction:
        safe_run_id = require_safe_id(run_id, label="run_id")
        require_safe_id(transaction_ref, label="transaction_ref")
        transaction = Phase32CanonTransaction(
            transaction_ref=transaction_ref,
            run_id=safe_run_id,
            source_artifact_ref=source_artifact_ref,
            facts=facts,
            committed_at=phase32_now(),
        )
        path = self.root / safe_run_id / f"{transaction_ref}.json"
        with self._lock:
            if path.exists():
                existing = Phase32CanonTransaction.model_validate(read_json(path))
                if existing.model_copy(update={"committed_at": transaction.committed_at}) != transaction:
                    raise ValueError("Phase 32 Canon transaction is immutable")
                return existing
            atomic_write_json(path, transaction.model_dump(mode="json"))
        return transaction

    def transactions(self, run_id: str) -> tuple[Phase32CanonTransaction, ...]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return ()
        return tuple(
            Phase32CanonTransaction.model_validate(read_json(path))
            for path in sorted(directory.glob("p32-canon-*.json"))
        )

    def facts(self, run_id: str) -> tuple[Phase32CanonFact, ...]:
        return tuple(
            fact for transaction in self.transactions(run_id) for fact in transaction.facts
        )

    def fact(self, run_id: str, fact_ref: str) -> Phase32CanonFact:
        for fact in self.facts(run_id):
            if fact.fact_ref == fact_ref:
                return fact
        raise FileNotFoundError(fact_ref)


__all__ = ["Phase32CanonStore"]
