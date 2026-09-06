"""Versioned, redacted evidence bundle contracts for private Phase 32 release runs."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32ContinuityEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Literal["ready", "blocked"]
    issue_codes: tuple[str, ...] = ()
    terminal_status: str = Field(max_length=80)
    terminal_event_count: int = Field(ge=0)
    committed_chapter_count: int = Field(ge=0)
    committed_writeback_count: int = Field(ge=0)
    pending_writeback_count: int = Field(ge=0)
    provider_operation_count: int = Field(ge=0)
    pending_provider_operation_count: int = Field(ge=0)
    transport_attempt_count: int = Field(ge=0)
    budget_admission_count: int = Field(ge=0)
    image_provider_operation_count: int = Field(ge=0)
    collaboration_provider_operation_count: int = Field(ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )
    quality_report_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_verdict(self) -> Self:
        if (self.verdict == "blocked") != bool(self.issue_codes):
            raise ValueError("Evidence summary verdict must match its issue codes")
        if len(self.issue_codes) != len(set(self.issue_codes)):
            raise ValueError("Evidence summary issue codes must be unique")
        return self


class Phase32ContinuityEvidenceBundle(BaseModel):
    """Content-addressed, secret-free snapshot of all release authorities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format_version: Literal["phase32-continuity-evidence.v1"] = (
        "phase32-continuity-evidence.v1"
    )
    bundle_ref: str = Field(pattern=r"^p32-continuity-evidence-[a-f0-9]{64}$")
    generated_at: str = Field(min_length=1, max_length=80)
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition: dict[str, Any]
    readiness_admissions: tuple[dict[str, Any], ...] = ()
    budget_authorization: dict[str, Any] | None = None
    budget_admissions: tuple[dict[str, Any], ...] = ()
    transport_attempt_events: tuple[dict[str, Any], ...] = ()
    provider_receipts: tuple[dict[str, Any], ...] = ()
    run_events: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    evidence_records: tuple[dict[str, Any], ...] = ()
    writebacks: tuple[dict[str, Any], ...] = ()
    canon_transactions: tuple[dict[str, Any], ...] = ()
    wiki_transactions: tuple[dict[str, Any], ...] = ()
    quality_reports: tuple[dict[str, Any], ...] = ()
    summary: Phase32ContinuityEvidenceSummary

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        _assert_redacted(self.model_dump(mode="json", exclude={"bundle_ref"}))
        expected = continuity_evidence_bundle_ref(
            self.model_dump(mode="json", exclude={"bundle_ref"})
        )
        if self.bundle_ref != expected:
            raise ValueError("Continuity evidence bundle is not content addressed")
        return self


def build_phase32_continuity_evidence_bundle(
    payload: dict[str, Any],
) -> Phase32ContinuityEvidenceBundle:
    return Phase32ContinuityEvidenceBundle.model_validate(
        {**payload, "bundle_ref": continuity_evidence_bundle_ref(payload)}
    )


def continuity_evidence_bundle_ref(payload: dict[str, Any]) -> str:
    return f"p32-continuity-evidence-{canonical_digest(payload)}"


def _assert_redacted(value: object) -> None:
    forbidden_keys = {
        "api_key",
        "base_url",
        "headers",
        "payload",
        "prompt",
        "raw_provider_payload",
        "rendered_prompt",
        "request",
        "result",
        "secret_ref",
        "secret_value",
        "source_url",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in forbidden_keys:
                raise ValueError("Continuity evidence bundle contains sensitive fields")
            _assert_redacted(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_redacted(nested)


__all__ = [
    "Phase32ContinuityEvidenceBundle",
    "Phase32ContinuityEvidenceSummary",
    "build_phase32_continuity_evidence_bundle",
    "continuity_evidence_bundle_ref",
]
