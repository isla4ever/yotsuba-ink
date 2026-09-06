"""Auditable, zero-call contracts for a Phase 32 live candidate preflight."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32PricingAttestationCommand(BaseModel):
    """Explicit operator statement used to refresh one model price."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    idempotency_key: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
    )
    expected_profile_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_profile_id: Literal["provider-deepseek-text"] = (
        "provider-deepseek-text"
    )
    provider_template_id: Literal["deepseek-text"] = "deepseek-text"
    model_id: Literal["deepseek-v4-pro"] = "deepseek-v4-pro"
    input_usd_per_million_tokens: float = Field(gt=0, allow_inf_nan=False)
    output_usd_per_million_tokens: float = Field(gt=0, allow_inf_nan=False)
    source_url: str = Field(min_length=1, max_length=2_000)
    verified_at: str = Field(min_length=1, max_length=80)
    estimate_basis: Literal["conservative_upper_bound"] = (
        "conservative_upper_bound"
    )
    estimate_basis_note: str = Field(min_length=1, max_length=1_000)
    attested_by: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
    )

    @field_validator("verified_at")
    @classmethod
    def validate_verified_at(cls, value: str) -> str:
        _parse_timestamp(value, label="Pricing verification time")
        return value


class Phase32PricingAttestation(BaseModel):
    """Immutable proof of the exact Provider profile pricing mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    attestation_ref: str = Field(pattern=r"^p32-pricing-attestation-[a-f0-9]{64}$")
    idempotency_key: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
    )
    command_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_profile_id: Literal["provider-deepseek-text"]
    provider_template_id: Literal["deepseek-text"]
    model_id: Literal["deepseek-v4-pro"]
    input_usd_per_million_tokens: float = Field(gt=0, allow_inf_nan=False)
    output_usd_per_million_tokens: float = Field(gt=0, allow_inf_nan=False)
    source_url: str = Field(min_length=1, max_length=2_000)
    verified_at: str = Field(min_length=1, max_length=80)
    estimate_basis: Literal["conservative_upper_bound"]
    estimate_basis_note: str = Field(min_length=1, max_length=1_000)
    attested_by: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$"
    )
    attested_at: str = Field(min_length=1, max_length=80)
    profile_before_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile_after_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_attestation(self) -> Self:
        verified_at = _parse_timestamp(
            self.verified_at,
            label="Pricing verification time",
        )
        attested_at = _parse_timestamp(self.attested_at, label="Pricing attestation time")
        if verified_at > attested_at:
            raise ValueError("Pricing verification cannot follow its attestation")
        expected = pricing_attestation_ref(
            self.model_dump(mode="json", exclude={"attestation_ref"})
        )
        if self.attestation_ref != expected:
            raise ValueError("Pricing attestation is not content addressed")
        return self


class Phase32LiveCandidateEnvironmentReport(BaseModel):
    """Redacted proof that local configuration is ready for a budget decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    report_version: Literal["phase32-live-candidate-preflight.v1"] = (
        "phase32-live-candidate-preflight.v1"
    )
    report_ref: str = Field(pattern=r"^p32-live-preflight-[a-f0-9]{64}$")
    observed_at: str = Field(min_length=1, max_length=80)
    provider_profile_id: Literal["provider-deepseek-text"] = (
        "provider-deepseek-text"
    )
    provider_template_id: str = Field(default="", max_length=240)
    model_id: Literal["deepseek-v4-pro"] = "deepseek-v4-pro"
    profile_digest: str = Field(default="", pattern=r"^$|^[a-f0-9]{64}$")
    pricing_attestation_ref: str = Field(
        default="",
        pattern=r"^$|^p32-pricing-attestation-[a-f0-9]{64}$",
    )
    pricing_snapshot_ref: str = Field(
        default="",
        pattern=r"^$|^p32-provider-pricing-[a-f0-9]{64}$",
    )
    pricing_source_digest: str = Field(default="", pattern=r"^$|^[a-f0-9]{64}$")
    pricing_verified_at: str = Field(default="", max_length=80)
    pricing_age_hours: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    input_usd_per_million_tokens: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    output_usd_per_million_tokens: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
    )
    secret_configured: bool
    issue_codes: tuple[str, ...] = ()
    verdict: Literal["blocked", "ready_for_budget_authorization"]
    next_gate: Literal["refresh_environment", "explicit_run_budget"]
    billable_call_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        _parse_timestamp(self.observed_at, label="Preflight observation time")
        if len(self.issue_codes) != len(set(self.issue_codes)):
            raise ValueError("Live preflight issue codes must be unique")
        ready = not self.issue_codes
        if ready != (self.verdict == "ready_for_budget_authorization"):
            raise ValueError("Live preflight verdict must match its issues")
        expected_gate = "explicit_run_budget" if ready else "refresh_environment"
        if self.next_gate != expected_gate:
            raise ValueError("Live preflight next gate must match its verdict")
        expected = live_candidate_environment_report_ref(
            self.model_dump(mode="json", exclude={"report_ref"})
        )
        if self.report_ref != expected:
            raise ValueError("Live candidate preflight report is not content addressed")
        return self


class Phase32LiveCandidateAuthorization(BaseModel):
    """Immutable binding of every authority required before a live Run."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    authorization_version: Literal["phase32-live-candidate-authorization.v1"] = (
        "phase32-live-candidate-authorization.v1"
    )
    authorization_ref: str = Field(
        pattern=r"^p32-live-candidate-auth-[a-f0-9]{64}$"
    )
    issued_at: str = Field(min_length=1, max_length=80)
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    environment_report_ref: str = Field(
        pattern=r"^p32-live-preflight-[a-f0-9]{64}$"
    )
    pricing_attestation_ref: str = Field(
        pattern=r"^p32-pricing-attestation-[a-f0-9]{64}$"
    )
    profile_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    pricing_snapshot_ref: str = Field(
        pattern=r"^p32-provider-pricing-[a-f0-9]{64}$"
    )
    readiness_admission_ref: str = Field(
        pattern=r"^p32-provider-readiness-[a-f0-9]{64}$"
    )
    readiness_report_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    budget_authorization_ref: str = Field(
        pattern=r"^p32-run-budget-[a-f0-9]{64}$"
    )
    max_cost_usd: float = Field(gt=0, allow_inf_nan=False)
    max_operations: int = Field(gt=0)
    max_total_tokens: int = Field(gt=0)
    max_transport_attempts: Literal[3] = 3
    authorization_basis: Literal["user_confirmed_limits"] = (
        "user_confirmed_limits"
    )
    text_only: Literal[True] = True
    billable_call_count_at_issue: Literal[0] = 0

    @field_validator(
        "max_cost_usd",
        "max_operations",
        "max_total_tokens",
        "max_transport_attempts",
        "billable_call_count_at_issue",
        mode="before",
    )
    @classmethod
    def reject_boolean_limits(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Live candidate authorization values cannot be boolean")
        return value

    @model_validator(mode="after")
    def validate_authorization(self) -> Self:
        _parse_timestamp(self.issued_at, label="Live candidate authorization time")
        expected = live_candidate_authorization_ref(
            self.model_dump(mode="json", exclude={"authorization_ref"})
        )
        if self.authorization_ref != expected:
            raise ValueError("Live candidate authorization is not content addressed")
        return self


def build_pricing_attestation(
    command: Phase32PricingAttestationCommand,
    *,
    attested_at: str,
    profile_after_digest: str,
) -> Phase32PricingAttestation:
    command_payload = command.model_dump(mode="json")
    payload = {
        "architecture_version": "phase32-routes-v1",
        "idempotency_key": command.idempotency_key,
        "command_digest": canonical_digest(command_payload),
        "provider_profile_id": command.provider_profile_id,
        "provider_template_id": command.provider_template_id,
        "model_id": command.model_id,
        "input_usd_per_million_tokens": command.input_usd_per_million_tokens,
        "output_usd_per_million_tokens": command.output_usd_per_million_tokens,
        "source_url": command.source_url,
        "verified_at": command.verified_at,
        "estimate_basis": command.estimate_basis,
        "estimate_basis_note": command.estimate_basis_note,
        "attested_by": command.attested_by,
        "attested_at": attested_at,
        "profile_before_digest": command.expected_profile_digest,
        "profile_after_digest": profile_after_digest,
    }
    return Phase32PricingAttestation.model_validate(
        {**payload, "attestation_ref": pricing_attestation_ref(payload)}
    )


def build_live_candidate_environment_report(
    payload: dict[str, object],
) -> Phase32LiveCandidateEnvironmentReport:
    return Phase32LiveCandidateEnvironmentReport.model_validate(
        {**payload, "report_ref": live_candidate_environment_report_ref(payload)}
    )


def build_live_candidate_authorization(
    payload: dict[str, object],
) -> Phase32LiveCandidateAuthorization:
    return Phase32LiveCandidateAuthorization.model_validate(
        {**payload, "authorization_ref": live_candidate_authorization_ref(payload)}
    )


def pricing_attestation_ref(payload: dict[str, object]) -> str:
    return f"p32-pricing-attestation-{canonical_digest(payload)}"


def live_candidate_environment_report_ref(payload: dict[str, object]) -> str:
    return f"p32-live-preflight-{canonical_digest(payload)}"


def live_candidate_authorization_ref(payload: dict[str, object]) -> str:
    return f"p32-live-candidate-auth-{canonical_digest(payload)}"


def _parse_timestamp(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "Phase32LiveCandidateAuthorization",
    "Phase32LiveCandidateEnvironmentReport",
    "Phase32PricingAttestation",
    "Phase32PricingAttestationCommand",
    "build_live_candidate_authorization",
    "build_live_candidate_environment_report",
    "build_pricing_attestation",
]
