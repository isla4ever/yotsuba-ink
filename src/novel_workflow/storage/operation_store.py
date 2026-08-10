from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class OperationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    kind: str
    status: Literal["pending", "succeeded", "failed"]
    provider_profile_id: str = ""
    model: str = ""
    request_signature: str = Field(min_length=64, max_length=64)
    result: Any = None
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class OperationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def begin(
        self,
        *,
        run_id: str,
        operation_key: str,
        kind: str,
        request_signature: str,
        provider_profile_id: str = "",
        model: str = "",
    ) -> OperationReceipt:
        require_safe_id(run_id, label="run_id")
        path = self._path(run_id, operation_key)
        with self._lock:
            if path.exists():
                existing = OperationReceipt.model_validate(read_json(path))
                if existing.request_signature != request_signature:
                    raise ValueError("Operation key was reused with a different request")
                return existing
            now = _now()
            receipt = OperationReceipt(
                operation_key=operation_key,
                run_id=run_id,
                kind=kind,
                status="pending",
                provider_profile_id=provider_profile_id,
                model=model,
                request_signature=request_signature,
                created_at=now,
                updated_at=now,
            )
            atomic_write_json(path, receipt.model_dump(mode="json"))
            return receipt

    def succeed(self, run_id: str, operation_key: str, result: Any) -> OperationReceipt:
        return self._finish(run_id, operation_key, status="succeeded", result=result)

    def fail(self, run_id: str, operation_key: str, error: dict[str, Any]) -> OperationReceipt:
        return self._finish(run_id, operation_key, status="failed", error=error)

    def read(self, run_id: str, operation_key: str) -> OperationReceipt:
        return OperationReceipt.model_validate(read_json(self._path(run_id, operation_key)))

    def find(self, run_id: str, operation_key: str) -> OperationReceipt | None:
        try:
            return self.read(run_id, operation_key)
        except FileNotFoundError:
            return None

    def copy_receipt(
        self,
        *,
        source_run_id: str,
        source_operation_key: str,
        target_run_id: str,
        target_operation_key: str,
    ) -> OperationReceipt:
        source = self.read(source_run_id, source_operation_key)
        target = source.model_copy(
            update={"run_id": target_run_id, "operation_key": target_operation_key}
        )
        path = self._path(target_run_id, target_operation_key)
        with self._lock:
            if path.exists():
                existing = OperationReceipt.model_validate(read_json(path))
                if existing != target:
                    raise ValueError("Branch operation receipt is immutable")
                return existing
            atomic_write_json(path, target.model_dump(mode="json"))
        return target

    def _finish(
        self,
        run_id: str,
        operation_key: str,
        *,
        status: Literal["succeeded", "failed"],
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        with self._lock:
            current = self.read(run_id, operation_key)
            if current.status == status:
                return current
            if current.status != "pending":
                raise ValueError("Completed operations are immutable")
            next_receipt = current.model_copy(update={"status": status, "result": result, "error": error, "updated_at": _now()})
            atomic_write_json(self._path(run_id, operation_key), next_receipt.model_dump(mode="json"))
            return next_receipt

    def _path(self, run_id: str, operation_key: str) -> Path:
        require_safe_id(run_id, label="run_id")
        digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()
        return self.root / run_id / f"{digest}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
