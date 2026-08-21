from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.providers.usage import ProviderUsageSummary, normalize_provider_usage
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.provider_input_store import (
    ProviderInputPayload,
    ProviderInputStore,
)


class OperationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_key: str
    run_id: str
    kind: str
    status: Literal[
        "pending",
        "provider_returned",
        "succeeded",
        "contract_rejected",
        "failed",
        "cancelled",
    ]
    provider_profile_id: str = ""
    model: str = ""
    request_signature: str = Field(min_length=64, max_length=64)
    provider_input_ref: str = ""
    provider_result: Any = None
    result: Any = None
    error: dict[str, Any] | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    diagnostic: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def require_provider_input_reference(self) -> "OperationReceipt":
        if bool(self.provider_profile_id) != bool(self.provider_input_ref):
            raise ValueError(
                "Provider receipts require an input reference; non-Provider receipts cannot have one"
            )
        return self


class OperationStore:
    def __init__(
        self,
        root: Path,
        *,
        provider_inputs: ProviderInputStore | None = None,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.provider_inputs = provider_inputs or ProviderInputStore(
            root.parent / "provider_inputs"
        )
        self._lock = threading.RLock()

    def begin_provider(
        self,
        *,
        run_id: str,
        operation_key: str,
        kind: str,
        provider_profile_id: str,
        model: str,
        provider_input: ProviderInputPayload,
    ) -> OperationReceipt:
        request_signature = self.provider_inputs.signature(
            run_id=run_id,
            operation_key=operation_key,
            input=provider_input,
        )
        return self.begin(
            run_id=run_id,
            operation_key=operation_key,
            kind=kind,
            request_signature=request_signature,
            provider_profile_id=provider_profile_id,
            model=model,
            provider_input=provider_input,
        )

    def begin(
        self,
        *,
        run_id: str,
        operation_key: str,
        kind: str,
        request_signature: str,
        provider_profile_id: str = "",
        model: str = "",
        provider_input: ProviderInputPayload | None = None,
    ) -> OperationReceipt:
        require_safe_id(run_id, label="run_id")
        if provider_profile_id and provider_input is None:
            raise ValueError("Provider operations require an immutable input snapshot")
        if not provider_profile_id and provider_input is not None:
            raise ValueError("Non-Provider operations cannot attach a Provider input snapshot")
        if provider_input is not None:
            input_signature = self.provider_inputs.signature(
                run_id=run_id,
                operation_key=operation_key,
                input=provider_input,
            )
            if input_signature != request_signature:
                raise ValueError("Provider request signature does not match its input snapshot")
        path = self._path(run_id, operation_key)
        with self._lock:
            if path.exists():
                existing = OperationReceipt.model_validate(read_json(path))
                if existing.request_signature != request_signature:
                    raise ValueError("Operation key was reused with a different request")
                return existing
            snapshot = (
                self.provider_inputs.write(
                    run_id=run_id,
                    operation_key=operation_key,
                    input=provider_input,
                )
                if provider_input is not None
                else None
            )
            now = _now()
            receipt = OperationReceipt(
                operation_key=operation_key,
                run_id=run_id,
                kind=kind,
                status="pending",
                provider_profile_id=provider_profile_id,
                model=model,
                request_signature=request_signature,
                provider_input_ref=snapshot.snapshot_ref if snapshot else "",
                created_at=now,
                updated_at=now,
            )
            atomic_write_json(path, receipt.model_dump(mode="json"))
            return receipt

    def succeed(
        self,
        run_id: str,
        operation_key: str,
        result: Any,
        *,
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        return self._finish(
            run_id,
            operation_key,
            status="succeeded",
            result=result,
            usage=usage,
            diagnostic=diagnostic,
        )

    def record_provider_return(
        self,
        run_id: str,
        operation_key: str,
        provider_result: Any,
        *,
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        """Persist a parsed Provider response before domain validation."""

        with self._lock:
            current = self.read(run_id, operation_key)
            if current.status in {
                "provider_returned",
                "succeeded",
                "contract_rejected",
            }:
                if current.provider_result != provider_result:
                    raise ValueError("Provider return is immutable")
                return current
            if current.status != "pending" or not current.provider_profile_id:
                raise ValueError("Only pending Provider operations can record a return")
            next_receipt = current.model_copy(
                update={
                    "status": "provider_returned",
                    "provider_result": provider_result,
                    "usage": normalize_provider_usage(usage),
                    "diagnostic": dict(diagnostic or {}),
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(run_id, operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def accept_provider_result(
        self,
        run_id: str,
        operation_key: str,
        result: Any,
        *,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        """Mark a persisted Provider return as accepted by its domain contract."""

        return self._finish_provider_contract(
            run_id,
            operation_key,
            status="succeeded",
            result=result,
            diagnostic=diagnostic,
        )

    def reject_provider_contract(
        self,
        run_id: str,
        operation_key: str,
        error: dict[str, Any],
        *,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        """Persist a deterministic rejection without misreporting transport failure."""

        return self._finish_provider_contract(
            run_id,
            operation_key,
            status="contract_rejected",
            error=error,
            diagnostic=diagnostic,
        )

    def fail(
        self,
        run_id: str,
        operation_key: str,
        error: dict[str, Any],
        *,
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        return self._finish(
            run_id,
            operation_key,
            status="failed",
            error=error,
            usage=usage,
            diagnostic=diagnostic,
        )

    def cancel(
        self,
        run_id: str,
        operation_key: str,
        error: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        return self._finish(
            run_id,
            operation_key,
            status="cancelled",
            error=error or {"code": "cancelled", "message": "Cancelled by the author"},
        )

    def read(self, run_id: str, operation_key: str) -> OperationReceipt:
        return OperationReceipt.model_validate(read_json(self._path(run_id, operation_key)))

    def find(self, run_id: str, operation_key: str) -> OperationReceipt | None:
        try:
            return self.read(run_id, operation_key)
        except FileNotFoundError:
            return None

    def list(self, run_id: str) -> list[OperationReceipt]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id
        if not directory.exists():
            return []
        return [
            OperationReceipt.model_validate(read_json(path))
            for path in sorted(directory.glob("*.json"))
        ]

    def usage_summary(self, run_id: str) -> ProviderUsageSummary:
        provider_receipts = [
            receipt for receipt in self.list(run_id) if receipt.provider_profile_id
        ]
        totals = {
            key: sum(receipt.usage.get(key, 0) for receipt in provider_receipts)
            for key in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "reasoning_tokens",
            )
        }
        return ProviderUsageSummary(
            provider_operations=len(provider_receipts),
            returned_operations=sum(
                receipt.status
                in {"provider_returned", "succeeded", "contract_rejected"}
                for receipt in provider_receipts
            ),
            succeeded_operations=sum(
                receipt.status == "succeeded" for receipt in provider_receipts
            ),
            contract_rejected_operations=sum(
                receipt.status == "contract_rejected"
                for receipt in provider_receipts
            ),
            failed_operations=sum(
                receipt.status == "failed" for receipt in provider_receipts
            ),
            pending_operations=sum(
                receipt.status == "pending" for receipt in provider_receipts
            ),
            **totals,
        )

    def copy_receipt(
        self,
        *,
        source_run_id: str,
        source_operation_key: str,
        target_run_id: str,
        target_operation_key: str,
    ) -> OperationReceipt:
        source = self.read(source_run_id, source_operation_key)
        snapshot = None
        if source.provider_input_ref:
            source_snapshot = self.provider_inputs.read(
                source_run_id,
                source.provider_input_ref,
            )
            snapshot = self.provider_inputs.write(
                run_id=target_run_id,
                operation_key=target_operation_key,
                input=source_snapshot.input,
            )
        target = source.model_copy(update={
            "run_id": target_run_id,
            "operation_key": target_operation_key,
            "request_signature": (
                snapshot.request_signature if snapshot else source.request_signature
            ),
            "provider_input_ref": snapshot.snapshot_ref if snapshot else "",
        })
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
        status: Literal["succeeded", "failed", "cancelled"],
        result: Any = None,
        error: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        with self._lock:
            current = self.read(run_id, operation_key)
            if current.status == status:
                return current
            if current.status != "pending":
                raise ValueError("Completed operations are immutable")
            next_receipt = current.model_copy(update={
                "status": status,
                "result": result,
                "error": error,
                "usage": normalize_provider_usage(usage),
                "diagnostic": dict(diagnostic or {}),
                "updated_at": _now(),
            })
            atomic_write_json(self._path(run_id, operation_key), next_receipt.model_dump(mode="json"))
            return next_receipt

    def _finish_provider_contract(
        self,
        run_id: str,
        operation_key: str,
        *,
        status: Literal["succeeded", "contract_rejected"],
        result: Any = None,
        error: dict[str, Any] | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> OperationReceipt:
        with self._lock:
            current = self.read(run_id, operation_key)
            if current.status == status:
                return current
            if current.status != "provider_returned":
                raise ValueError(
                    "Provider contract outcome requires a persisted Provider return"
                )
            next_receipt = current.model_copy(
                update={
                    "status": status,
                    "result": result,
                    "error": error,
                    "diagnostic": {
                        **current.diagnostic,
                        **dict(diagnostic or {}),
                    },
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(run_id, operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def _path(self, run_id: str, operation_key: str) -> Path:
        require_safe_id(run_id, label="run_id")
        digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()
        return self.root / run_id / f"{digest}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
