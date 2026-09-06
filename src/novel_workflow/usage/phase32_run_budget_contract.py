"""Immutable contracts for Phase 32 Run budget authorization and admission."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest


_AUTHORIZATION_REF_PREFIX = "p32-run-budget-"
_ADMISSION_REF_PREFIX = "p32-budget-admission-"


class Phase32RunBudgetAllocation(BaseModel):
    """Known Provider budget allocated at one admission boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operations: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0, allow_inf_nan=False)
    currency: Literal["USD"] = "USD"


class Phase32RunBudgetAuthorization(BaseModel):
    """One immutable, content-addressed spending authority for a Run."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    authorization_ref: str = Field(pattern=r"^p32-run-budget-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    max_cost_usd: float = Field(gt=0, allow_inf_nan=False)
    max_operations: int = Field(gt=0)
    max_total_tokens: int = Field(gt=0)
    max_transport_attempts: int = Field(default=3, ge=1, le=20)
    currency: Literal["USD"] = "USD"
    authorized_at: str = Field(min_length=1, max_length=80)

    @field_validator(
        "max_cost_usd",
        "max_operations",
        "max_total_tokens",
        "max_transport_attempts",
        mode="before",
    )
    @classmethod
    def reject_boolean_limits(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Run budget limits cannot be boolean")
        return value

    @field_validator("authorized_at")
    @classmethod
    def validate_authorized_at(cls, value: str) -> str:
        _parse_timestamp(value, label="Run budget authorization time")
        return value

    @model_validator(mode="after")
    def validate_content_address(self) -> "Phase32RunBudgetAuthorization":
        expected = _content_ref(
            _AUTHORIZATION_REF_PREFIX,
            self.model_dump(mode="json", exclude={"authorization_ref"}),
        )
        if self.authorization_ref != expected:
            raise ValueError("Run budget authorization reference does not match its payload")
        return self


class Phase32ProviderBudgetAdmission(Phase32ProviderOperationAdmissionFence):
    """Immutable proof that one transport attempt fit the frozen Run budget."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    new_logical_operation: bool
    reserved_total_tokens: int = Field(gt=0)
    reserved_cost_usd: float = Field(gt=0, allow_inf_nan=False)
    currency: Literal["USD"] = "USD"
    allocated_before: Phase32RunBudgetAllocation
    projected_after: Phase32RunBudgetAllocation
    admitted_at: str = Field(min_length=1, max_length=80)

    @field_validator(
        "transport_attempt",
        "reserved_total_tokens",
        "reserved_cost_usd",
        mode="before",
    )
    @classmethod
    def reject_boolean_reservations(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Provider budget reservations cannot be boolean")
        return value

    @field_validator("admitted_at")
    @classmethod
    def validate_admitted_at(cls, value: str) -> str:
        _parse_timestamp(value, label="Provider budget admission time")
        return value

    @model_validator(mode="after")
    def validate_admission(self) -> "Phase32ProviderBudgetAdmission":
        if self.allocated_before.currency != self.currency:
            raise ValueError("Admission allocation currency differs from its reservation")
        if self.projected_after.currency != self.currency:
            raise ValueError("Admission projection currency differs from its reservation")
        expected_operations = self.allocated_before.operations + int(
            self.new_logical_operation
        )
        if self.projected_after.operations != expected_operations:
            raise ValueError("Admission logical-operation projection is invalid")
        if (
            self.projected_after.total_tokens
            != self.allocated_before.total_tokens + self.reserved_total_tokens
        ):
            raise ValueError("Admission token projection differs from its reservation")
        expected_cost = round(
            self.allocated_before.estimated_cost_usd + self.reserved_cost_usd,
            12,
        )
        if self.projected_after.estimated_cost_usd != expected_cost:
            raise ValueError("Admission cost projection differs from its reservation")
        expected_ref = _content_ref(
            _ADMISSION_REF_PREFIX,
            self.model_dump(mode="json", exclude={"admission_ref"}),
        )
        if self.admission_ref != expected_ref:
            raise ValueError("Provider budget admission reference does not match its payload")
        return self


class Phase32RunBudgetAdmissionResult(BaseModel):
    """Runtime result; replay is observational and not persisted into the grant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    admission: Phase32ProviderBudgetAdmission
    replay: bool


class Phase32RunBudgetConflict(ValueError):
    code = "phase32_run_budget_conflict"


class Phase32RunBudgetAdmissionDenied(ValueError):
    code = "phase32_run_budget_admission_denied"

    def __init__(self, issue_codes: tuple[str, ...]) -> None:
        self.issue_codes = issue_codes
        super().__init__("Phase 32 Provider budget admission denied: " + ", ".join(issue_codes))


def freeze_phase32_run_budget_authorization(
    *,
    run_id: str,
    definition_digest: str,
    max_cost_usd: float,
    max_operations: int,
    max_total_tokens: int,
    max_transport_attempts: int = 3,
    authorized_at: str | None = None,
) -> Phase32RunBudgetAuthorization:
    """Freeze exact Run limits into a validated content-addressed authority."""

    payload = {
        "architecture_version": "phase32-routes-v1",
        "run_id": run_id,
        "definition_digest": definition_digest,
        "max_cost_usd": float(max_cost_usd),
        "max_operations": max_operations,
        "max_total_tokens": max_total_tokens,
        "max_transport_attempts": max_transport_attempts,
        "currency": "USD",
        "authorized_at": authorized_at or datetime.now(timezone.utc).isoformat(),
    }
    return Phase32RunBudgetAuthorization.model_validate(
        {
            **payload,
            "authorization_ref": _content_ref(_AUTHORIZATION_REF_PREFIX, payload),
        }
    )


def build_phase32_provider_budget_admission(
    payload: dict[str, Any],
) -> Phase32ProviderBudgetAdmission:
    """Validate and content-address one server-derived admission payload."""

    return Phase32ProviderBudgetAdmission.model_validate(
        {
            **payload,
            "admission_ref": _content_ref(_ADMISSION_REF_PREFIX, payload),
        }
    )


def _content_ref(prefix: str, payload: dict[str, Any]) -> str:
    return f"{prefix}{canonical_digest(payload)}"


def _parse_timestamp(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


__all__ = [
    "Phase32ProviderBudgetAdmission",
    "Phase32RunBudgetAdmissionDenied",
    "Phase32RunBudgetAdmissionResult",
    "Phase32RunBudgetAllocation",
    "Phase32RunBudgetAuthorization",
    "Phase32RunBudgetConflict",
    "build_phase32_provider_budget_admission",
    "freeze_phase32_run_budget_authorization",
]
