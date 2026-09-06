"""Redacted contracts for Phase 32 Provider configuration readiness."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Phase32ProviderStageReadiness(BaseModel):
    """Public facts for one frozen text binding; secrets and URLs are omitted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_id: str
    provider_profile_id: str
    provider_template_id: str
    model_id: str
    structured_output_mode: Literal["json_schema", "json_object", "prompt_only"]
    max_tokens: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    base_url_present: bool
    secret_present: bool
    pricing_ready: bool
    pricing_fresh: bool
    pricing_age_hours: float | None = Field(default=None, ge=0)
    image_execution_absent: bool
    ready: bool
    issue_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_readiness_semantics(self) -> "Phase32ProviderStageReadiness":
        if self.ready != (not self.issue_codes):
            raise ValueError(
                "Provider stage readiness must agree with its issue codes"
            )
        if self.ready and not all(
            (
                self.base_url_present,
                self.secret_present,
                self.pricing_ready,
                self.pricing_fresh,
            )
        ):
            raise ValueError(
                "Ready Provider stage contains a failing configuration fact"
            )
        if self.pricing_fresh and self.pricing_age_hours is None:
            raise ValueError(
                "Fresh Provider pricing requires a measured pricing age"
            )
        return self


class Phase32ProviderReadinessReport(BaseModel):
    """One no-network verdict for all billable stages of a frozen Run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["phase32_configuration_only"] = "phase32_configuration_only"
    run_id: str
    workflow_id: str
    creation_route_id: str
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: str = Field(min_length=1, max_length=80)
    require_canonical_workflow: bool
    require_text_only: bool
    required_model_id: str = ""
    required_profile_kind: str = ""
    max_pricing_age_hours: int = Field(ge=1, le=24 * 365)
    expected_stage_ids: tuple[str, ...] = Field(min_length=1)
    ready: bool
    issue_codes: tuple[str, ...] = ()
    stages: tuple[Phase32ProviderStageReadiness, ...]

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: str) -> str:
        try:
            observed_at = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Provider readiness observation timestamp is invalid") from exc
        if observed_at.tzinfo is None:
            raise ValueError("Provider readiness observation must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_readiness_semantics(self) -> "Phase32ProviderReadinessReport":
        stage_ids = tuple(stage.stage_id for stage in self.stages)
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("Provider readiness report contains duplicate stages")
        if stage_ids != self.expected_stage_ids:
            raise ValueError(
                "Provider readiness report stages differ from its frozen stage manifest"
            )

        report_issues = set(self.issue_codes)
        stage_issues = {
            issue
            for stage in self.stages
            for issue in stage.issue_codes
        }
        if not stage_issues.issubset(report_issues):
            raise ValueError(
                "Provider readiness report omits stage issue codes"
            )

        for stage in self.stages:
            expected_pricing_fresh = (
                stage.pricing_age_hours is not None
                and stage.pricing_age_hours <= self.max_pricing_age_hours
            )
            if stage.pricing_fresh != expected_pricing_fresh:
                raise ValueError(
                    "Provider stage pricing freshness differs from report policy"
                )
            if self.require_text_only and not stage.image_execution_absent:
                if "image_execution_present" not in stage.issue_codes:
                    raise ValueError(
                        "Text-only readiness must reject image execution"
                    )
            if self.required_model_id and stage.model_id != self.required_model_id:
                if "required_model_mismatch" not in stage.issue_codes:
                    raise ValueError(
                        "Provider model mismatch must block stage readiness"
                    )

        expected_ready = not self.issue_codes and all(
            stage.ready for stage in self.stages
        )
        if self.ready != expected_ready:
            raise ValueError(
                "Provider readiness report verdict differs from its stage aggregate"
            )
        return self


__all__ = [
    "Phase32ProviderReadinessReport",
    "Phase32ProviderStageReadiness",
]
