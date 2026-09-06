"""Immutable, secret-free Provider input snapshots for the Phase 32 runtime.

The input snapshot is the durable identity of the request sent to a Provider.
It is intentionally separate from LangGraph state and from the legacy
``ProviderInputStore``: a restarted graph must be able to prove that a receipt
belongs to the exact frozen request without persisting credentials or headers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32ProviderInputRecord(BaseModel):
    """Content-addressed, secret-free snapshot of one frozen Provider request."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    provider_input_ref: str = Field(pattern=r"^p32-provider-input-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    operation_key: str = Field(min_length=1, max_length=500)
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    request: dict[str, Any]
    created_at: str = Field(min_length=1, max_length=80)

    @property
    def snapshot_ref(self) -> str:
        """Compatibility-friendly name for callers that use snapshot terminology."""

        return self.provider_input_ref

    @property
    def input_snapshot_ref(self) -> str:
        """Alias matching the receipt architecture terminology."""

        return self.provider_input_ref

    @property
    def input(self) -> dict[str, Any]:
        """Compatibility-friendly accessor for generic input snapshot readers."""

        return self.request


class Phase32ProviderInputSnapshotConflict(ValueError):
    code = "phase32_provider_input_snapshot_conflict"


class Phase32ProviderInputStore:
    """Persist one immutable Phase 32 request snapshot per run."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def signature(self, request: dict[str, Any]) -> str:
        """Return the canonical signature of a frozen request payload."""

        _validate_request_shape(request)
        _assert_secret_free(request)
        return canonical_digest(request)

    def write(
        self,
        *,
        run_id: str,
        operation_key: str,
        stage_id: str,
        request: dict[str, Any],
    ) -> Phase32ProviderInputRecord:
        """Write or recover a content-addressed request snapshot."""

        safe_run_id = require_safe_id(run_id, label="run_id")
        if not operation_key.strip():
            raise ValueError("Provider operation key is required")
        if not stage_id.strip():
            raise ValueError("Provider stage id is required")
        frozen_request = _freeze_json(request)
        request_signature = self.signature(frozen_request)
        _validate_request_identity(
            frozen_request,
            run_id=safe_run_id,
            operation_key=operation_key,
            stage_id=stage_id,
        )
        record = Phase32ProviderInputRecord(
            provider_input_ref=f"p32-provider-input-{request_signature}",
            run_id=safe_run_id,
            operation_key=operation_key,
            stage_id=stage_id,
            request_signature=request_signature,
            request=frozen_request,
            created_at=_now(),
        )
        path = self._path(safe_run_id, record.provider_input_ref)
        with self._lock:
            if path.exists():
                existing = self._read_path(path)
                if existing != record.model_copy(update={"created_at": existing.created_at}):
                    raise Phase32ProviderInputSnapshotConflict(
                        "Provider input snapshot is immutable"
                    )
                return existing
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, provider_input_ref: str) -> Phase32ProviderInputRecord:
        safe_run_id = require_safe_id(run_id, label="run_id")
        record = self._read_path(self._path(safe_run_id, provider_input_ref))
        if record.run_id != safe_run_id or record.provider_input_ref != provider_input_ref:
            raise Phase32ProviderInputSnapshotConflict(
                "Provider input snapshot identity does not match its path"
            )
        return record

    def require_matches(
        self,
        *,
        run_id: str,
        operation_key: str,
        stage_id: str,
        request_signature: str,
        provider_input_ref: str,
    ) -> Phase32ProviderInputRecord:
        """Read a receipt-bound snapshot and prove all identity fields agree."""

        record = self.read(run_id, provider_input_ref)
        if (
            record.operation_key != operation_key
            or record.stage_id != stage_id
            or record.request_signature != request_signature
        ):
            raise Phase32ProviderInputSnapshotConflict(
                "Provider input snapshot does not match the Provider operation"
            )
        return record

    def list(self, run_id: str) -> list[Phase32ProviderInputRecord]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        return sorted(
            (self._read_path(path) for path in directory.glob("*.json")),
            key=lambda item: (item.created_at, item.provider_input_ref),
        )

    def _path(self, run_id: str, provider_input_ref: str) -> Path:
        require_safe_id(run_id, label="run_id")
        if not provider_input_ref.startswith("p32-provider-input-"):
            raise ValueError("Invalid provider_input_ref")
        require_safe_id(provider_input_ref, label="provider_input_ref")
        return self.root / run_id / f"{provider_input_ref}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32ProviderInputRecord:
        try:
            record = Phase32ProviderInputRecord.model_validate(read_json(path))
            _validate_record(record)
            return record
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ProviderInputSnapshotConflict(
                f"Malformed Phase 32 Provider input snapshot: {path.name}"
            ) from exc


def _validate_record(record: Phase32ProviderInputRecord) -> None:
    expected_signature = canonical_digest(record.request)
    if record.request_signature != expected_signature:
        raise ValueError("Provider input snapshot signature does not match its request")
    if record.provider_input_ref != f"p32-provider-input-{expected_signature}":
        raise ValueError("Provider input reference does not match its request")
    _assert_secret_free(record.request)
    _validate_request_identity(
        record.request,
        run_id=record.run_id,
        operation_key=record.operation_key,
        stage_id=record.stage_id,
    )


def _validate_request_shape(request: Any) -> None:
    if not isinstance(request, dict) or not request:
        raise ValueError("Provider input request must be a non-empty JSON object")


def _validate_request_identity(
    request: dict[str, Any],
    *,
    run_id: str,
    operation_key: str,
    stage_id: str,
) -> None:
    if request.get("run_id") != run_id:
        raise ValueError("Provider input request run_id does not match its snapshot")
    if request.get("operation_key") != operation_key:
        raise ValueError("Provider input request operation_key does not match its snapshot")
    if request.get("stage_id") != stage_id:
        raise ValueError("Provider input request stage_id does not match its snapshot")


def _freeze_json(value: Any) -> Any:
    """Copy nested JSON values so callers cannot mutate the written input."""

    if isinstance(value, dict):
        return {str(key): _freeze_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_freeze_json(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError("Provider input snapshot must contain canonical JSON values")


def _assert_secret_free(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if (
                normalized
                in {
                    "api_key",
                    "authorization",
                    "header",
                    "headers",
                    "secret",
                    "secret_ref",
                    "password",
                    "token",
                    "token_ref",
                    "access_token",
                    "refresh_token",
                    "credential",
                    "credentials",
                }
                or normalized.endswith("_header")
                or normalized.endswith("_headers")
            ):
                raise ValueError(
                    "Provider input snapshot contains forbidden secret or header field: "
                    f"{'.'.join((*path, str(key)))}"
                )
            _assert_secret_free(item, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_secret_free(item, (*path, str(index)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


Phase32ProviderInputSnapshot = Phase32ProviderInputRecord


__all__ = [
    "Phase32ProviderInputRecord",
    "Phase32ProviderInputSnapshot",
    "Phase32ProviderInputSnapshotConflict",
    "Phase32ProviderInputStore",
]
