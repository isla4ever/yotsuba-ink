"""Immutable candidate/committed storage for Phase 32 core Artifacts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.phase32_route_artifacts import (
    Phase32CoreArtifact,
    bind_phase32_artifact,
    phase32_artifact_binding,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


ArtifactRecordStatus = Literal["candidate", "committed"]


class Phase32ArtifactRecord(BaseModel):
    """Storage metadata around one immutable core Artifact payload."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    artifact_ref: str = Field(pattern=r"^p32-[a-z][a-z0-9_-]{1,63}-(?:candidate|committed)-[a-f0-9]{24,64}(?:-[a-f0-9]{8})?$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    creation_route_id: CreationRouteId
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    artifact_kind: ArtifactKind
    status: ArtifactRecordStatus
    payload: dict[str, Any]
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_operation_key: str = Field(min_length=1, max_length=500)
    created_at: str = Field(min_length=1, max_length=80)

    def validate_payload(self) -> "Phase32ArtifactRecord":
        if self.payload_digest != canonical_digest(self.payload):
            raise ValueError("Phase 32 Artifact payload digest does not match its payload")
        binding = phase32_artifact_binding(self.creation_route_id, self.stage_id)
        artifact = binding.model_type.model_validate(self.payload)
        bind_phase32_artifact(self.creation_route_id, self.stage_id, artifact)
        if self.artifact_kind != binding.artifact_kind:
            raise ValueError("Phase 32 Artifact kind does not match its stage binding")
        return self


class Phase32ArtifactStoreError(ValueError):
    code = "phase32_artifact_store_invalid"


class Phase32ArtifactStore:
    """Content-addressed JSON store with immutable candidate/commit records."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def save_candidate(
        self,
        *,
        run_id: str,
        creation_route_id: CreationRouteId,
        stage_id: str,
        artifact: Phase32CoreArtifact,
        source_operation_key: str,
    ) -> Phase32ArtifactRecord:
        payload, binding = _validated_payload(creation_route_id, stage_id, artifact)
        digest = canonical_digest(payload)
        operation_digest = hashlib.sha256(source_operation_key.encode("utf-8")).hexdigest()
        record = Phase32ArtifactRecord(
            artifact_ref=f"p32-{stage_id}-candidate-{digest[:32]}-{operation_digest[:8]}",
            run_id=require_safe_id(run_id, label="run_id"),
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            artifact_kind=binding.artifact_kind,
            status="candidate",
            payload=payload,
            payload_digest=digest,
            source_operation_key=source_operation_key,
            created_at=_now(),
        ).validate_payload()
        return self._write_immutable(record)

    def commit_candidate(
        self,
        *,
        run_id: str,
        creation_route_id: CreationRouteId,
        stage_id: str,
        candidate_ref: str,
    ) -> Phase32ArtifactRecord:
        candidate = self.read(run_id, candidate_ref)
        if (
            candidate.creation_route_id != creation_route_id
            or candidate.stage_id != stage_id
            or candidate.status != "candidate"
        ):
            raise Phase32ArtifactStoreError("Candidate does not belong to the requested route stage")
        committed_ref = f"p32-{stage_id}-committed-{candidate.payload_digest}"
        record = candidate.model_copy(
            update={
                "artifact_ref": committed_ref,
                "status": "committed",
                "source_operation_key": f"commit:{candidate.artifact_ref}",
                "created_at": _now(),
            }
        ).validate_payload()
        committed_path = self.root / candidate.run_id / f"{committed_ref}.json"
        if committed_path.exists():
            existing = self.read(candidate.run_id, committed_ref)
            if (
                existing.status != "committed"
                or existing.creation_route_id != creation_route_id
                or existing.stage_id != stage_id
                or existing.payload_digest != candidate.payload_digest
            ):
                raise Phase32ArtifactStoreError("Committed Artifact identity is not immutable")
            return existing
        return self._write_immutable(record)

    def save_deterministic(
        self,
        *,
        run_id: str,
        creation_route_id: CreationRouteId,
        stage_id: str,
        artifact: Phase32CoreArtifact,
    ) -> Phase32ArtifactRecord:
        candidate = self.save_candidate(
            run_id=run_id,
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            artifact=artifact,
            source_operation_key=f"deterministic:{run_id}:{stage_id}",
        )
        return self.commit_candidate(
            run_id=run_id,
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            candidate_ref=candidate.artifact_ref,
        )

    def copy_committed(
        self,
        *,
        source_run_id: str,
        target_run_id: str,
        creation_route_id: CreationRouteId,
        stage_id: str,
        source_artifact_ref: str,
        source_operation_key: str,
    ) -> Phase32ArtifactRecord:
        source = self.read(source_run_id, source_artifact_ref)
        if (
            source.status != "committed"
            or source.creation_route_id != creation_route_id
            or source.stage_id != stage_id
        ):
            raise Phase32ArtifactStoreError(
                "Only a committed Artifact from the same route stage may be copied"
            )
        binding = phase32_artifact_binding(creation_route_id, stage_id)
        artifact = binding.model_type.model_validate(source.payload)
        candidate = self.save_candidate(
            run_id=target_run_id,
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            artifact=artifact,
            source_operation_key=source_operation_key,
        )
        committed = self.commit_candidate(
            run_id=target_run_id,
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            candidate_ref=candidate.artifact_ref,
        )
        if committed.artifact_ref != source.artifact_ref:
            raise Phase32ArtifactStoreError(
                "Copied committed Artifact changed its content-addressed identity"
            )
        return committed

    def read(self, run_id: str, artifact_ref: str) -> Phase32ArtifactRecord:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(artifact_ref, label="artifact_ref")
        try:
            record = Phase32ArtifactRecord.model_validate(
                read_json(self.root / safe_run_id / f"{safe_ref}.json")
            )
            if record.run_id != safe_run_id or record.artifact_ref != safe_ref:
                raise ValueError("Artifact storage identity does not match its record")
            return record.validate_payload()
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ArtifactStoreError(
                f"Malformed Phase 32 Artifact: {safe_run_id}/{safe_ref}"
            ) from exc

    def list(
        self,
        run_id: str,
        *,
        stage_id: str | None = None,
        status: ArtifactRecordStatus | None = None,
    ) -> list[Phase32ArtifactRecord]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        records = [self.read(safe_run_id, path.stem) for path in directory.glob("*.json")]
        if stage_id:
            records = [record for record in records if record.stage_id == stage_id]
        if status:
            records = [record for record in records if record.status == status]
        return sorted(records, key=lambda record: (record.created_at, record.artifact_ref))

    def _write_immutable(self, record: Phase32ArtifactRecord) -> Phase32ArtifactRecord:
        path = self.root / record.run_id / f"{record.artifact_ref}.json"
        with self._lock:
            if path.exists():
                existing = self.read(record.run_id, record.artifact_ref)
                if existing.model_copy(update={"created_at": record.created_at}) != record:
                    raise Phase32ArtifactStoreError("Phase 32 Artifact records are immutable")
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record


def _validated_payload(
    route_id: CreationRouteId,
    stage_id: str,
    artifact: Phase32CoreArtifact,
) -> tuple[dict[str, Any], Any]:
    binding = phase32_artifact_binding(route_id, stage_id)
    if not isinstance(artifact, binding.model_type):
        raise Phase32ArtifactStoreError(
            f"Artifact type {type(artifact).__name__} does not match {route_id}/{stage_id}"
        )
    validated = bind_phase32_artifact(route_id, stage_id, artifact)
    return validated.model_dump(mode="json"), binding


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "ArtifactRecordStatus",
    "Phase32ArtifactRecord",
    "Phase32ArtifactStore",
    "Phase32ArtifactStoreError",
]
