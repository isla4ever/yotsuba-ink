from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class StageArtifactDraftRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    run_id: str
    stage_id: StageId
    decision_id: str = Field(min_length=1, max_length=240)
    domain_revision: int = Field(ge=0)
    source_artifact_id: str = Field(min_length=1, max_length=240)
    payload: dict[str, Any]
    signature: str = Field(min_length=64, max_length=64)
    created_at: str


class StageArtifactDraftStore:
    """Immutable edit history with one latest pointer per graph decision."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save(
        self,
        *,
        run_id: str,
        stage_id: StageId,
        decision_id: str,
        domain_revision: int,
        source_artifact_id: str,
        payload: dict[str, Any],
    ) -> StageArtifactDraftRecord:
        require_safe_id(run_id, label="run_id")
        require_safe_id(decision_id, label="decision_id")
        require_safe_id(source_artifact_id, label="source_artifact_id")
        signed = {
            "run_id": run_id,
            "stage_id": stage_id,
            "decision_id": decision_id,
            "domain_revision": domain_revision,
            "source_artifact_id": source_artifact_id,
            "payload": payload,
        }
        signature = _digest(signed)
        record = StageArtifactDraftRecord(
            draft_id=f"{stage_id}-draft-{signature[:24]}",
            signature=signature,
            created_at=_now(),
            **signed,
        )
        with self._lock:
            path = self._draft_path(run_id, record.draft_id)
            if path.exists():
                existing = StageArtifactDraftRecord.model_validate(read_json(path))
                if existing != record.model_copy(update={"created_at": existing.created_at}):
                    raise ValueError("Stage Artifact draft records are immutable")
                record = existing
            else:
                atomic_write_json(path, record.model_dump(mode="json"))
            index = self._read_index(run_id)
            index.setdefault("decisions", {})[_decision_key(decision_id)] = {
                "decision_id": decision_id,
                "draft_id": record.draft_id,
            }
            atomic_write_json(self._run_dir(run_id) / "index.json", index)
        return record

    def read(self, run_id: str, draft_id: str) -> StageArtifactDraftRecord:
        return StageArtifactDraftRecord.model_validate(
            read_json(self._draft_path(run_id, draft_id))
        )

    def latest(self, run_id: str, decision_id: str) -> StageArtifactDraftRecord:
        require_safe_id(decision_id, label="decision_id")
        pointer = (self._read_index(run_id).get("decisions") or {}).get(
            _decision_key(decision_id)
        )
        if not isinstance(pointer, dict) or pointer.get("decision_id") != decision_id:
            raise FileNotFoundError(decision_id)
        return self.read(run_id, str(pointer.get("draft_id") or ""))

    def list(self, run_id: str) -> list[StageArtifactDraftRecord]:
        directory = self._run_dir(run_id) / "drafts"
        if not directory.exists():
            return []
        records = [
            StageArtifactDraftRecord.model_validate(read_json(path))
            for path in directory.glob("*.json")
        ]
        return sorted(records, key=lambda item: (item.created_at, item.draft_id))

    def _read_index(self, run_id: str) -> dict[str, Any]:
        path = self._run_dir(run_id) / "index.json"
        return read_json(path) if path.exists() else {}

    def _draft_path(self, run_id: str, draft_id: str) -> Path:
        require_safe_id(draft_id, label="draft_id")
        return self._run_dir(run_id) / "drafts" / f"{draft_id}.json"

    def _run_dir(self, run_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        return self.root / run_id


def _decision_key(decision_id: str) -> str:
    return hashlib.sha256(decision_id.encode("utf-8")).hexdigest()


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["StageArtifactDraftRecord", "StageArtifactDraftStore"]
