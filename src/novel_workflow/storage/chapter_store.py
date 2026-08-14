from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class ChapterRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    chapter_id: str
    version_id: str
    artifact: ChapterArtifact
    signature: str = Field(min_length=64, max_length=64)
    created_at: str


class ChapterStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(self, run_id: str, payload: dict[str, object]) -> ChapterRecord:
        require_safe_id(run_id, label="run_id")
        artifact = ChapterArtifact.model_validate(payload)
        signature = _digest(artifact.model_dump(mode="json"))
        if not artifact.version_id:
            raise ValueError("Chapter version_id is required")
        record = ChapterRecord(
            run_id=run_id,
            chapter_id=artifact.chapter_id,
            version_id=artifact.version_id,
            artifact=artifact,
            signature=signature,
            created_at=_now(),
        )
        path = self._path(run_id, artifact.chapter_id, artifact.version_id)
        with self._lock:
            if path.exists():
                existing = ChapterRecord.model_validate(read_json(path))
                if existing.signature != signature:
                    raise ValueError("Chapter version_id was reused with different content")
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
            atomic_write_json(
                self.root / run_id / artifact.chapter_id / "latest.json",
                {"version_id": artifact.version_id},
            )
        return record

    def read(self, run_id: str, chapter_id: str, version_id: str) -> ChapterRecord:
        return ChapterRecord.model_validate(read_json(self._path(run_id, chapter_id, version_id)))

    def latest(self, run_id: str, chapter_id: str) -> ChapterRecord:
        pointer = read_json(self.root / run_id / chapter_id / "latest.json")
        return self.read(run_id, chapter_id, str(pointer["version_id"]))

    def list(self, run_id: str) -> list[ChapterRecord]:
        require_safe_id(run_id, label="run_id")
        records = [
            ChapterRecord.model_validate(read_json(path))
            for path in (self.root / run_id).glob("*/*.json")
            if path.name != "latest.json"
        ]
        return sorted(records, key=lambda item: (item.chapter_id, item.created_at))

    def latest_word_total(self, run_id: str) -> int:
        """Character count across the latest version of every chapter in a run.

        Reads raw JSON instead of validating full ChapterRecords: this backs the
        run-history word column, which lists many runs at once.
        """
        require_safe_id(run_id, label="run_id")
        run_dir = self.root / run_id
        if not run_dir.exists():
            return 0
        total = 0
        for pointer_path in run_dir.glob("*/latest.json"):
            try:
                pointer = read_json(pointer_path)
                record = read_json(pointer_path.parent / f"{pointer['version_id']}.json")
                content = record.get("artifact", {}).get("content", "")
            except (OSError, ValueError, KeyError):
                continue
            total += len(str(content))
        return total

    def _path(self, run_id: str, chapter_id: str, version_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(chapter_id, label="chapter_id")
        require_safe_id(version_id, label="version_id")
        return self.root / run_id / chapter_id / f"{version_id}.json"


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
