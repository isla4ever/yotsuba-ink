"""Durable Provider-operation receipts for the Phase 32 runtime.

The receipt is deliberately separate from the legacy ``OperationStore``.  It
is the recovery boundary for one frozen Provider request: a transport failure
leaves the operation pending, while a returned payload is persisted before any
Artifact parsing occurs.  This lets a restarted process finish parsing the
same response without making a second Provider call.
"""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

try:  # pragma: no cover - the production target is POSIX; tests still cover the fallback.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
)
from novel_workflow.providers.usage import (
    BalanceStatus,
    CostStatus,
    Phase32ProviderPricingSnapshot,
    Phase32ProviderUsageSummary,
    balance_status_from_diagnostic,
    estimate_phase32_cost,
    normalize_provider_usage,
    phase32_pricing_snapshot,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.phase32_provider_input_store import (
    Phase32ProviderInputStore,
    Phase32ProviderInputSnapshotConflict,
)
from novel_workflow.storage.phase32_provider_attempt_ledger import (
    Phase32ProviderTransportAttemptEvent,
    append_claimed_attempt_event,
    append_terminal_attempt_event,
    build_claimed_attempt_event,
    public_transport_error_code,
    validate_transport_attempt_events,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.usage import summarize_phase32_provider_receipts


ProviderOperationReceiptStatus = Literal[
    "pending",
    "returned",
    "succeeded",
    "contract_rejected",
]


class Phase32ProviderOperationReceipt(BaseModel):
    """Immutable identity plus the mutable lifecycle of one Provider call."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    receipt_ref: str = Field(pattern=r"^p32-provider-operation-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    operation_key: str = Field(min_length=1, max_length=500)
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    # Kept optional for low-level receipt inspection fixtures.  Production
    # Phase32RouteDriver instances always bind this to an input snapshot.
    provider_input_ref: str = Field(
        default="",
        pattern=r"^(?:p32-provider-input-[a-f0-9]{64})?$",
    )
    provider_profile_id: str = Field(default="", max_length=240)
    provider_template_id: str = Field(default="", max_length=240)
    model_id: str = Field(default="", max_length=240)
    pricing_snapshot_ref: str = Field(
        default="",
        pattern=r"^(?:p32-provider-pricing-[a-f0-9]{64})?$",
    )
    lease_owner: str = Field(default="", max_length=240)
    lease_expires_at: str = Field(default="", max_length=80)
    transport_attempts: int = Field(default=0, ge=0)
    transport_admission_refs: tuple[str, ...] = ()
    transport_attempt_events: tuple[Phase32ProviderTransportAttemptEvent, ...] = ()
    budget_definition_digest: str = Field(default="", pattern=r"^$|^[a-f0-9]{64}$")
    budget_authorization_ref: str = Field(
        default="",
        pattern=r"^$|^p32-run-budget-[a-f0-9]{64}$",
    )
    status: ProviderOperationReceiptStatus
    raw_provider_payload: dict[str, Any] | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    cost_status: CostStatus = "unknown"
    balance_status: BalanceStatus = "unknown"
    diagnostic: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    created_at: str = Field(min_length=1, max_length=80)
    updated_at: str = Field(min_length=1, max_length=80)

    @field_validator("usage")
    @classmethod
    def _validate_usage(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for key, amount in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Provider usage keys must be non-empty strings")
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise ValueError("Provider usage values must be non-negative integers")
            normalized[key] = amount
        return normalized

    @field_validator("transport_admission_refs")
    @classmethod
    def _validate_transport_admission_refs(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("Provider transport admission references must be unique")
        for admission_ref in value:
            if (
                len(admission_ref) != len("p32-budget-admission-") + 64
                or not admission_ref.startswith("p32-budget-admission-")
                or any(
                    character not in "0123456789abcdef"
                    for character in admission_ref.removeprefix(
                        "p32-budget-admission-"
                    )
                )
            ):
                raise ValueError(
                    "Provider transport admission reference must be content addressed"
                )
        return value

    @model_validator(mode="after")
    def validate_cost_projection(self) -> "Phase32ProviderOperationReceipt":
        if self.cost_status == "known" and self.estimated_cost_usd is None:
            raise ValueError("Known Provider cost requires an estimated cost value")
        if self.estimated_cost_usd is not None and self.cost_status != "known":
            raise ValueError("Estimated Provider cost must be marked known")
        if self.transport_admission_refs and (
            len(self.transport_admission_refs) != self.transport_attempts
        ):
            raise ValueError(
                "Provider transport admission history must cover every claimed attempt"
            )
        has_budget_identity = bool(
            self.budget_definition_digest or self.budget_authorization_ref
        )
        if has_budget_identity and not (
            self.budget_definition_digest and self.budget_authorization_ref
        ):
            raise ValueError("Provider receipt budget identity must be complete")
        if bool(self.transport_admission_refs) != has_budget_identity:
            raise ValueError(
                "Provider transport admissions and budget identity must be recorded together"
            )
        validate_transport_attempt_events(
            self.transport_attempt_events,
            run_id=self.run_id,
            operation_key=self.operation_key,
            request_signature=self.request_signature,
            transport_attempts=self.transport_attempts,
            admission_refs=self.transport_admission_refs,
        )
        return self

    @property
    def raw_payload(self) -> dict[str, Any] | None:
        """Compatibility-friendly name for callers inspecting the raw return."""

        return self.raw_provider_payload

    @property
    def input_snapshot_ref(self) -> str:
        """Alias used by the architecture notes for the same receipt field."""

        return self.provider_input_ref


class Phase32ProviderOperationReceiptConflict(ValueError):
    code = "phase32_provider_operation_receipt_conflict"


class Phase32ProviderOperationLeaseConflict(Phase32ProviderOperationReceiptConflict):
    code = "phase32_provider_operation_lease_conflict"


class Phase32ProviderOperationRetryExhausted(Phase32ProviderOperationReceiptConflict):
    code = "phase32_provider_operation_retry_exhausted"


class Phase32ProviderOperationAttemptFenceConflict(
    Phase32ProviderOperationReceiptConflict
):
    code = "phase32_provider_operation_attempt_fence_conflict"


class Phase32ProviderOperationStore:
    """Content-addressed receipts isolated from all legacy runtime stores."""

    def __init__(
        self,
        root: Path,
        *,
        provider_inputs: Phase32ProviderInputStore | None = None,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_root = root / ".locks"
        self.lock_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.provider_inputs = provider_inputs

    def attach_provider_inputs(self, provider_inputs: Phase32ProviderInputStore) -> None:
        """Attach the input store used to validate receipt-bound snapshots."""

        with self._lock:
            if self.provider_inputs is not None and self.provider_inputs.root != provider_inputs.root:
                raise ValueError("Phase 32 operation store is already bound to another input store")
            self.provider_inputs = provider_inputs

    def begin(
        self,
        *,
        run_id: str,
        operation_key: str,
        stage_id: str,
        request_signature: str,
        provider_input_ref: str = "",
        provider_profile_id: str = "",
        provider_template_id: str = "",
        model_id: str = "",
        pricing_snapshot_ref: str = "",
    ) -> Phase32ProviderOperationReceipt:
        """Create or recover a pending receipt for a frozen request."""

        safe_run_id = require_safe_id(run_id, label="run_id")
        _validate_signature(request_signature)
        if not operation_key.strip():
            raise ValueError("Provider operation key is required")
        _validate_pricing_ref(pricing_snapshot_ref)
        if provider_input_ref:
            _validate_input_ref(provider_input_ref)
            self._require_input_snapshot(
                run_id=safe_run_id,
                operation_key=operation_key,
                stage_id=stage_id,
                request_signature=request_signature,
                provider_input_ref=provider_input_ref,
            )
        receipt = Phase32ProviderOperationReceipt(
            receipt_ref=_receipt_ref(operation_key),
            run_id=safe_run_id,
            operation_key=operation_key,
            stage_id=stage_id,
            request_signature=request_signature,
            provider_input_ref=provider_input_ref,
            provider_profile_id=provider_profile_id,
            provider_template_id=provider_template_id,
            model_id=model_id,
            pricing_snapshot_ref=pricing_snapshot_ref,
            status="pending",
            created_at=_now(),
            updated_at=_now(),
        )
        path = self._path(safe_run_id, operation_key)
        with self._operation_guard(safe_run_id, operation_key):
            if path.exists():
                existing = self._read_path(path)
                if (
                    existing.run_id != safe_run_id
                    or existing.operation_key != operation_key
                    or existing.stage_id != stage_id
                    or existing.request_signature != request_signature
                    or existing.provider_input_ref != provider_input_ref
                    or existing.provider_profile_id != provider_profile_id
                    or existing.provider_template_id != provider_template_id
                    or existing.model_id != model_id
                    or existing.pricing_snapshot_ref != pricing_snapshot_ref
                ):
                    raise Phase32ProviderOperationReceiptConflict(
                        "Provider operation key was reused with a different frozen request"
                    )
                return existing
            atomic_write_json(path, receipt.model_dump(mode="json"))
        return receipt

    def claim_pending(
        self,
        *,
        run_id: str,
        operation_key: str,
        request_signature: str,
        lease_owner: str,
        admission_fence: Phase32ProviderOperationAdmissionFence | None = None,
        lease_seconds: int = 120,
        max_transport_attempts: int = 3,
        now: datetime | None = None,
    ) -> Phase32ProviderOperationReceipt:
        """Atomically claim a pending operation before calling the Provider.

        The lease survives a process crash.  A normal transport exception must
        call :meth:`release_pending`, while an abandoned lease becomes
        reclaimable after ``lease_seconds``.  The attempt limit prevents a
        permanently unreachable Provider from burning tokens indefinitely.
        """

        safe_run_id = require_safe_id(run_id, label="run_id")
        _validate_signature(request_signature)
        _validate_lease_owner(lease_owner)
        if not 1 <= lease_seconds <= 3_600:
            raise ValueError("Provider operation lease must be between 1 and 3600 seconds")
        if not 1 <= max_transport_attempts <= 20:
            raise ValueError("Provider transport attempts must be between 1 and 20")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)
        with self._operation_guard(safe_run_id, operation_key):
            current = self._read_for_request(run_id, operation_key, request_signature)
            if current.status != "pending":
                return current
            if current.lease_owner and _lease_is_active(current, current_time):
                if current.lease_owner == lease_owner:
                    _require_current_attempt_fence(current, admission_fence)
                    return current
                raise Phase32ProviderOperationLeaseConflict(
                    "Provider operation is leased by another process"
                )
            if current.transport_attempts >= max_transport_attempts:
                raise Phase32ProviderOperationRetryExhausted(
                    "Provider transport retry limit has been exhausted"
                )
            next_transport_attempt = current.transport_attempts + 1
            next_admission_refs = _next_transport_admission_refs(
                current,
                admission_fence,
                next_transport_attempt=next_transport_attempt,
            )
            attempt_events = current.transport_attempt_events
            if current.lease_owner:
                attempt_events = append_terminal_attempt_event(
                    attempt_events,
                    transport_attempt=current.transport_attempts,
                    event_kind="lease_expired",
                    lease_owner=current.lease_owner,
                    occurred_at=_iso(current_time.timestamp()),
                    error_code="provider_lease_expired",
                )
            attempt_events = append_claimed_attempt_event(
                attempt_events,
                build_claimed_attempt_event(
                    run_id=current.run_id,
                    operation_key=current.operation_key,
                    request_signature=current.request_signature,
                    transport_attempt=next_transport_attempt,
                    admission_ref=(
                        admission_fence.admission_ref
                        if admission_fence is not None
                        else ""
                    ),
                    lease_owner=lease_owner,
                    occurred_at=_iso(current_time.timestamp()),
                ),
            )
            next_receipt = current.model_copy(
                update={
                    "lease_owner": lease_owner,
                    "lease_expires_at": _iso(current_time.timestamp() + lease_seconds),
                    "transport_attempts": next_transport_attempt,
                    "transport_admission_refs": next_admission_refs,
                    "transport_attempt_events": attempt_events,
                    "budget_definition_digest": (
                        admission_fence.definition_digest
                        if admission_fence is not None
                        else current.budget_definition_digest
                    ),
                    "budget_authorization_ref": (
                        admission_fence.authorization_ref
                        if admission_fence is not None
                        else current.budget_authorization_ref
                    ),
                    "updated_at": _iso(current_time.timestamp()),
                }
            )
            atomic_write_json(
                self._path(current.run_id, current.operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def release_pending(
        self,
        *,
        run_id: str,
        operation_key: str,
        request_signature: str,
        lease_owner: str,
        claimed_transport_attempt: int | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> Phase32ProviderOperationReceipt:
        """Release a lease after a transport failure without changing status."""

        safe_run_id = require_safe_id(run_id, label="run_id")
        _validate_signature(request_signature)
        _validate_lease_owner(lease_owner)
        with self._operation_guard(safe_run_id, operation_key):
            current = self._read_for_request(run_id, operation_key, request_signature)
            if current.status != "pending":
                return current
            _require_lease_owner(
                current,
                lease_owner,
                claimed_transport_attempt=claimed_transport_attempt,
            )
            attempt = claimed_transport_attempt or current.transport_attempts
            next_attempt_events = append_terminal_attempt_event(
                current.transport_attempt_events,
                transport_attempt=attempt,
                event_kind="transport_failed",
                lease_owner=lease_owner,
                occurred_at=_now(),
                error_code=public_transport_error_code(
                    (diagnostic or {}).get("code")
                ),
            )
            next_receipt = current.model_copy(
                update={
                    "lease_owner": "",
                    "lease_expires_at": "",
                    "diagnostic": {**current.diagnostic, **dict(diagnostic or {})},
                    "balance_status": balance_status_from_diagnostic(diagnostic),
                    "transport_attempt_events": next_attempt_events,
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(current.run_id, current.operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def record_return(
        self,
        *,
        run_id: str,
        operation_key: str,
        request_signature: str,
        raw_provider_payload: dict[str, Any],
        usage: dict[str, int] | None = None,
        diagnostic: dict[str, Any] | None = None,
        pricing_snapshot: Phase32ProviderPricingSnapshot | dict[str, Any] | None = None,
        lease_owner: str = "",
        claimed_transport_attempt: int | None = None,
    ) -> Phase32ProviderOperationReceipt:
        """Persist a raw Provider return before parsing its Artifact contract."""

        payload = dict(raw_provider_payload)
        next_usage = normalize_provider_usage(usage)
        next_diagnostic = dict(diagnostic or {})
        pricing = phase32_pricing_snapshot(pricing_snapshot)
        estimated_cost = estimate_phase32_cost(next_usage, pricing)
        cost_status: CostStatus = "known" if estimated_cost is not None else "unknown"
        balance_status = balance_status_from_diagnostic(next_diagnostic)
        with self._operation_guard(run_id, operation_key):
            current = self._read_for_request(run_id, operation_key, request_signature)
            _require_frozen_pricing_snapshot(current, pricing)
            _require_lease_owner(
                current,
                lease_owner,
                claimed_transport_attempt=claimed_transport_attempt,
            )
            if current.status == "succeeded":
                return current
            if current.status == "contract_rejected":
                raise Phase32ProviderOperationReceiptConflict(
                    "A contract-rejected Provider operation is immutable"
                )
            if current.status == "returned":
                if (
                    current.raw_provider_payload != payload
                    or current.usage != next_usage
                    or current.estimated_cost_usd != estimated_cost
                    or current.cost_status != cost_status
                    or current.diagnostic != next_diagnostic
                ):
                    raise Phase32ProviderOperationReceiptConflict(
                        "Provider return for an operation key is immutable"
                    )
                return current
            attempt = claimed_transport_attempt or current.transport_attempts
            next_attempt_events = append_terminal_attempt_event(
                current.transport_attempt_events,
                transport_attempt=attempt,
                event_kind="provider_returned",
                lease_owner=lease_owner or current.lease_owner or "unclaimed",
                occurred_at=_now(),
            )
            next_receipt = current.model_copy(
                update={
                    "status": "returned",
                    "raw_provider_payload": payload,
                    "usage": next_usage,
                    "estimated_cost_usd": estimated_cost,
                    "cost_status": cost_status,
                    "balance_status": balance_status,
                    "diagnostic": next_diagnostic,
                    "transport_attempt_events": next_attempt_events,
                    "lease_owner": "",
                    "lease_expires_at": "",
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(current.run_id, current.operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def succeed(
        self,
        *,
        run_id: str,
        operation_key: str,
        request_signature: str,
        result: dict[str, Any],
        lease_owner: str = "",
    ) -> Phase32ProviderOperationReceipt:
        """Mark a returned payload as having produced a validated candidate."""

        with self._operation_guard(run_id, operation_key):
            current = self._read_for_request(run_id, operation_key, request_signature)
            _require_lease_owner(current, lease_owner)
            if current.status == "succeeded":
                if current.result != result:
                    raise Phase32ProviderOperationReceiptConflict(
                        "Succeeded Provider operation receipts are immutable"
                    )
                return current
            if current.status != "returned" or current.raw_provider_payload is None:
                raise Phase32ProviderOperationReceiptConflict(
                    "A Provider operation must persist its return before succeeding"
                )
            next_receipt = current.model_copy(
                update={
                    "status": "succeeded",
                    "result": dict(result),
                    "lease_owner": "",
                    "lease_expires_at": "",
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(current.run_id, current.operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def reject_contract(
        self,
        *,
        run_id: str,
        operation_key: str,
        request_signature: str,
        diagnostic: dict[str, Any],
        lease_owner: str = "",
    ) -> Phase32ProviderOperationReceipt:
        """Record deterministic contract rejection without making it a retry."""

        with self._operation_guard(run_id, operation_key):
            current = self._read_for_request(run_id, operation_key, request_signature)
            _require_lease_owner(current, lease_owner)
            if current.status == "contract_rejected":
                if current.diagnostic != diagnostic:
                    raise Phase32ProviderOperationReceiptConflict(
                        "Contract-rejected Provider operation receipts are immutable"
                    )
                return current
            if current.status != "returned" or current.raw_provider_payload is None:
                raise Phase32ProviderOperationReceiptConflict(
                    "A Provider operation must persist its return before contract rejection"
                )
            merged_diagnostic = {**current.diagnostic, **diagnostic}
            next_receipt = current.model_copy(
                update={
                    "status": "contract_rejected",
                    "diagnostic": merged_diagnostic,
                    "lease_owner": "",
                    "lease_expires_at": "",
                    "updated_at": _now(),
                }
            )
            atomic_write_json(
                self._path(current.run_id, current.operation_key),
                next_receipt.model_dump(mode="json"),
            )
            return next_receipt

    def read(self, run_id: str, operation_key: str) -> Phase32ProviderOperationReceipt:
        return self._read_path(
            self._path(require_safe_id(run_id, label="run_id"), operation_key)
        )

    def read_receipt_ref(
        self,
        run_id: str,
        receipt_ref: str,
    ) -> Phase32ProviderOperationReceipt:
        """Read an operation through its public content-addressed receipt identity."""

        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_receipt_ref = require_safe_id(receipt_ref, label="receipt_ref")
        if (
            len(safe_receipt_ref) != len("p32-provider-operation-") + 64
            or not safe_receipt_ref.startswith("p32-provider-operation-")
            or any(
                character not in "0123456789abcdef"
                for character in safe_receipt_ref.removeprefix(
                    "p32-provider-operation-"
                )
            )
        ):
            raise ValueError("Provider operation receipt ref must be content addressed")
        receipt = self._read_path(self.root / safe_run_id / f"{safe_receipt_ref}.json")
        if receipt.run_id != safe_run_id or receipt.receipt_ref != safe_receipt_ref:
            raise Phase32ProviderOperationReceiptConflict(
                "Provider operation receipt storage identity is invalid"
            )
        return receipt

    def find(self, run_id: str, operation_key: str) -> Phase32ProviderOperationReceipt | None:
        try:
            return self.read(run_id, operation_key)
        except FileNotFoundError:
            return None

    def list(self, run_id: str) -> list[Phase32ProviderOperationReceipt]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        return [self._read_path(path) for path in sorted(directory.glob("*.json"))]

    def usage_summary(self, run_id: str) -> Phase32ProviderUsageSummary:
        """Aggregate receipted usage for the Phase 32 Run read model."""

        return summarize_phase32_provider_receipts(self.list(run_id))

    def _read_for_request(
        self,
        run_id: str,
        operation_key: str,
        request_signature: str,
    ) -> Phase32ProviderOperationReceipt:
        receipt = self.read(run_id, operation_key)
        _validate_signature(request_signature)
        if receipt.request_signature != request_signature:
            raise Phase32ProviderOperationReceiptConflict(
                "Provider operation key was reused with a different frozen request"
            )
        return receipt

    def _path(self, run_id: str, operation_key: str) -> Path:
        if not operation_key.strip():
            raise ValueError("Provider operation key is required")
        return self.root / run_id / f"{_receipt_ref(operation_key)}.json"

    @contextmanager
    def _operation_guard(self, run_id: str, operation_key: str) -> Iterator[None]:
        """Serialize receipt transitions inside and across Python processes."""

        lock_path = self.lock_root / f"{hashlib.sha256(operation_key.encode('utf-8')).hexdigest()}.lock"
        with self._lock:
            with lock_path.open("a+", encoding="utf-8") as handle:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_path(self, path: Path) -> Phase32ProviderOperationReceipt:
        try:
            receipt = Phase32ProviderOperationReceipt.model_validate(read_json(path))
            if receipt.provider_input_ref:
                self._require_input_snapshot(
                    run_id=receipt.run_id,
                    operation_key=receipt.operation_key,
                    stage_id=receipt.stage_id,
                    request_signature=receipt.request_signature,
                    provider_input_ref=receipt.provider_input_ref,
                )
            return receipt
        except FileNotFoundError:
            raise
        except Phase32ProviderInputSnapshotConflict as exc:
            raise Phase32ProviderOperationReceiptConflict(
                "Provider operation receipt input snapshot is invalid"
            ) from exc
        except Phase32ProviderOperationReceiptConflict:
            raise
        except Exception as exc:
            raise Phase32ProviderOperationReceiptConflict(
                f"Malformed Phase 32 Provider operation receipt: {path.name}"
            ) from exc

    def _require_input_snapshot(
        self,
        *,
        run_id: str,
        operation_key: str,
        stage_id: str,
        request_signature: str,
        provider_input_ref: str,
    ) -> None:
        if self.provider_inputs is None:
            # A low-level store can be used without an attached input store by
            # tests and archive tooling; the production driver attaches one.
            return
        try:
            self.provider_inputs.require_matches(
                run_id=run_id,
                operation_key=operation_key,
                stage_id=stage_id,
                request_signature=request_signature,
                provider_input_ref=provider_input_ref,
            )
        except FileNotFoundError as exc:
            raise Phase32ProviderOperationReceiptConflict(
                "Provider operation receipt input snapshot is missing"
            ) from exc


def provider_request_signature(request: dict[str, Any]) -> str:
    """Return the deterministic signature frozen into a Provider receipt."""

    return canonical_digest(request)


def _receipt_ref(operation_key: str) -> str:
    return f"p32-provider-operation-{hashlib.sha256(operation_key.encode('utf-8')).hexdigest()}"


def _validate_signature(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("Provider request signature must be a lowercase SHA-256 digest")


def _validate_input_ref(value: str) -> None:
    if len(value) != len("p32-provider-input-") + 64 or not value.startswith(
        "p32-provider-input-"
    ):
        raise ValueError("Provider input reference must be content addressed")
    digest = value.removeprefix("p32-provider-input-")
    if any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("Provider input reference must use a lowercase SHA-256 digest")


def _validate_pricing_ref(value: str) -> None:
    if not value:
        return
    if len(value) != len("p32-provider-pricing-") + 64 or not value.startswith(
        "p32-provider-pricing-"
    ):
        raise ValueError("Provider pricing snapshot reference must be content addressed")
    digest = value.removeprefix("p32-provider-pricing-")
    if any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(
            "Provider pricing snapshot reference must use a lowercase SHA-256 digest"
        )


def _require_frozen_pricing_snapshot(
    receipt: Phase32ProviderOperationReceipt,
    pricing: Phase32ProviderPricingSnapshot,
) -> None:
    """Prevent a returned usage record from changing its frozen cost basis."""

    if not receipt.pricing_snapshot_ref:
        return
    if pricing.snapshot_ref != receipt.pricing_snapshot_ref:
        raise Phase32ProviderOperationReceiptConflict(
            "Provider return pricing snapshot differs from the frozen operation"
        )
    identities = (
        (receipt.provider_profile_id, pricing.provider_profile_id),
        (receipt.provider_template_id, pricing.provider_template_id),
        (receipt.model_id, pricing.model_id),
    )
    if any(expected and expected != actual for expected, actual in identities):
        raise Phase32ProviderOperationReceiptConflict(
            "Provider return pricing identity differs from the frozen operation"
        )


def _validate_lease_owner(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise ValueError("Provider operation lease owner is required")


def _lease_is_active(
    receipt: Phase32ProviderOperationReceipt,
    now: datetime,
) -> bool:
    if not receipt.lease_owner or not receipt.lease_expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(receipt.lease_expires_at)
    except ValueError:
        # A malformed lease must fail closed rather than allow two callers to
        # enter the Provider at the same time.
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > now


def _require_lease_owner(
    receipt: Phase32ProviderOperationReceipt,
    lease_owner: str,
    *,
    claimed_transport_attempt: int | None = None,
) -> None:
    if claimed_transport_attempt is not None:
        if (
            isinstance(claimed_transport_attempt, bool)
            or claimed_transport_attempt <= 0
        ):
            raise ValueError("Claimed Provider transport attempt must be positive")
        if receipt.transport_attempts != claimed_transport_attempt:
            raise Phase32ProviderOperationAttemptFenceConflict(
                "Provider operation transition uses a stale transport attempt"
            )
    if not receipt.lease_owner:
        return
    now = datetime.now(timezone.utc)
    if receipt.lease_owner == lease_owner:
        return
    if _lease_is_active(receipt, now):
        raise Phase32ProviderOperationLeaseConflict(
            "Provider operation transition is owned by another process"
        )


def _require_current_attempt_fence(
    receipt: Phase32ProviderOperationReceipt,
    admission_fence: Phase32ProviderOperationAdmissionFence | None,
) -> None:
    if admission_fence is None:
        if receipt.transport_admission_refs:
            raise Phase32ProviderOperationAttemptFenceConflict(
                "Budgeted Provider operation claim requires its admission fence"
            )
        return
    _require_admission_fence_identity(receipt, admission_fence)
    if (
        admission_fence.transport_attempt != receipt.transport_attempts
        or not receipt.transport_admission_refs
        or receipt.transport_admission_refs[-1] != admission_fence.admission_ref
    ):
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission fence does not match its active attempt"
        )


def _next_transport_admission_refs(
    receipt: Phase32ProviderOperationReceipt,
    admission_fence: Phase32ProviderOperationAdmissionFence | None,
    *,
    next_transport_attempt: int,
) -> tuple[str, ...]:
    if admission_fence is None:
        if (
            receipt.transport_admission_refs
            or receipt.budget_definition_digest
            or receipt.budget_authorization_ref
        ):
            raise Phase32ProviderOperationAttemptFenceConflict(
                "Budgeted Provider operation retry requires its admission fence"
            )
        return ()
    _require_admission_fence_identity(receipt, admission_fence)
    if admission_fence.transport_attempt != next_transport_attempt:
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission fence is stale for the next transport attempt"
        )
    if len(receipt.transport_admission_refs) != receipt.transport_attempts:
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission history is incomplete"
        )
    if admission_fence.admission_ref in receipt.transport_admission_refs:
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission fence was already claimed"
        )
    return (*receipt.transport_admission_refs, admission_fence.admission_ref)


def _require_admission_fence_identity(
    receipt: Phase32ProviderOperationReceipt,
    admission_fence: Phase32ProviderOperationAdmissionFence,
) -> None:
    if (
        admission_fence.run_id != receipt.run_id
        or admission_fence.operation_key != receipt.operation_key
        or admission_fence.request_signature != receipt.request_signature
    ):
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission fence targets another frozen request"
        )
    if receipt.budget_definition_digest and (
        receipt.budget_definition_digest != admission_fence.definition_digest
    ):
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission fence changes the Run definition authority"
        )
    if receipt.budget_authorization_ref and (
        receipt.budget_authorization_ref != admission_fence.authorization_ref
    ):
        raise Phase32ProviderOperationAttemptFenceConflict(
            "Provider operation admission fence changes the Run budget authority"
        )


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32ProviderOperationReceipt",
    "Phase32ProviderOperationReceiptConflict",
    "Phase32ProviderOperationLeaseConflict",
    "Phase32ProviderOperationAttemptFenceConflict",
    "Phase32ProviderOperationRetryExhausted",
    "Phase32ProviderTransportAttemptEvent",
    "Phase32ProviderOperationStore",
    "ProviderOperationReceiptStatus",
    "provider_request_signature",
]
