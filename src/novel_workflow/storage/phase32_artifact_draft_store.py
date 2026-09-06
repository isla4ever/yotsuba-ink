"""Source-bound draft sidecar for Phase 32 core Artifact editing."""

from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import CreationRouteId


class Phase32ArtifactDraft(BaseModel):
    """One immutable author draft bound to one exact decision frontier."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    draft_ref: str = Field(pattern=r"^p32-draft-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    decision_id: str = Field(min_length=1, max_length=240)
    domain_revision: int = Field(ge=0)
    creation_route_id: CreationRouteId
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any]
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: str = Field(min_length=1, max_length=80)

    def validate_payload_digest(self) -> "Phase32ArtifactDraft":
        if self.payload_digest != canonical_digest(self.payload):
            raise ValueError("Phase 32 draft payload digest does not match its payload")
        return self


class Phase32ArtifactDraftStoreError(ValueError):
    code = "phase32_artifact_draft_invalid"


class Phase32ArtifactDraftStore:
    """Immutable draft history with one replaceable latest pointer per decision."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save(
        self,
        *,
        run_id: str,
        decision_id: str,
        domain_revision: int,
        creation_route_id: CreationRouteId,
        stage_id: str,
        source_artifact_ref: str,
        payload: dict[str, Any],
    ) -> Phase32ArtifactDraft:
        safe_run_id = require_safe_id(run_id, label="run_id")
        require_safe_id(source_artifact_ref, label="source_artifact_ref")
        identity = {
            "run_id": safe_run_id,
            "decision_id": decision_id,
            "domain_revision": domain_revision,
            "creation_route_id": creation_route_id,
            "stage_id": stage_id,
            "source_artifact_ref": source_artifact_ref,
            "payload": payload,
        }
        draft = Phase32ArtifactDraft(
            draft_ref=f"p32-draft-{canonical_digest(identity)}",
            run_id=safe_run_id,
            decision_id=decision_id,
            domain_revision=domain_revision,
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            source_artifact_ref=source_artifact_ref,
            payload=dict(payload),
            payload_digest=canonical_digest(payload),
            created_at=_now(),
        ).validate_payload_digest()
        directory = self._decision_directory(safe_run_id, decision_id)
        record_path = directory / "records" / f"{draft.draft_ref}.json"
        pointer_path = directory / "latest.json"
        with self._lock:
            if record_path.exists():
                existing = self._read_path(record_path)
                if existing.model_copy(update={"created_at": draft.created_at}) != draft:
                    raise Phase32ArtifactDraftStoreError("Phase 32 draft records are immutable")
                draft = existing
            else:
                atomic_write_json(record_path, draft.model_dump(mode="json"))
            atomic_write_json(
                pointer_path,
                {
                    "architecture_version": "phase32-routes-v1",
                    "run_id": safe_run_id,
                    "decision_id": decision_id,
                    "draft_ref": draft.draft_ref,
                },
            )
        return draft

    def latest(self, run_id: str, decision_id: str) -> Phase32ArtifactDraft | None:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self._decision_directory(safe_run_id, decision_id)
        try:
            pointer = read_json(directory / "latest.json")
        except FileNotFoundError:
            return None
        if pointer.get("run_id") != safe_run_id or pointer.get("decision_id") != decision_id:
            raise Phase32ArtifactDraftStoreError("Phase 32 latest draft pointer is malformed")
        return self.read(safe_run_id, decision_id, str(pointer.get("draft_ref") or ""))

    def read(
        self,
        run_id: str,
        decision_id: str,
        draft_ref: str,
    ) -> Phase32ArtifactDraft:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(draft_ref, label="draft_ref")
        draft = self._read_path(
            self._decision_directory(safe_run_id, decision_id)
            / "records"
            / f"{safe_ref}.json"
        )
        if (
            draft.run_id != safe_run_id
            or draft.decision_id != decision_id
            or draft.draft_ref != safe_ref
        ):
            raise Phase32ArtifactDraftStoreError("Phase 32 draft storage identity is malformed")
        return draft

    def list(self, run_id: str, decision_id: str) -> list[Phase32ArtifactDraft]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        records = self._decision_directory(safe_run_id, decision_id) / "records"
        if not records.exists():
            return []
        return sorted(
            (self._read_path(path) for path in records.glob("*.json")),
            key=lambda item: (item.created_at, item.draft_ref),
        )

    def _decision_directory(self, run_id: str, decision_id: str) -> Path:
        if not decision_id.strip() or len(decision_id) > 240:
            raise ValueError("Invalid decision_id")
        digest = hashlib.sha256(decision_id.encode("utf-8")).hexdigest()
        return self.root / run_id / digest

    @staticmethod
    def _read_path(path: Path) -> Phase32ArtifactDraft:
        try:
            return Phase32ArtifactDraft.model_validate(read_json(path)).validate_payload_digest()
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ArtifactDraftStoreError("Malformed Phase 32 Artifact draft") from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32ArtifactDraft",
    "Phase32ArtifactDraftStore",
    "Phase32ArtifactDraftStoreError",
]
