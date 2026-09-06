"""Persist and revalidate redacted Phase 32 Provider readiness admissions.

The private continuity authority persists this no-network verdict and Run
execution revalidates it before the first or next billable graph step.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

from novel_workflow.orchestration.phase32_provider_readiness import (
    phase32_provider_readiness_report,
)
from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessAdmission,
    Phase32ProviderReadinessAdmissionPolicy,
    Phase32ProviderReadinessStore,
    Phase32ProviderReadinessStoreError,
    parse_readiness_timestamp,
    readiness_admission_expiry,
    readiness_admission_ref,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


SecretResolver = Callable[[str], str | None]


def continuity_acceptance_provider_readiness_policy(
) -> Phase32ProviderReadinessAdmissionPolicy:
    """Return the code-owned policy for the private exact-12 DeepSeek run."""

    return Phase32ProviderReadinessAdmissionPolicy(
        required_model_id="deepseek-v4-pro",
        required_profile_kind="continuity_acceptance",
        max_pricing_age_hours=24,
        max_admission_age_seconds=900,
    )


class Phase32ProviderReadinessAdmissionVerdict(BaseModel):
    """Fail-closed projection of the latest persisted readiness observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["phase32_persisted_provider_readiness"] = (
        "phase32_persisted_provider_readiness"
    )
    run_id: str
    definition_digest: str
    policy_digest: str
    admission_ref: str = ""
    observed_at: str = ""
    expires_at: str = ""
    ready: bool
    issue_codes: tuple[str, ...] = ()


class Phase32ProviderReadinessAdmissionError(ValueError):
    code = "phase32_provider_readiness_admission_failed"

    def __init__(self, verdict: Phase32ProviderReadinessAdmissionVerdict) -> None:
        self.verdict = verdict
        super().__init__(
            "Phase 32 Provider readiness admission failed: "
            + ", ".join(verdict.issue_codes)
        )


def admit_phase32_provider_readiness(
    definition: GraphRunDefinition,
    *,
    store: Phase32ProviderReadinessStore,
    policy: Phase32ProviderReadinessAdmissionPolicy,
    secret_resolver: SecretResolver,
    now: datetime | None = None,
) -> Phase32ProviderReadinessAdmission:
    """Observe local configuration and persist one immutable redacted verdict."""

    observed_at = _utc(now or datetime.now(timezone.utc))
    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=secret_resolver,
        now=observed_at,
        max_pricing_age_hours=policy.max_pricing_age_hours,
        require_canonical_workflow=policy.require_canonical_workflow,
        require_text_only=policy.require_text_only,
        required_model_id=policy.required_model_id,
        required_profile_kind=policy.required_profile_kind,
    )
    policy_digest = canonical_digest(policy.model_dump(mode="json"))
    report_digest = canonical_digest(report.model_dump(mode="json"))
    values: dict[str, object] = {
        "architecture_version": "phase32-routes-v1",
        "run_id": definition.run_id,
        "definition_digest": definition.definition_digest,
        "observed_at": report.observed_at,
        "expires_at": readiness_admission_expiry(
            observed_at=observed_at,
            policy=policy,
            report=report,
        ).isoformat(),
        "policy": policy.model_dump(mode="json"),
        "policy_digest": policy_digest,
        "report": report.model_dump(mode="json"),
        "report_digest": report_digest,
        "verdict": "ready" if report.ready else "blocked",
    }
    admission = Phase32ProviderReadinessAdmission.model_validate(
        {"admission_ref": readiness_admission_ref(values), **values}
    )
    return store.write(admission)


def current_phase32_provider_readiness_verdict(
    definition: GraphRunDefinition,
    *,
    store: Phase32ProviderReadinessStore,
    policy: Phase32ProviderReadinessAdmissionPolicy,
    now: datetime | None = None,
) -> Phase32ProviderReadinessAdmissionVerdict:
    """Read the latest observation and reject drift, expiry, or a blocked report."""

    checked_at = _utc(now or datetime.now(timezone.utc))
    policy_digest = canonical_digest(policy.model_dump(mode="json"))
    try:
        admission = store.latest(definition.run_id)
    except Phase32ProviderReadinessStoreError:
        return _verdict(
            definition,
            policy_digest=policy_digest,
            issue_codes=("readiness_admission_unreadable",),
        )
    if admission is None:
        return _verdict(
            definition,
            policy_digest=policy_digest,
            issue_codes=("readiness_admission_missing",),
        )

    issues: list[str] = []
    if admission.definition_digest != definition.definition_digest:
        issues.append("readiness_definition_drift")
    if admission.policy_digest != policy_digest:
        issues.append("readiness_policy_mismatch")
    report = admission.report
    if report.run_id != definition.run_id:
        issues.append("readiness_report_run_mismatch")
    if report.workflow_id != definition.workflow_id:
        issues.append("readiness_report_workflow_mismatch")
    if report.creation_route_id != definition.creation_route_id:
        issues.append("readiness_report_route_mismatch")
    if report.definition_digest != definition.definition_digest:
        issues.append("readiness_report_definition_mismatch")
    if (
        report.require_canonical_workflow != policy.require_canonical_workflow
        or report.require_text_only != policy.require_text_only
        or report.required_model_id != policy.required_model_id
        or report.required_profile_kind != policy.required_profile_kind
        or report.max_pricing_age_hours != policy.max_pricing_age_hours
    ):
        issues.append("readiness_report_policy_mismatch")
    expected_stage_ids = definition.route_contract.provider_stage_ids
    report_stage_ids = tuple(stage.stage_id for stage in report.stages)
    if (
        report.expected_stage_ids != expected_stage_ids
        or report_stage_ids != expected_stage_ids
    ):
        issues.append("readiness_report_stage_manifest_mismatch")
    else:
        for stage, frozen in zip(report.stages, definition.provider_bindings_by_stage):
            try:
                binding = Phase32StageProviderBindingSnapshot.model_validate(
                    frozen.binding.payload
                )
            except Exception:
                issues.append("readiness_report_stage_identity_mismatch")
                break
            execution = binding.execution
            if (
                stage.provider_profile_id != execution.provider_profile_id
                or stage.provider_template_id != execution.provider_template_id
                or stage.model_id != execution.model_id
            ):
                issues.append("readiness_report_stage_identity_mismatch")
                break
    observed_at = parse_readiness_timestamp(admission.observed_at)
    expires_at = parse_readiness_timestamp(admission.expires_at)
    if checked_at < observed_at:
        issues.append("readiness_observation_in_future")
    if checked_at >= expires_at:
        issues.append("readiness_admission_expired")
    elapsed_hours = max(0.0, (checked_at - observed_at).total_seconds() / 3_600)
    if any(
        stage.pricing_age_hours is None
        or stage.pricing_age_hours + elapsed_hours > policy.max_pricing_age_hours
        for stage in report.stages
    ):
        issues.append("readiness_pricing_expired")
    if admission.verdict != "ready":
        issues.append("readiness_configuration_blocked")
        issues.extend(admission.report.issue_codes)
    return _verdict(
        definition,
        policy_digest=policy_digest,
        admission=admission,
        issue_codes=tuple(dict.fromkeys(issues)),
    )


def require_current_phase32_provider_readiness(
    definition: GraphRunDefinition,
    *,
    store: Phase32ProviderReadinessStore,
    policy: Phase32ProviderReadinessAdmissionPolicy,
    now: datetime | None = None,
) -> Phase32ProviderReadinessAdmission:
    """Return only an effective ready admission; every stale state fails closed."""

    verdict = current_phase32_provider_readiness_verdict(
        definition,
        store=store,
        policy=policy,
        now=now,
    )
    if not verdict.ready:
        raise Phase32ProviderReadinessAdmissionError(verdict)
    return store.read(definition.run_id, verdict.admission_ref)


def _verdict(
    definition: GraphRunDefinition,
    *,
    policy_digest: str,
    admission: Phase32ProviderReadinessAdmission | None = None,
    issue_codes: tuple[str, ...],
) -> Phase32ProviderReadinessAdmissionVerdict:
    return Phase32ProviderReadinessAdmissionVerdict(
        run_id=definition.run_id,
        definition_digest=definition.definition_digest,
        policy_digest=policy_digest,
        admission_ref=admission.admission_ref if admission is not None else "",
        observed_at=admission.observed_at if admission is not None else "",
        expires_at=admission.expires_at if admission is not None else "",
        ready=not issue_codes,
        issue_codes=issue_codes,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Provider readiness admission clock must include a timezone")
    return value.astimezone(timezone.utc)


__all__ = [
    "Phase32ProviderReadinessAdmissionError",
    "Phase32ProviderReadinessAdmissionVerdict",
    "admit_phase32_provider_readiness",
    "continuity_acceptance_provider_readiness_policy",
    "current_phase32_provider_readiness_verdict",
    "require_current_phase32_provider_readiness",
]
