"""Frozen Run budgets and fail-closed Provider-operation admission.

This module deliberately does not call a Provider or know about Graph
execution.  It projects durable Provider receipts together with immutable
per-operation reservations, then grants the next logical operation only when
the whole Run remains inside its frozen authorization.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from novel_workflow.usage.phase32_run_budget_contract import (
    Phase32ProviderBudgetAdmission,
    Phase32RunBudgetAdmissionDenied,
    Phase32RunBudgetAdmissionResult,
    Phase32RunBudgetAllocation,
    Phase32RunBudgetAuthorization,
    Phase32RunBudgetConflict,
    build_phase32_provider_budget_admission,
    freeze_phase32_run_budget_authorization,
)


_RETURNED_STATUSES = frozenset({"returned", "succeeded", "contract_rejected"})


class _Receipt(Protocol):
    run_id: str
    operation_key: str
    request_signature: str
    status: str
    usage: dict[str, int]
    estimated_cost_usd: float | None
    cost_status: str
    transport_attempts: int
    transport_admission_refs: tuple[str, ...]
    lease_owner: str
    lease_expires_at: str


class Phase32ProviderOperationReader(Protocol):
    def list(self, run_id: str) -> list[_Receipt]: ...


AdmissionTransaction = Callable[
    [
        Phase32RunBudgetAuthorization,
        tuple[Phase32ProviderBudgetAdmission, ...],
    ],
    Phase32ProviderBudgetAdmission,
]


class Phase32RunBudgetAdmissionStore(Protocol):
    def transact_admission(
        self,
        *,
        run_id: str,
        operation_key: str,
        transaction: AdmissionTransaction,
    ) -> tuple[Phase32ProviderBudgetAdmission, bool]: ...


class Phase32RunBudgetAdmissionService:
    """Admit logical operations from durable receipts and reservations only."""

    def __init__(
        self,
        budgets: Phase32RunBudgetAdmissionStore,
        provider_operations: Phase32ProviderOperationReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.budgets = budgets
        self.provider_operations = provider_operations
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def admit(
        self,
        *,
        run_id: str,
        definition_digest: str,
        operation_key: str,
        request_signature: str,
        reserved_total_tokens: int | None,
        reserved_cost_usd: float | None,
        max_transport_attempts: int = 3,
    ) -> Phase32RunBudgetAdmissionResult:
        """Reserve the next operation, or return its existing immutable grant.

        A caller must provide positive conservative upper bounds.  Returned
        receipts replace their reservation with actual usage for subsequent
        admissions. Pending/not-yet-created operations retain the reservation.
        """

        _validate_digest(definition_digest, label="Run definition digest")
        _validate_request_identity(operation_key, request_signature)
        _validate_max_transport_attempts(max_transport_attempts)
        reservation_issues = _reservation_issue_codes(
            reserved_total_tokens=reserved_total_tokens,
            reserved_cost_usd=reserved_cost_usd,
        )
        if reservation_issues:
            raise Phase32RunBudgetAdmissionDenied(reservation_issues)
        assert reserved_total_tokens is not None
        assert reserved_cost_usd is not None
        normalized_cost_reserve = _cost(float(reserved_cost_usd))

        def transaction(
            authorization: Phase32RunBudgetAuthorization,
            admissions: tuple[Phase32ProviderBudgetAdmission, ...],
        ) -> Phase32ProviderBudgetAdmission:
            if authorization.definition_digest != definition_digest:
                raise Phase32RunBudgetAdmissionDenied(
                    ("budget_definition_mismatch",)
                )
            if authorization.max_transport_attempts != max_transport_attempts:
                raise Phase32RunBudgetAdmissionDenied(
                    ("budget_transport_attempt_limit_mismatch",)
                )
            receipts = tuple(self.provider_operations.list(run_id))
            receipt_by_key = _receipt_map(run_id, receipts)
            admission_by_key = _admission_map(run_id, admissions, receipt_by_key)
            if any(
                admission.authorization_ref != authorization.authorization_ref
                for admission in admissions
            ):
                raise Phase32RunBudgetConflict(
                    "Run budget admissions use another authorization"
                )
            current_receipt = receipt_by_key.get(operation_key)
            current_admissions = admission_by_key.get(operation_key, ())
            desired_attempt = _desired_transport_attempt(
                current_receipt,
                current_admissions,
                now=self.clock(),
            )
            if desired_attempt > authorization.max_transport_attempts:
                raise Phase32RunBudgetAdmissionDenied(
                    ("transport_retry_limit_exhausted",)
                )
            existing = next(
                (
                    admission
                    for admission in current_admissions
                    if admission.transport_attempt == desired_attempt
                ),
                None,
            )
            if existing is not None:
                _require_matching_replay(
                    existing,
                    authorization=authorization,
                    request_signature=request_signature,
                    reserved_total_tokens=reserved_total_tokens,
                    reserved_cost_usd=normalized_cost_reserve,
                )
                return existing

            if current_receipt is not None:
                if current_receipt.request_signature != request_signature:
                    raise Phase32RunBudgetConflict(
                        "Provider operation key was reused with another request signature"
                    )
                if current_receipt.status != "pending":
                    raise Phase32RunBudgetAdmissionDenied(
                        ("operation_started_without_budget_admission",)
                    )

            allocated_before = _project_allocation(
                run_id=run_id,
                receipts=receipts,
                admissions=admissions,
                ignored_pending_operation_key=(
                    operation_key if not current_admissions else None
                ),
            )
            new_logical_operation = operation_key not in (
                set(receipt_by_key) | set(admission_by_key)
            )
            if current_receipt is not None and not current_admissions:
                # ``begin`` creates the receipt immediately before admission;
                # it has not consumed a logical-operation slot until now.
                new_logical_operation = True
            projected_after = Phase32RunBudgetAllocation(
                operations=allocated_before.operations + int(new_logical_operation),
                total_tokens=allocated_before.total_tokens + reserved_total_tokens,
                estimated_cost_usd=_cost(
                    allocated_before.estimated_cost_usd + normalized_cost_reserve
                ),
                currency=authorization.currency,
            )
            limit_issues = _limit_issue_codes(authorization, projected_after)
            if limit_issues:
                raise Phase32RunBudgetAdmissionDenied(limit_issues)
            admitted_at = _utc_iso(self.clock())
            payload = {
                "architecture_version": "phase32-routes-v1",
                "authorization_ref": authorization.authorization_ref,
                "run_id": run_id,
                "definition_digest": definition_digest,
                "operation_key": operation_key,
                "request_signature": request_signature,
                "transport_attempt": desired_attempt,
                "new_logical_operation": new_logical_operation,
                "reserved_total_tokens": reserved_total_tokens,
                "reserved_cost_usd": normalized_cost_reserve,
                "currency": authorization.currency,
                "allocated_before": allocated_before.model_dump(mode="json"),
                "projected_after": projected_after.model_dump(mode="json"),
                "admitted_at": admitted_at,
            }
            return build_phase32_provider_budget_admission(payload)

        try:
            admission, replay = self.budgets.transact_admission(
                run_id=run_id,
                operation_key=operation_key,
                transaction=transaction,
            )
        except FileNotFoundError as exc:
            raise Phase32RunBudgetAdmissionDenied(
                ("budget_authorization_missing",)
            ) from exc
        return Phase32RunBudgetAdmissionResult(admission=admission, replay=replay)


def _project_allocation(
    *,
    run_id: str,
    receipts: tuple[_Receipt, ...],
    admissions: tuple[Phase32ProviderBudgetAdmission, ...],
    ignored_pending_operation_key: str | None = None,
) -> Phase32RunBudgetAllocation:
    receipt_by_key = _receipt_map(run_id, receipts)
    admission_by_key = _admission_map(run_id, admissions, receipt_by_key)

    operations = set(receipt_by_key) | set(admission_by_key)
    allocated_operations = 0
    total_tokens = 0
    cost_usd = 0.0
    issues: list[str] = []
    for operation_key in sorted(operations):
        receipt = receipt_by_key.get(operation_key)
        operation_admissions = admission_by_key.get(operation_key, ())
        if (
            receipt is not None
            and not operation_admissions
            and operation_key == ignored_pending_operation_key
            and receipt.status == "pending"
            and receipt.transport_attempts == 0
        ):
            continue
        allocated_operations += 1
        if receipt is not None and not operation_admissions:
            issues.append("receipt_budget_admission_missing")
            continue
        if receipt is None:
            if tuple(item.transport_attempt for item in operation_admissions) != (1,):
                raise Phase32RunBudgetConflict(
                    "Unstarted operation has an invalid budget-attempt sequence"
                )
            total_tokens += operation_admissions[0].reserved_total_tokens
            cost_usd += operation_admissions[0].reserved_cost_usd
            continue
        if receipt.status == "pending":
            claim_issue = _claimed_admission_issue(receipt, operation_admissions)
            if claim_issue:
                issues.append(claim_issue)
                continue
            if len(operation_admissions) > receipt.transport_attempts + 1:
                raise Phase32RunBudgetConflict(
                    "Pending operation has too many future budget admissions"
                )
            total_tokens += sum(
                item.reserved_total_tokens for item in operation_admissions
            )
            cost_usd += sum(item.reserved_cost_usd for item in operation_admissions)
            continue
        if receipt.status not in _RETURNED_STATUSES:
            issues.append("receipt_status_unknown")
            continue
        if receipt.transport_attempts == 0:
            issues.append("terminal_receipt_without_transport_attempt")
            continue
        claim_issue = _claimed_admission_issue(receipt, operation_admissions)
        if claim_issue:
            issues.append(claim_issue)
            continue
        if len(operation_admissions) > receipt.transport_attempts + 1:
            raise Phase32RunBudgetConflict(
                "Terminal operation has too many future budget admissions"
            )
        # A terminal receipt proves that one trailing N+1 grant was never
        # claimed.  The grant remains immutable but is implicitly void and
        # must not consume Run capacity.
        claimed_admissions = operation_admissions[: receipt.transport_attempts]
        if len(claimed_admissions) != receipt.transport_attempts:
            issues.append("transport_attempt_without_budget_admission")
            continue
        for failed_attempt in claimed_admissions[:-1]:
            total_tokens += failed_attempt.reserved_total_tokens
            cost_usd += failed_attempt.reserved_cost_usd
        prompt_tokens = receipt.usage.get("prompt_tokens")
        completion_tokens = receipt.usage.get("completion_tokens")
        receipt_total_tokens = receipt.usage.get("total_tokens")
        if prompt_tokens is None or completion_tokens is None:
            issues.append("receipt_token_usage_incomplete")
        elif receipt_total_tokens is None:
            issues.append("receipt_total_tokens_unknown")
        elif receipt_total_tokens < prompt_tokens + completion_tokens:
            issues.append("receipt_total_tokens_inconsistent")
        else:
            total_tokens += max(
                receipt_total_tokens,
                prompt_tokens + completion_tokens,
            )
        if receipt.cost_status != "known" or receipt.estimated_cost_usd is None:
            issues.append("receipt_cost_unknown")
        else:
            cost_usd += receipt.estimated_cost_usd
    if issues:
        raise Phase32RunBudgetAdmissionDenied(tuple(dict.fromkeys(issues)))
    return Phase32RunBudgetAllocation(
        operations=allocated_operations,
        total_tokens=total_tokens,
        estimated_cost_usd=_cost(cost_usd),
    )


def _claimed_admission_issue(
    receipt: _Receipt,
    admissions: tuple[Phase32ProviderBudgetAdmission, ...],
) -> str:
    claimed_attempts = receipt.transport_attempts
    if len(admissions) < claimed_attempts:
        return "transport_attempt_without_budget_admission"
    if len(receipt.transport_admission_refs) != claimed_attempts:
        return "transport_admission_ref_missing"
    expected_refs = tuple(
        admission.admission_ref for admission in admissions[:claimed_attempts]
    )
    if receipt.transport_admission_refs != expected_refs:
        return "transport_admission_ref_mismatch"
    return ""


def _admission_map(
    run_id: str,
    admissions: tuple[Phase32ProviderBudgetAdmission, ...],
    receipt_by_key: dict[str, _Receipt],
) -> dict[str, tuple[Phase32ProviderBudgetAdmission, ...]]:
    grouped: dict[str, list[Phase32ProviderBudgetAdmission]] = {}
    for admission in admissions:
        if admission.run_id != run_id:
            raise Phase32RunBudgetConflict("Budget admission belongs to another Run")
        grouped.setdefault(admission.operation_key, []).append(admission)
        receipt = receipt_by_key.get(admission.operation_key)
        if receipt is not None and receipt.request_signature != admission.request_signature:
            raise Phase32RunBudgetConflict(
                "Provider receipt differs from its budget admission"
            )
    result: dict[str, tuple[Phase32ProviderBudgetAdmission, ...]] = {}
    for operation_key, items in grouped.items():
        ordered = tuple(sorted(items, key=lambda item: item.transport_attempt))
        attempts = tuple(item.transport_attempt for item in ordered)
        if attempts != tuple(range(1, len(ordered) + 1)):
            raise Phase32RunBudgetConflict(
                "Provider budget admission attempts are not contiguous"
            )
        if len({item.request_signature for item in ordered}) != 1:
            raise Phase32RunBudgetConflict(
                "Provider operation budget admissions bind different requests"
            )
        result[operation_key] = ordered
    return result


def _receipt_map(run_id: str, receipts: tuple[_Receipt, ...]) -> dict[str, _Receipt]:
    result: dict[str, _Receipt] = {}
    for receipt in receipts:
        if receipt.run_id != run_id:
            raise Phase32RunBudgetConflict("Provider receipt belongs to another Run")
        if receipt.operation_key in result:
            raise Phase32RunBudgetConflict("Provider operation receipt identity is duplicated")
        result[receipt.operation_key] = receipt
    return result


def _desired_transport_attempt(
    receipt: _Receipt | None,
    admissions: tuple[Phase32ProviderBudgetAdmission, ...],
    *,
    now: datetime,
) -> int:
    latest_admitted = admissions[-1].transport_attempt if admissions else 0
    if receipt is None:
        return latest_admitted or 1
    if receipt.status in _RETURNED_STATUSES:
        return receipt.transport_attempts or 1
    if receipt.status != "pending":
        raise Phase32RunBudgetAdmissionDenied(("receipt_status_unknown",))
    if receipt.transport_attempts > latest_admitted:
        raise Phase32RunBudgetAdmissionDenied(
            ("transport_attempt_without_budget_admission",)
        )
    if receipt.transport_attempts == 0:
        return 1
    if latest_admitted == receipt.transport_attempts + 1:
        return latest_admitted
    if latest_admitted != receipt.transport_attempts:
        raise Phase32RunBudgetConflict(
            "Pending Provider operation budget-attempt sequence is invalid"
        )
    if _lease_is_active(receipt, now):
        return latest_admitted
    return receipt.transport_attempts + 1


def _lease_is_active(receipt: _Receipt, now: datetime) -> bool:
    if not receipt.lease_owner or not receipt.lease_expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(receipt.lease_expires_at)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return expires_at > now.astimezone(timezone.utc)


def _require_matching_replay(
    admission: Phase32ProviderBudgetAdmission,
    *,
    authorization: Phase32RunBudgetAuthorization,
    request_signature: str,
    reserved_total_tokens: int,
    reserved_cost_usd: float,
) -> None:
    if admission.authorization_ref != authorization.authorization_ref:
        raise Phase32RunBudgetConflict("Budget admission uses another authorization")
    if (
        admission.request_signature != request_signature
        or admission.reserved_total_tokens != reserved_total_tokens
        or admission.reserved_cost_usd != reserved_cost_usd
    ):
        raise Phase32RunBudgetConflict(
            "Provider operation key was reused with another budget reservation"
        )


def _reservation_issue_codes(
    *,
    reserved_total_tokens: int | None,
    reserved_cost_usd: float | None,
) -> tuple[str, ...]:
    issues: list[str] = []
    if (
        isinstance(reserved_total_tokens, bool)
        or not isinstance(reserved_total_tokens, int)
        or reserved_total_tokens <= 0
    ):
        issues.append("reservation_total_tokens_unknown")
    if (
        isinstance(reserved_cost_usd, bool)
        or not isinstance(reserved_cost_usd, (int, float))
        or not math.isfinite(float(reserved_cost_usd))
        or reserved_cost_usd <= 0
    ):
        issues.append("reservation_cost_unknown")
    return tuple(issues)


def _limit_issue_codes(
    authorization: Phase32RunBudgetAuthorization,
    projected: Phase32RunBudgetAllocation,
) -> tuple[str, ...]:
    issues: list[str] = []
    if projected.operations > authorization.max_operations:
        issues.append("operation_limit_exceeded")
    if projected.total_tokens > authorization.max_total_tokens:
        issues.append("token_limit_exceeded")
    if projected.estimated_cost_usd > authorization.max_cost_usd:
        issues.append("cost_limit_exceeded")
    return tuple(issues)


def _validate_request_identity(operation_key: str, request_signature: str) -> None:
    if not isinstance(operation_key, str) or not operation_key.strip() or len(operation_key) > 500:
        raise ValueError("Provider operation key is required")
    if (
        not isinstance(request_signature, str)
        or len(request_signature) != 64
        or any(character not in "0123456789abcdef" for character in request_signature)
    ):
        raise ValueError("Provider request signature must be a lowercase SHA-256 digest")


def _validate_max_transport_attempts(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 20:
        raise ValueError("Provider transport attempts must be between 1 and 20")


def _validate_digest(value: str, *, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _cost(value: float) -> float:
    return round(value, 12)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


__all__ = [
    "AdmissionTransaction",
    "Phase32ProviderBudgetAdmission",
    "Phase32ProviderOperationReader",
    "Phase32RunBudgetAdmissionDenied",
    "Phase32RunBudgetAdmissionResult",
    "Phase32RunBudgetAdmissionService",
    "Phase32RunBudgetAdmissionStore",
    "Phase32RunBudgetAllocation",
    "Phase32RunBudgetAuthorization",
    "Phase32RunBudgetConflict",
    "freeze_phase32_run_budget_authorization",
]
