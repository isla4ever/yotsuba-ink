from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import StageId, validate_artifact_vnext


ArtifactStatus = Literal["candidate", "committed", "rejected"]


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    run_id: str
    stage_id: StageId
    status: ArtifactStatus
    payload: dict[str, Any]
    signature: str = Field(min_length=64, max_length=64)
    created_at: str
    source: str


class ArtifactStore:
    _ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save_candidate(
        self,
        run_id: str,
        stage_id: StageId,
        payload: Any,
        *,
        source: str,
        subject_ids: set[str] | None = None,
        chapter_target: int | None = None,
        demand_keys: set[str] | None = None,
        turn_ids: set[str] | None = None,
        volume_cast_ids: dict[str, set[str]] | None = None,
        historical_subject_ids: set[str] | None = None,
        chapter_refs: set[str] | None = None,
        chapter_turn_refs: dict[str, list[str]] | None = None,
        chapter_version_ids: list[str] | None = None,
        cover_asset_ids: set[str] | None = None,
        export_title: str | None = None,
    ) -> ArtifactRecord:
        return self._write(
            run_id,
            stage_id,
            payload,
            status="candidate",
            source=source,
            subject_ids=subject_ids,
            chapter_target=chapter_target,
            demand_keys=demand_keys,
            turn_ids=turn_ids,
            volume_cast_ids=volume_cast_ids,
            historical_subject_ids=historical_subject_ids,
            chapter_refs=chapter_refs,
            chapter_turn_refs=chapter_turn_refs,
            chapter_version_ids=chapter_version_ids,
            cover_asset_ids=cover_asset_ids,
            export_title=export_title,
        )

    def commit(
        self,
        run_id: str,
        stage_id: StageId,
        payload: Any,
        *,
        source: str,
        subject_ids: set[str] | None = None,
        chapter_target: int | None = None,
        demand_keys: set[str] | None = None,
        turn_ids: set[str] | None = None,
        volume_cast_ids: dict[str, set[str]] | None = None,
        historical_subject_ids: set[str] | None = None,
        chapter_refs: set[str] | None = None,
        chapter_turn_refs: dict[str, list[str]] | None = None,
        chapter_version_ids: list[str] | None = None,
        cover_asset_ids: set[str] | None = None,
        export_title: str | None = None,
    ) -> ArtifactRecord:
        return self._write(
            run_id,
            stage_id,
            payload,
            status="committed",
            source=source,
            subject_ids=subject_ids,
            chapter_target=chapter_target,
            demand_keys=demand_keys,
            turn_ids=turn_ids,
            volume_cast_ids=volume_cast_ids,
            historical_subject_ids=historical_subject_ids,
            chapter_refs=chapter_refs,
            chapter_turn_refs=chapter_turn_refs,
            chapter_version_ids=chapter_version_ids,
            cover_asset_ids=cover_asset_ids,
            export_title=export_title,
        )

    def read(self, run_id: str, artifact_id: str) -> ArtifactRecord:
        path = self._artifact_path(run_id, artifact_id)
        if not path.exists():
            raise FileNotFoundError(artifact_id)
        return ArtifactRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def latest(self, run_id: str, stage_id: StageId, *, status: ArtifactStatus = "committed") -> ArtifactRecord:
        index = self._read_index(run_id)
        artifact_id = str((index.get(status) or {}).get(stage_id) or "")
        if not artifact_id:
            raise FileNotFoundError(f"{run_id}:{stage_id}:{status}")
        return self.read(run_id, artifact_id)

    def list(self, run_id: str, *, stage_id: StageId | None = None) -> list[ArtifactRecord]:
        directory = self._run_dir(run_id) / "artifacts"
        if not directory.exists():
            return []
        records = [ArtifactRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in directory.glob("*.json")]
        if stage_id is not None:
            records = [record for record in records if record.stage_id == stage_id]
        return sorted(records, key=lambda item: (item.created_at, item.artifact_id))

    def _write(
        self,
        run_id: str,
        stage_id: StageId,
        payload: Any,
        *,
        status: ArtifactStatus,
        source: str,
        subject_ids: set[str] | None,
        chapter_target: int | None,
        demand_keys: set[str] | None,
        turn_ids: set[str] | None,
        volume_cast_ids: dict[str, set[str]] | None,
        historical_subject_ids: set[str] | None,
        chapter_refs: set[str] | None,
        chapter_turn_refs: dict[str, list[str]] | None,
        chapter_version_ids: list[str] | None,
        cover_asset_ids: set[str] | None,
        export_title: str | None,
    ) -> ArtifactRecord:
        self._validate_id(run_id)
        validated = validate_artifact_vnext(
            stage_id,
            payload,
            subject_ids=subject_ids,
            chapter_target=chapter_target,
            demand_keys=demand_keys,
            turn_ids=turn_ids,
            volume_cast_ids=volume_cast_ids,
            historical_subject_ids=historical_subject_ids,
            chapter_refs=chapter_refs,
            chapter_turn_refs=chapter_turn_refs,
            chapter_version_ids=chapter_version_ids,
            cover_asset_ids=cover_asset_ids,
            export_title=export_title,
        ).model_dump(mode="json")
        signature = _digest({"stage_id": stage_id, "payload": validated})
        source_signature = hashlib.sha256(source.encode("utf-8")).hexdigest()
        artifact_id = f"{stage_id}-{status}-{signature[:20]}-{source_signature[:8]}"
        record = ArtifactRecord(
            artifact_id=artifact_id,
            run_id=run_id,
            stage_id=stage_id,
            status=status,
            payload=validated,
            signature=signature,
            created_at=_now(),
            source=source,
        )
        with self._lock:
            path = self._artifact_path(run_id, artifact_id)
            if path.exists():
                existing = ArtifactRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if existing != record.model_copy(update={"created_at": existing.created_at}):
                    raise ValueError("Artifact records are immutable")
                return existing
            self._atomic_write(path, record.model_dump(mode="json"))
            index = self._read_index(run_id)
            index.setdefault(status, {})[stage_id] = artifact_id
            self._atomic_write(self._run_dir(run_id) / "index.json", index)
        return record

    def _read_index(self, run_id: str) -> dict[str, Any]:
        path = self._run_dir(run_id) / "index.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _artifact_path(self, run_id: str, artifact_id: str) -> Path:
        self._validate_id(run_id)
        self._validate_id(artifact_id)
        return self._run_dir(run_id) / "artifacts" / f"{artifact_id}.json"

    def _run_dir(self, run_id: str) -> Path:
        self._validate_id(run_id)
        return self.root / run_id

    def _validate_id(self, value: str) -> None:
        if not isinstance(value, str) or not self._ID.fullmatch(value):
            raise ValueError("Invalid artifact store identifier")

    def _atomic_write(self, path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
