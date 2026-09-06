"""Durable idempotency records for Phase 32 Run preparation.

The preparation record is a sidecar to the immutable GraphRunDefinition.  It
allows a request that was interrupted between reservation and Run persistence
to resume without inventing a second Run, while keeping the Run repository as
the sole authority for executable state.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from threading import RLock, local
from typing import Any, Iterator, Literal

try:  # pragma: no cover - exercised by the POSIX multiprocessing tests
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.frozen_route_contract import canonical_digest


PreparationStatus = Literal["reserved", "prepared"]
PreparationProfileKind = Literal[
    "production",
    "release_smoke",
    "continuity_acceptance",
]


def derive_phase32_creation_identifiers(
    idempotency_key: str,
    profile_kind: PreparationProfileKind,
) -> tuple[str, str]:
    """Derive the stable Project and Run ids for one preparation scope."""

    id_prefix = {
        "production": "p32",
        "release_smoke": "release-smoke",
        "continuity_acceptance": "continuity-acceptance",
    }[profile_kind]
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return (
        f"{id_prefix}-proj-{digest[:20]}",
        f"{id_prefix}-run-{digest[20:40]}",
    )


class Phase32CreationPreparation(BaseModel):
    """A replayable reservation for one creation request."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_payload: dict[str, Any]
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    created_at: str = Field(min_length=1, max_length=80)
    status: PreparationStatus
    profile_kind: PreparationProfileKind = "production"
    definition_digest: str = Field(default="", pattern=r"^$|^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_preparation_binding(self) -> "Phase32CreationPreparation":
        request_payload = dict(self.request_payload)
        if request_payload.get("idempotency_key") != self.idempotency_key:
            raise ValueError(
                "Creation preparation request idempotency key differs from its envelope"
            )

        digest_request = dict(request_payload)
        digest_request.pop("idempotency_key")
        expected_request_digest = canonical_digest(
            {"profile_kind": self.profile_kind, "request": digest_request}
        )
        if self.request_digest != expected_request_digest:
            raise ValueError(
                "Creation preparation request digest differs from its frozen payload"
            )

        derived_project_id, derived_run_id = derive_phase32_creation_identifiers(
            self.idempotency_key,
            self.profile_kind,
        )
        payload_project_id = request_payload.get("project_id")
        expected_project_id = (
            derived_project_id if payload_project_id is None else payload_project_id
        )
        if self.project_id != expected_project_id:
            raise ValueError(
                "Creation preparation project id differs from its frozen request"
            )
        payload_run_id = request_payload.get("run_id")
        expected_run_id = derived_run_id if payload_run_id is None else payload_run_id
        if self.run_id != expected_run_id:
            raise ValueError("Creation preparation Run id differs from its frozen request")

        if self.status == "reserved" and self.definition_digest:
            raise ValueError(
                "Reserved creation preparation cannot carry a definition digest"
            )
        if self.status == "prepared" and not self.definition_digest:
            raise ValueError(
                "Prepared creation preparation requires a definition digest"
            )
        return self


class Phase32PreparationConflict(ValueError):
    code = "phase32_creation_conflict"


class Phase32CreationPreparationStore:
    """Atomic JSON store keyed by the caller's idempotency key."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock_root = self.root / ".locks"
        self._lock_root.mkdir(parents=True, exist_ok=True)
        self._locks_guard = RLock()
        self._key_locks: dict[str, RLock] = {}
        self._thread_state = local()

    @contextmanager
    def transaction(self, idempotency_key: str) -> Iterator[None]:
        """Serialize a preparation transaction for one idempotency key.

        POSIX callers share a filesystem lock, so the reservation and its Run
        definition can be recovered or committed as one logical operation
        across processes.  Re-entrant store calls reuse the outer lock.
        """

        safe_key = require_safe_id(idempotency_key, label="idempotency_key")
        with self._key_guard(safe_key):
            yield

    def read(self, idempotency_key: str) -> Phase32CreationPreparation:
        safe_key = require_safe_id(idempotency_key, label="idempotency_key")
        with self._key_guard(safe_key):
            return self._read_locked(safe_key)

    def _read_locked(self, safe_key: str) -> Phase32CreationPreparation:
        try:
            payload = read_json(self._path(safe_key))
            record = Phase32CreationPreparation.model_validate(payload)
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32PreparationConflict(
                f"Malformed Phase 32 creation preparation: {safe_key}"
            ) from exc
        if record.idempotency_key != safe_key:
            raise Phase32PreparationConflict(
                "Creation preparation identity does not match its storage key"
            )
        return record

    def reserve(self, record: Phase32CreationPreparation) -> Phase32CreationPreparation:
        reserved, _ = self.reserve_or_read(record)
        return reserved

    def reserve_or_read(
        self,
        record: Phase32CreationPreparation,
    ) -> tuple[Phase32CreationPreparation, bool]:
        """Atomically persist a reservation or return its logical winner.

        ``created_at`` is deliberately not part of reservation identity. Two
        identical callers may observe different clocks, but only the timestamp
        already persisted by the winner can be used to freeze the definition.
        The boolean is true when a reservation already existed.
        """

        record = Phase32CreationPreparation.model_validate(
            record.model_dump(mode="json")
        )
        safe_key = require_safe_id(record.idempotency_key, label="idempotency_key")
        if safe_key != record.idempotency_key:
            raise ValueError("Invalid idempotency key")
        if record.status != "reserved" or record.definition_digest:
            raise ValueError("A new creation reservation must be unprepared")
        with self._key_guard(safe_key):
            path = self._path(safe_key)
            if path.exists():
                existing = self._read_locked(safe_key)
                if self._reservation_identity(existing) != self._reservation_identity(record):
                    raise Phase32PreparationConflict(
                        f"Idempotency key is already reserved with different input: {safe_key}"
                    )
                return existing, True
            atomic_write_json(path, record.model_dump(mode="json"))
        return record, False

    def mark_prepared(
        self,
        idempotency_key: str,
        *,
        definition_digest: str,
    ) -> Phase32CreationPreparation:
        safe_key = require_safe_id(idempotency_key, label="idempotency_key")
        with self._key_guard(safe_key):
            record = self._read_locked(safe_key)
            if record.status == "prepared":
                if record.definition_digest != definition_digest:
                    raise Phase32PreparationConflict(
                        "Prepared definition digest conflicts with the existing preparation"
                    )
                return record
            updated = Phase32CreationPreparation.model_validate(
                {
                    **record.model_dump(mode="json"),
                    "status": "prepared",
                    "definition_digest": definition_digest,
                }
            )
            atomic_write_json(self._path(record.idempotency_key), updated.model_dump(mode="json"))
            return updated

    def list(self) -> list[Phase32CreationPreparation]:
        records: list[Phase32CreationPreparation] = []
        for path in sorted(self.root.glob("*.json")):
            records.append(self.read(path.stem))
        return records

    def _path(self, idempotency_key: str) -> Path:
        return self.root / f"{require_safe_id(idempotency_key, label='idempotency_key')}.json"

    def _thread_lock_for(self, safe_key: str) -> RLock:
        with self._locks_guard:
            return self._key_locks.setdefault(safe_key, RLock())

    @contextmanager
    def _key_guard(self, safe_key: str) -> Iterator[None]:
        thread_lock = self._thread_lock_for(safe_key)
        with thread_lock:
            held_keys = getattr(self._thread_state, "held_keys", None)
            if held_keys is None:
                held_keys = set()
                self._thread_state.held_keys = held_keys
            if safe_key in held_keys:
                yield
                return

            handle = None
            held_keys.add(safe_key)
            try:
                if fcntl is not None:
                    lock_name = hashlib.sha256(safe_key.encode("utf-8")).hexdigest()
                    handle = (self._lock_root / f"{lock_name}.lock").open("a+b")
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                if handle is not None:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    finally:
                        handle.close()
                held_keys.remove(safe_key)

    @staticmethod
    def _reservation_identity(record: Phase32CreationPreparation) -> dict[str, Any]:
        return record.model_dump(
            mode="json",
            exclude={"created_at", "status", "definition_digest"},
        )


__all__ = [
    "derive_phase32_creation_identifiers",
    "Phase32CreationPreparation",
    "Phase32CreationPreparationStore",
    "PreparationProfileKind",
    "Phase32PreparationConflict",
    "PreparationStatus",
]
