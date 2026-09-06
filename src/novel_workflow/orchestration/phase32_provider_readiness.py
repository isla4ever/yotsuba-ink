"""Redacted, configuration-only readiness for a frozen Phase 32 Run.

The report intentionally performs no Provider request and persists nothing.  It
is the release-harness gate between an immutable Run definition and the first
billable operation.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Literal

from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.providers.phase32_readiness_contract import (
    Phase32ProviderReadinessReport,
    Phase32ProviderStageReadiness,
)
from novel_workflow.providers.usage import (
    Phase32PricingReadinessError,
    ensure_phase32_text_pricing_ready,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.workflow_ids import is_canonical_workflow_id


SecretResolver = Callable[[str], str | None]


class Phase32ProviderReadinessError(ValueError):
    code = "phase32_provider_configuration_not_ready"

    def __init__(self, report: Phase32ProviderReadinessReport) -> None:
        self.report = report
        super().__init__(
            "Phase 32 Provider configuration is not ready: "
            + ", ".join(report.issue_codes)
        )


def phase32_provider_readiness_report(
    definition: GraphRunDefinition,
    *,
    secret_resolver: SecretResolver,
    now: datetime | None = None,
    max_pricing_age_hours: int = 24,
    require_canonical_workflow: bool = True,
    require_text_only: bool = True,
    required_model_id: str = "",
    required_profile_kind: str = "",
) -> Phase32ProviderReadinessReport:
    """Inspect only frozen configuration and local secret availability.

    The function does not create a Run, write a receipt/input snapshot, or
    contact a Provider.  Its return type deliberately has no Base URL, pricing
    source URL, secret reference, key, prompt, schema, or payload fields.
    """

    if not 1 <= max_pricing_age_hours <= 24 * 365:
        raise ValueError("Pricing freshness must be between 1 hour and 1 year")
    observed_at = _utc(now or datetime.now(timezone.utc))
    report_issues: list[str] = []
    if require_canonical_workflow and not is_canonical_workflow_id(
        definition.workflow_id
    ):
        report_issues.append("workflow_not_canonical")
    profile_kind = str(definition.scale_profile.payload.get("profile_kind") or "")
    if required_profile_kind and profile_kind != required_profile_kind:
        report_issues.append("scale_profile_kind_mismatch")

    expected_stage_ids = definition.route_contract.provider_stage_ids
    actual_stage_ids = tuple(
        item.stage_id for item in definition.provider_bindings_by_stage
    )
    if actual_stage_ids != expected_stage_ids:
        report_issues.append("provider_stage_order_mismatch")

    checks: list[Phase32ProviderStageReadiness] = []
    for frozen in definition.provider_bindings_by_stage:
        issues: list[str] = []
        if canonical_digest(frozen.binding.payload) != frozen.binding.payload_digest:
            issues.append("provider_binding_digest_mismatch")
        try:
            binding = Phase32StageProviderBindingSnapshot.model_validate(
                frozen.binding.payload
            )
        except Exception:
            report_issues.append("provider_binding_invalid")
            continue
        execution = binding.execution
        base_url_present = bool(execution.provider_config.base_url.strip())
        if not base_url_present:
            issues.append("base_url_missing")
        try:
            resolved_secret = secret_resolver(execution.provider_config.secret_ref)
        except Exception:
            resolved_secret = None
            issues.append("secret_resolution_failed")
        secret_present = bool(
            isinstance(resolved_secret, str) and resolved_secret.strip()
        )
        if not secret_present:
            issues.append("secret_missing")
        try:
            ensure_phase32_text_pricing_ready(execution.pricing_snapshot)
            pricing_ready = True
        except Phase32PricingReadinessError as exc:
            pricing_ready = False
            issues.extend(exc.issue_codes)
        pricing_age_hours = _pricing_age_hours(
            execution.pricing_snapshot.verified_at,
            observed_at,
        )
        pricing_fresh = (
            pricing_age_hours is not None
            and pricing_age_hours <= max_pricing_age_hours
        )
        if pricing_age_hours is None:
            if "pricing_verification_missing" not in issues:
                issues.append("pricing_verification_invalid")
        elif not pricing_fresh:
            issues.append("pricing_verification_stale")
        image_execution_absent = binding.image_execution is None
        if require_text_only and not image_execution_absent:
            issues.append("image_execution_present")
        if required_model_id and execution.model_id != required_model_id:
            issues.append("required_model_mismatch")
        issues = list(dict.fromkeys(issues))
        checks.append(
            Phase32ProviderStageReadiness(
                stage_id=binding.stage_id,
                provider_profile_id=execution.provider_profile_id,
                provider_template_id=execution.provider_template_id,
                model_id=execution.model_id,
                structured_output_mode=_structured_output_mode(binding),
                max_tokens=execution.model_settings.max_tokens,
                timeout_seconds=execution.model_settings.timeout_seconds,
                base_url_present=base_url_present,
                secret_present=secret_present,
                pricing_ready=pricing_ready,
                pricing_fresh=pricing_fresh,
                pricing_age_hours=pricing_age_hours,
                image_execution_absent=image_execution_absent,
                ready=not issues,
                issue_codes=tuple(issues),
            )
        )
    report_issues.extend(
        issue
        for check in checks
        for issue in check.issue_codes
    )
    report_issues = list(dict.fromkeys(report_issues))
    return Phase32ProviderReadinessReport(
        run_id=definition.run_id,
        workflow_id=definition.workflow_id,
        creation_route_id=definition.creation_route_id,
        definition_digest=definition.definition_digest,
        observed_at=observed_at.isoformat(),
        require_canonical_workflow=require_canonical_workflow,
        require_text_only=require_text_only,
        required_model_id=required_model_id,
        required_profile_kind=required_profile_kind,
        max_pricing_age_hours=max_pricing_age_hours,
        expected_stage_ids=expected_stage_ids,
        ready=not report_issues and len(checks) == len(expected_stage_ids),
        issue_codes=tuple(report_issues),
        stages=tuple(checks),
    )


def ensure_phase32_provider_ready(
    definition: GraphRunDefinition,
    *,
    secret_resolver: SecretResolver,
    now: datetime | None = None,
    max_pricing_age_hours: int = 24,
    require_canonical_workflow: bool = True,
    require_text_only: bool = True,
    required_model_id: str = "",
    required_profile_kind: str = "",
) -> Phase32ProviderReadinessReport:
    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=secret_resolver,
        now=now,
        max_pricing_age_hours=max_pricing_age_hours,
        require_canonical_workflow=require_canonical_workflow,
        require_text_only=require_text_only,
        required_model_id=required_model_id,
        required_profile_kind=required_profile_kind,
    )
    if not report.ready:
        raise Phase32ProviderReadinessError(report)
    return report


def _structured_output_mode(
    binding: Phase32StageProviderBindingSnapshot,
) -> Literal["json_schema", "json_object", "prompt_only"]:
    template = binding.execution.provider_template
    model = binding.execution.model_id
    capability = next(
        (
            item
            for item in template.model_capabilities
            if fnmatchcase(model.casefold(), item.model_pattern.casefold())
        ),
        None,
    )
    return (
        capability.structured_output_mode
        if capability is not None and capability.structured_output_mode is not None
        else template.structured_output_mode
    )


def _pricing_age_hours(value: str, now: datetime) -> float | None:
    try:
        verified_at = _utc(datetime.fromisoformat(value))
    except (TypeError, ValueError):
        return None
    seconds = (now - verified_at).total_seconds()
    if seconds < 0:
        return None
    return round(seconds / 3_600, 6)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Readiness clock must include a timezone")
    return value.astimezone(timezone.utc)


__all__ = [
    "Phase32ProviderReadinessError",
    "Phase32ProviderReadinessReport",
    "Phase32ProviderStageReadiness",
    "ensure_phase32_provider_ready",
    "phase32_provider_readiness_report",
]
