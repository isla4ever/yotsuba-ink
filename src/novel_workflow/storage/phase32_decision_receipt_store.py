"""Idempotent decision receipts for the dormant Phase 32 execution path."""

from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.frozen_route_contract import canonical_digest


DecisionReceiptStatus = Literal["pending", "succeeded"]


class Phase32DecisionReceipt(BaseModel):
    """A durable receipt for one exact decision command."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    receipt_ref: str = Field(pattern=r"^p32-decision-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    operation_key: str = Field(min_length=1, max_length=500)
    decision_id: str = Field(min_length=1, max_length=240)
    request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    command: dict[str, Any]
    status: DecisionReceiptStatus
    result: dict[str, Any] | None = None
    created_at: str = Field(min_length=1, max_length=80)
    updated_at: str = Field(min_length=1, max_length=80)


class Phase32DecisionReceiptConflict(ValueError):
    code = "phase32_decision_receipt_conflict"


class Phase32DecisionReceiptStore:
    """Content-addressed command receipts isolated from legacy operations."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def begin(
        self,
        *,
        run_id: str,
        operation_key: str,
        decision_id: str,
        command: dict[str, Any],
    ) -> Phase32DecisionReceipt:
        safe_run_id = require_safe_id(run_id, label="run_id")
        signature = canonical_digest(command)
        receipt = Phase32DecisionReceipt(
            receipt_ref=f"p32-decision-{hashlib.sha256(operation_key.encode('utf-8')).hexdigest()}",
            run_id=safe_run_id,
            operation_key=operation_key,
            decision_id=decision_id,
            request_signature=signature,
            command=dict(command),
            status="pending",
            created_at=_now(),
            updated_at=_now(),
        )
        path = self._path(safe_run_id, operation_key)
        with self._lock:
            if path.exists():
                existing = self._read_path(path)
                if (
                    existing.run_id != safe_run_id
                    or existing.operation_key != operation_key
                    or existing.decision_id != decision_id
                    or existing.request_signature != signature
                    or existing.command != command
                ):
                    raise Phase32DecisionReceiptConflict(
                        "Decision operation key was reused with different command data"
                    )
                return existing
            atomic_write_json(path, receipt.model_dump(mode="json"))
        return receipt

    def succeed(
        self,
        *,
        run_id: str,
        operation_key: str,
        result: dict[str, Any],
    ) -> Phase32DecisionReceipt:
        safe_run_id = require_safe_id(run_id, label="run_id")
        path = self._path(safe_run_id, operation_key)
        with self._lock:
            current = self._read_path(path)
            if current.status == "succeeded":
                if current.result != result:
                    raise Phase32DecisionReceiptConflict(
                        "Succeeded decision receipt is immutable"
                    )
                return current
            next_receipt = current.model_copy(
                update={"status": "succeeded", "result": dict(result), "updated_at": _now()}
            )
            atomic_write_json(path, next_receipt.model_dump(mode="json"))
            return next_receipt

    def read(self, run_id: str, operation_key: str) -> Phase32DecisionReceipt:
        return self._read_path(self._path(require_safe_id(run_id, label="run_id"), operation_key))

    def find(self, run_id: str, operation_key: str) -> Phase32DecisionReceipt | None:
        try:
            return self.read(run_id, operation_key)
        except FileNotFoundError:
            return None

    def list(self, run_id: str) -> list[Phase32DecisionReceipt]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        return [self._read_path(path) for path in sorted(directory.glob("*.json"))]

    def _path(self, run_id: str, operation_key: str) -> Path:
        if not operation_key.strip():
            raise ValueError("Decision operation key is required")
        digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()
        return self.root / run_id / f"p32-decision-{digest}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32DecisionReceipt:
        return Phase32DecisionReceipt.model_validate(read_json(path))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "DecisionReceiptStatus",
    "Phase32DecisionReceipt",
    "Phase32DecisionReceiptConflict",
    "Phase32DecisionReceiptStore",
]
