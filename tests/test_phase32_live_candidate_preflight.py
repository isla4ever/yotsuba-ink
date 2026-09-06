from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.phase32_live_candidate_preflight import (
    Phase32LiveCandidatePreflightError,
    Phase32LiveCandidatePreflightService,
)
from novel_workflow.storage.phase32_live_candidate_preflight_store import (
    Phase32LiveCandidatePreflightStore,
)
from novel_workflow.storage.provider_profile_store import (
    ProviderProfileStore,
    ProviderProfileStoreConflict,
)
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32PricingAttestationCommand,
)
from novel_workflow.workflows.definition_schemas import ProviderProfile
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.templates import (
    DEEPSEEK_PRICING_SOURCE_URL,
    default_provider_profiles,
)


NOW = datetime.fromisoformat("2026-09-05T12:00:00+00:00")


def _profile() -> ProviderProfile:
    return default_provider_profiles()[0]


def _profile_digest(profile: ProviderProfile) -> str:
    return canonical_digest(profile.model_dump(mode="json"))


def _command(
    profile: ProviderProfile,
    *,
    idempotency_key: str = "wave61-pricing-refresh",
    input_rate: float = 1.32,
) -> Phase32PricingAttestationCommand:
    return Phase32PricingAttestationCommand(
        idempotency_key=idempotency_key,
        expected_profile_digest=_profile_digest(profile),
        input_usd_per_million_tokens=input_rate,
        output_usd_per_million_tokens=3.96,
        source_url=DEEPSEEK_PRICING_SOURCE_URL,
        verified_at=(NOW - timedelta(hours=1)).isoformat(),
        estimate_basis_note="按官方 peak cache-miss 输入与输出费率冻结保守上界。",
        attested_by="operator-test",
    )


def _service(
    tmp_path: Path,
    *,
    secret: str | None = "configured-secret",
) -> tuple[
    Phase32LiveCandidatePreflightService,
    ProviderProfileStore,
    Phase32LiveCandidatePreflightStore,
]:
    profiles = ProviderProfileStore(tmp_path / "profiles.sqlite3")
    profiles.write(_profile().id, _profile().model_dump(mode="json"))
    audit = Phase32LiveCandidatePreflightStore(tmp_path / "preflight")
    service = Phase32LiveCandidatePreflightService(
        profiles=profiles,
        store=audit,
        secret_resolver=lambda _provider_id: secret,
        clock=lambda: NOW,
    )
    return service, profiles, audit


def test_pricing_attestation_refreshes_by_cas_and_emits_zero_call_report(
    tmp_path: Path,
) -> None:
    service, profiles, audit = _service(tmp_path)
    command = _command(_profile())

    attestation = service.attest_pricing(command)
    report = service.assess_environment()
    stored = ProviderProfile.model_validate(profiles.read(_profile().id))
    pricing = stored.model_pricing["deepseek-v4-pro"]

    assert pricing.verified_at == command.verified_at
    assert pricing.input_usd_per_million_tokens == 1.32
    assert pricing.output_usd_per_million_tokens == 3.96
    assert attestation.profile_before_digest == command.expected_profile_digest
    assert attestation.profile_after_digest == _profile_digest(stored)
    assert report.verdict == "ready_for_budget_authorization"
    assert report.next_gate == "explicit_run_budget"
    assert report.billable_call_count == 0
    assert report.pricing_attestation_ref == attestation.attestation_ref
    assert report.pricing_age_hours == 1
    assert report.secret_configured is True
    assert report.issue_codes == ()
    assert len(audit.list_reports()) == 1
    serialized = report.model_dump_json()
    assert "configured-secret" not in serialized
    assert "source_url" not in serialized
    assert "api.deepseek.com" not in serialized


def test_provider_profile_store_cas_rejects_a_changed_payload(tmp_path: Path) -> None:
    profiles = ProviderProfileStore(tmp_path / "profiles.sqlite3")
    expected = _profile().model_dump(mode="json")
    profiles.write(_profile().id, expected)
    changed = {**expected, "name": "Operator changed this profile"}
    profiles.write(_profile().id, changed)

    with pytest.raises(ProviderProfileStoreConflict, match="changed"):
        profiles.write_if_current(
            _profile().id,
            expected=expected,
            data={**expected, "name": "Stale pricing writer"},
        )

    assert profiles.read(_profile().id) == changed


def test_pricing_attestation_replays_after_restart_and_rejects_drift(
    tmp_path: Path,
) -> None:
    service, profiles, audit = _service(tmp_path)
    command = _command(_profile())
    first = service.attest_pricing(command)
    restarted = Phase32LiveCandidatePreflightService(
        profiles=ProviderProfileStore(profiles.path),
        store=Phase32LiveCandidatePreflightStore(audit.root),
        secret_resolver=lambda _provider_id: "configured-secret",
        clock=lambda: NOW,
    )

    assert restarted.attest_pricing(command) == first
    late_replay = Phase32LiveCandidatePreflightService(
        profiles=ProviderProfileStore(profiles.path),
        store=Phase32LiveCandidatePreflightStore(audit.root),
        secret_resolver=lambda _provider_id: "configured-secret",
        clock=lambda: NOW + timedelta(hours=25),
    )
    assert late_replay.attest_pricing(command) == first
    assert late_replay.assess_environment().issue_codes == (
        "pricing_verification_stale",
    )
    with pytest.raises(Phase32LiveCandidatePreflightError, match="another command"):
        restarted.attest_pricing(
            _command(_profile(), input_rate=1.33)
        )
    with pytest.raises(Phase32LiveCandidatePreflightError, match="changed"):
        restarted.attest_pricing(
            _command(
                _profile(),
                idempotency_key="wave61-stale-cas",
            )
        )


def test_attestation_intent_recovers_if_catalog_write_was_interrupted(
    tmp_path: Path,
) -> None:
    service, profiles, audit = _service(tmp_path)
    command = _command(_profile())
    original_write = profiles.write_if_current
    failed = False

    def fail_once(
        item_id: str,
        *,
        expected: dict[str, object],
        data: dict[str, object],
    ):
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("simulated profile write interruption")
        return original_write(item_id, expected=expected, data=data)

    profiles.write_if_current = fail_once  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="interruption"):
        service.attest_pricing(command)
    assert audit.find_attestation(command.idempotency_key) is not None
    assert _profile_digest(
        ProviderProfile.model_validate(profiles.read(_profile().id))
    ) == command.expected_profile_digest

    blocked = Phase32LiveCandidatePreflightService(
        profiles=ProviderProfileStore(profiles.path),
        store=Phase32LiveCandidatePreflightStore(audit.root),
        secret_resolver=lambda _provider_id: "configured-secret",
        clock=lambda: NOW,
    )
    with pytest.raises(Phase32LiveCandidatePreflightError, match="requires recovery"):
        blocked.attest_pricing(
            _command(
                _profile(),
                idempotency_key="wave61-competing-refresh",
            )
        )

    recovered = Phase32LiveCandidatePreflightService(
        profiles=ProviderProfileStore(profiles.path),
        store=Phase32LiveCandidatePreflightStore(audit.root),
        secret_resolver=lambda _provider_id: "configured-secret",
        clock=lambda: NOW,
    ).attest_pricing(command)
    current = ProviderProfile.model_validate(profiles.read(_profile().id))
    assert _profile_digest(current) == recovered.profile_after_digest


def test_pending_attestation_blocks_an_unexplained_third_profile_state(
    tmp_path: Path,
) -> None:
    service, profiles, audit = _service(tmp_path)
    command = _command(_profile())

    def interrupt_catalog_write(
        _item_id: str,
        *,
        expected: dict[str, object],
        data: dict[str, object],
    ) -> None:
        del expected, data
        raise RuntimeError("simulated profile write interruption")

    profiles.write_if_current = interrupt_catalog_write  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="interruption"):
        service.attest_pricing(command)

    drifted_payload = profiles.read(_profile().id)
    drifted_payload["name"] = "Unexpected concurrent edit"
    ProviderProfileStore(profiles.path).write(_profile().id, drifted_payload)
    drifted = ProviderProfile.model_validate(drifted_payload)
    restarted = Phase32LiveCandidatePreflightService(
        profiles=ProviderProfileStore(profiles.path),
        store=Phase32LiveCandidatePreflightStore(audit.root),
        secret_resolver=lambda _provider_id: "configured-secret",
        clock=lambda: NOW,
    )

    with pytest.raises(Phase32LiveCandidatePreflightError, match="diverged"):
        restarted.attest_pricing(
            _command(
                drifted,
                idempotency_key="wave61-third-state-refresh",
            )
        )


def test_environment_report_blocks_stale_unattested_or_missing_secret(
    tmp_path: Path,
) -> None:
    service, _profiles, audit = _service(tmp_path, secret=None)

    report = service.assess_environment()

    assert report.verdict == "blocked"
    assert report.next_gate == "refresh_environment"
    assert report.billable_call_count == 0
    assert set(report.issue_codes) == {
        "pricing_verification_stale",
        "pricing_attestation_missing",
        "provider_secret_missing",
    }
    assert audit.list_reports() == (report,)


def test_bootstrap_wires_private_preflight_without_public_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app()) as client:
        service = client.app.state.phase32_live_candidate_preflight

        assert service.profiles is client.app.state.provider_store
        assert service.store is client.app.state.phase32_live_candidate_preflight_store
        authorization = client.app.state.phase32_live_candidate_authorization
        assert authorization.preflight is service
        assert authorization.store is service.store
        assert (
            client.app.state.phase32_release_harness.live_candidate_authorization
            is authorization
        )
        assert client.app.state.phase32_provider_operations.list("missing-run") == []
