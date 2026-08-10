from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class CanonFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    claim: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(min_length=1)
    chapter_version_id: str = Field(min_length=1)


class CanonTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    run_id: str
    facts: list[CanonFact]
    committed_at: str


class CanonStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def commit(self, run_id: str, transaction_id: str, facts: list[CanonFact]) -> CanonTransaction:
        require_safe_id(run_id, label="run_id")
        require_safe_id(transaction_id, label="transaction_id")
        path = self.root / run_id / f"{transaction_id}.json"
        with self._lock:
            if path.exists():
                existing = CanonTransaction.model_validate(read_json(path))
                if existing.facts != facts:
                    raise ValueError("Canon transaction is immutable")
                return existing
            transaction = CanonTransaction(
                transaction_id=transaction_id,
                run_id=run_id,
                facts=facts,
                committed_at=_now(),
            )
            atomic_write_json(path, transaction.model_dump(mode="json"))
            return transaction

    def facts(self, run_id: str) -> list[CanonFact]:
        require_safe_id(run_id, label="run_id")
        facts: list[CanonFact] = []
        for path in sorted((self.root / run_id).glob("*.json")):
            facts.extend(CanonTransaction.model_validate(read_json(path)).facts)
        return facts


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
