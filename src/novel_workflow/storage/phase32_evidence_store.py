"""Immutable source-bound Evidence storage for Phase 32 accepted units."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from novel_workflow.output_contracts.phase32_writeback import Phase32EvidenceRecord
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def write(self, record: Phase32EvidenceRecord) -> Phase32EvidenceRecord:
        require_safe_id(record.run_id, label="run_id")
        require_safe_id(record.evidence_ref, label="evidence_ref")
        path = self._path(record.run_id, record.evidence_ref)
        with self._lock:
            if path.exists():
                existing = self.read(record.run_id, record.evidence_ref)
                if existing.model_copy(update={"created_at": record.created_at}) != record:
                    raise ValueError("Phase 32 Evidence is immutable")
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, evidence_ref: str) -> Phase32EvidenceRecord:
        return Phase32EvidenceRecord.model_validate(
            read_json(self._path(run_id, evidence_ref))
        )

    def list(self, run_id: str) -> tuple[Phase32EvidenceRecord, ...]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return ()
        return tuple(
            self.read(safe_run_id, path.stem)
            for path in sorted(directory.glob("p32-evidence-*.json"))
        )

    def for_source(
        self,
        run_id: str,
        source_artifact_ref: str,
    ) -> tuple[Phase32EvidenceRecord, ...]:
        return tuple(
            item for item in self.list(run_id)
            if item.source_artifact_ref == source_artifact_ref
        )

    def _path(self, run_id: str, evidence_ref: str) -> Path:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(evidence_ref, label="evidence_ref")
        return self.root / safe_run_id / f"{safe_ref}.json"


def phase32_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["Phase32EvidenceStore", "phase32_now"]
