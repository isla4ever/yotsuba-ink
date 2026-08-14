from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class ContextManifestRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    manifest_id: str = Field(pattern=r"^manifest-[a-f0-9]{64}$")
    chapter_id: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    attempt: int = Field(ge=1)
    manifest: ContextManifest
    created_at: str


class ContextManifestStore:
    """Run-scoped immutable inputs frozen before a chapter Provider call."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(
        self,
        run_id: str,
        *,
        attempt: int,
        manifest: ContextManifest,
    ) -> ContextManifestRecord:
        require_safe_id(run_id, label="run_id")
        if attempt < 1:
            raise ValueError("Context Manifest attempt must be positive")
        manifest_id = _manifest_id(attempt, manifest)
        record = ContextManifestRecord(
            run_id=run_id,
            manifest_id=manifest_id,
            chapter_id=manifest.task,
            attempt=attempt,
            manifest=manifest,
            created_at=_now(),
        )
        path = self._path(run_id, manifest_id)
        with self._lock:
            if path.exists():
                existing = ContextManifestRecord.model_validate(read_json(path))
                _validate_identity(existing, manifest_id)
                if (
                    existing.chapter_id != record.chapter_id
                    or existing.attempt != record.attempt
                    or existing.manifest != record.manifest
                ):
                    raise ValueError("Context Manifest id was reused with different content")
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, manifest_id: str) -> ContextManifestRecord:
        record = ContextManifestRecord.model_validate(
            read_json(self._path(run_id, manifest_id))
        )
        _validate_identity(record, manifest_id)
        if record.run_id != run_id:
            raise ValueError("Context Manifest Run identity mismatch")
        return record

    def list(self, run_id: str) -> list[ContextManifestRecord]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id
        if not directory.exists():
            return []
        records = [self.read(run_id, path.stem) for path in directory.glob("*.json")]
        return sorted(
            records,
            key=lambda item: (
                int(item.chapter_id.removeprefix("chapter-")),
                item.attempt,
                item.created_at,
            ),
        )

    def copy(
        self,
        *,
        source_run_id: str,
        target_run_id: str,
        manifest_id: str,
    ) -> ContextManifestRecord:
        source = self.read(source_run_id, manifest_id)
        target = source.model_copy(update={"run_id": target_run_id})
        path = self._path(target_run_id, manifest_id)
        with self._lock:
            if path.exists():
                existing = ContextManifestRecord.model_validate(read_json(path))
                _validate_identity(existing, manifest_id)
                if existing != target:
                    raise ValueError("Branch Context Manifest is immutable")
                return existing
            atomic_write_json(path, target.model_dump(mode="json"))
        return target

    def _path(self, run_id: str, manifest_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(manifest_id, label="manifest_id")
        return self.root / run_id / f"{manifest_id}.json"


def _manifest_id(attempt: int, manifest: ContextManifest) -> str:
    payload = {
        "attempt": attempt,
        "manifest": manifest.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"manifest-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _validate_identity(record: ContextManifestRecord, manifest_id: str) -> None:
    if record.manifest_id != manifest_id:
        raise ValueError("Context Manifest record identity mismatch")
    if record.chapter_id != record.manifest.task:
        raise ValueError("Context Manifest chapter identity mismatch")
    if _manifest_id(record.attempt, record.manifest) != manifest_id:
        raise ValueError("Context Manifest record content does not match its identity")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["ContextManifestRecord", "ContextManifestStore"]
