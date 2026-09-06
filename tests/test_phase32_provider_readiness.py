from __future__ import annotations

from datetime import datetime

import pytest

from novel_workflow.orchestration.phase32_provider_readiness import (
    Phase32ProviderReadinessError,
    ensure_phase32_provider_ready,
    phase32_provider_readiness_report,
)
from novel_workflow.workflows.route_specs import (
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)
from tests.test_phase32_route_graph import _definition


FRESH_NOW = datetime.fromisoformat("2026-08-23T13:00:00+08:00")


def test_configuration_only_report_is_redacted_and_makes_no_provider_call() -> None:
    definition = _definition(
        SCREENPLAY_SAMPLE_ROUTE,
        workflow_id="official.screenplay_sample",
    )
    resolved: list[str] = []

    def resolve_secret(secret_ref: str) -> str:
        resolved.append(secret_ref)
        return "private-provider-key"

    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=resolve_secret,
        now=FRESH_NOW,
    )

    assert report.ready is True
    assert len(resolved) == len(definition.provider_bindings_by_stage)
    assert all(check.secret_present for check in report.stages)
    assert all(check.pricing_fresh for check in report.stages)
    serialized = report.model_dump_json()
    assert "private-provider-key" not in serialized
    assert "phase32-fixture.invalid" not in serialized
    assert "secret_ref" not in serialized
    assert "source_url" not in serialized


def test_report_blocks_missing_secret_stale_pricing_and_wrong_model() -> None:
    definition = _definition(
        SCREENPLAY_SAMPLE_ROUTE,
        workflow_id="official.screenplay_sample",
    )

    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=lambda _ref: None,
        now=datetime.fromisoformat("2026-09-05T12:00:00+08:00"),
        required_model_id="deepseek-v4-flash",
    )

    assert report.ready is False
    assert set(report.issue_codes) >= {
        "secret_missing",
        "pricing_verification_stale",
        "required_model_mismatch",
    }
    with pytest.raises(Phase32ProviderReadinessError) as captured:
        ensure_phase32_provider_ready(
            definition,
            secret_resolver=lambda _ref: None,
            now=datetime.fromisoformat("2026-09-05T12:00:00+08:00"),
            required_model_id="deepseek-v4-flash",
        )
    assert captured.value.report == report


def test_text_only_gate_rejects_a_frozen_image_execution() -> None:
    # A non-canonical fixture workflow retains the image binding and is useful
    # for proving that the text-only acceptance gate fails closed.
    definition = _definition(SHORT_NOVEL_ROUTE)

    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=lambda _ref: "fixture-secret",
        now=FRESH_NOW,
        require_canonical_workflow=False,
        require_text_only=True,
    )

    assert report.ready is False
    cover = next(check for check in report.stages if check.stage_id == "cover")
    assert cover.image_execution_absent is False
    assert "image_execution_present" in cover.issue_codes


def test_required_private_profile_kind_is_explicitly_checked() -> None:
    definition = _definition(
        SHORT_NOVEL_ROUTE,
        workflow_id="official.short_novel",
    )

    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=lambda _ref: "fixture-secret",
        now=FRESH_NOW,
        required_profile_kind="continuity_acceptance",
    )

    assert report.ready is False
    assert "scale_profile_kind_mismatch" in report.issue_codes


def test_secret_resolver_failure_is_redacted_and_fails_closed() -> None:
    definition = _definition(
        SCREENPLAY_SAMPLE_ROUTE,
        workflow_id="official.screenplay_sample",
    )

    def fail_secret_resolution(_ref: str) -> str:
        raise RuntimeError("private-key-material-must-not-escape")

    report = phase32_provider_readiness_report(
        definition,
        secret_resolver=fail_secret_resolution,
        now=FRESH_NOW,
    )

    assert report.ready is False
    assert "secret_resolution_failed" in report.issue_codes
    assert "private-key-material-must-not-escape" not in report.model_dump_json()
