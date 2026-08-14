from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    kind: Literal["fact", "character", "relationship", "foreshadow", "spine"]
    claim: str = Field(min_length=1, max_length=2000)
    spans: list[EvidenceSpan] = Field(min_length=1)
    created_at: str


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(
        self,
        *,
        run_id: str,
        chapter_id: str,
        chapter_version_id: str,
        kind: Literal["fact", "character", "relationship", "foreshadow", "spine"],
        claim: str,
        spans: list[EvidenceSpan],
    ) -> EvidenceRecord:
        signature = hashlib.sha256(
            json.dumps(
                {"run_id": run_id, "chapter_id": chapter_id, "chapter_version_id": chapter_version_id, "kind": kind, "claim": claim, "spans": [item.model_dump() for item in spans]},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        record = EvidenceRecord(
            evidence_id=f"evidence-{signature[:24]}",
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_version_id=chapter_version_id,
            kind=kind,
            claim=claim,
            spans=spans,
            created_at=_now(),
        )
        path = self._path(run_id, record.evidence_id)
        with self._lock:
            if path.exists():
                return EvidenceRecord.model_validate(read_json(path))
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, evidence_id: str) -> EvidenceRecord:
        return EvidenceRecord.model_validate(read_json(self._path(run_id, evidence_id)))

    def list(self, run_id: str) -> list[EvidenceRecord]:
        require_safe_id(run_id, label="run_id")
        return [EvidenceRecord.model_validate(read_json(path)) for path in sorted((self.root / run_id).glob("*.json"))]

    def _path(self, run_id: str, evidence_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(evidence_id, label="evidence_id")
        return self.root / run_id / f"{evidence_id}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
