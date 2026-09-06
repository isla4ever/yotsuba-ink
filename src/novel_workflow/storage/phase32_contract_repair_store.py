"""Durable provenance receipts for zero-Provider contract repairs."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


ContractRepairStatus = Literal["pending", "succeeded"]


class Phase32ContractRepairRecord(BaseModel):
    """Immutable source/candidate binding plus the graph-resume outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    repair_ref: str = Field(pattern=r"^p32-contract-repair-[a-f0-9]{64}$")
    repair_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    domain_revision: int = Field(ge=0)
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    provider_receipt_ref: str = Field(
        pattern=r"^p32-provider-operation-[a-f0-9]{64}$"
    )
    provider_request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    repaired_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_ref: str = Field(min_length=1, max_length=500)
    status: ContractRepairStatus
    decision_id: str = Field(default="", max_length=500)
    result: dict[str, Any] | None = None
    created_at: str = Field(min_length=1, max_length=80)
    updated_at: str = Field(min_length=1, max_length=80)


class Phase32ContractRepairStoreConflict(ValueError):
    code = "phase32_contract_repair_store_conflict"


class Phase32ContractRepairStore:
    """Persist one idempotent repair identity without altering Provider receipts."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def begin(
        self,
        *,
        repair_id: str,
        run_id: str,
        definition_digest: str,
        domain_revision: int,
        stage_id: str,
        provider_receipt_ref: str,
        provider_request_signature: str,
        source_payload_digest: str,
        repaired_payload_digest: str,
        candidate_ref: str,
    ) -> Phase32ContractRepairRecord:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_repair_id = require_safe_id(repair_id, label="repair_id")
        now = _now()
        record = Phase32ContractRepairRecord(
            repair_ref=_repair_ref(safe_run_id, safe_repair_id),
            repair_id=safe_repair_id,
            run_id=safe_run_id,
            definition_digest=definition_digest,
            domain_revision=domain_revision,
            stage_id=stage_id,
            provider_receipt_ref=provider_receipt_ref,
            provider_request_signature=provider_request_signature,
            source_payload_digest=source_payload_digest,
            repaired_payload_digest=repaired_payload_digest,
            candidate_ref=candidate_ref,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        path = self._path(safe_run_id, safe_repair_id)
        with self._lock:
            if path.exists():
                existing = self._read_path(path)
                expected = record.model_copy(
                    update={
                        "created_at": existing.created_at,
                        "updated_at": existing.updated_at,
                        "status": existing.status,
                        "decision_id": existing.decision_id,
                        "result": existing.result,
                    }
                )
                if existing != expected:
                    raise Phase32ContractRepairStoreConflict(
                        "Contract repair id cannot be reused with different source or payload data"
                    )
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def succeed(
        self,
        *,
        run_id: str,
        repair_id: str,
        decision_id: str,
        result: dict[str, Any],
    ) -> Phase32ContractRepairRecord:
        with self._lock:
            current = self.read(run_id, repair_id)
            if current.status == "succeeded":
                if current.decision_id != decision_id or current.result != result:
                    raise Phase32ContractRepairStoreConflict(
                        "Succeeded contract repair receipts are immutable"
                    )
                return current
            updated = current.model_copy(
                update={
                    "status": "succeeded",
                    "decision_id": decision_id,
                    "result": dict(result),
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(current.run_id, current.repair_id),
                updated.model_dump(mode="json"),
            )
        return updated

    def read(self, run_id: str, repair_id: str) -> Phase32ContractRepairRecord:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_repair_id = require_safe_id(repair_id, label="repair_id")
        record = self._read_path(
            self._path(safe_run_id, safe_repair_id)
        )
        if (
            record.run_id != safe_run_id
            or record.repair_id != safe_repair_id
            or record.repair_ref != _repair_ref(safe_run_id, safe_repair_id)
        ):
            raise Phase32ContractRepairStoreConflict(
                "Contract repair storage identity is invalid"
            )
        return record

    def find(self, run_id: str, repair_id: str) -> Phase32ContractRepairRecord | None:
        try:
            return self.read(run_id, repair_id)
        except FileNotFoundError:
            return None

    def list(self, run_id: str) -> list[Phase32ContractRepairRecord]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        return sorted(
            (self._read_path(path) for path in directory.glob("*.json")),
            key=lambda item: (item.created_at, item.repair_ref),
        )

    def _path(self, run_id: str, repair_id: str) -> Path:
        return self.root / run_id / f"{_repair_ref(run_id, repair_id)}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32ContractRepairRecord:
        try:
            record = Phase32ContractRepairRecord.model_validate(read_json(path))
            if (
                path.stem != record.repair_ref
                or path.parent.name != record.run_id
                or record.repair_ref != _repair_ref(record.run_id, record.repair_id)
            ):
                raise ValueError("Contract repair path identity does not match its record")
            return record
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ContractRepairStoreConflict(
                f"Malformed Phase 32 contract repair receipt: {path.name}"
            ) from exc


def _repair_ref(run_id: str, repair_id: str) -> str:
    digest = hashlib.sha256(f"{run_id}\0{repair_id}".encode("utf-8")).hexdigest()
    return f"p32-contract-repair-{digest}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "ContractRepairStatus",
    "Phase32ContractRepairRecord",
    "Phase32ContractRepairStore",
    "Phase32ContractRepairStoreConflict",
]
