from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.phase32_continuity_acceptance import (
    Phase32ContinuityAdmissionError,
    Phase32ContinuityBudgetLimits,
    PreparedPhase32ContinuityAcceptance,
)
from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
)
from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    Phase32ProviderReadinessAdmissionError,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32DriverError
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32PricingAttestationCommand,
)
from novel_workflow.workflows.definition_schemas import ProviderProfile
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.templates import (
    DEEPSEEK_PRICING_SOURCE_URL,
    DEEPSEEK_PRICING_VERIFIED_AT,
)


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    api = TestClient(create_app())
    preflight = api.app.state.phase32_live_candidate_preflight
    preflight.clock = _ready_clock
    profile = ProviderProfile.model_validate(
        api.app.state.provider_store.read("provider-deepseek-text")
    )
    pricing = profile.model_pricing["deepseek-v4-pro"]
    preflight.attest_pricing(
        Phase32PricingAttestationCommand(
            idempotency_key="continuity-offline-pricing-attestation",
            expected_profile_digest=canonical_digest(profile.model_dump(mode="json")),
            input_usd_per_million_tokens=(
                pricing.input_usd_per_million_tokens or 1.32
            ),
            output_usd_per_million_tokens=(
                pricing.output_usd_per_million_tokens or 3.96
            ),
            source_url=DEEPSEEK_PRICING_SOURCE_URL,
            verified_at=DEEPSEEK_PRICING_VERIFIED_AT,
            estimate_basis_note="Offline continuity conservative pricing.",
            attested_by="offline-continuity-test",
        )
    )
    return api


def _request(key: str) -> CreationPreparationRequest:
    return CreationPreparationRequest.model_validate(
        {
            "selection": {
                "intent": {
                    "creative_intent": "一名档案修复师收到十二封来自未来的失踪报告。",
                    "creation_language": "zh-CN",
                    "creation_kind": "novel",
                    "novel_length_class": "long_novel",
                    "requested_target": 150_000,
                },
                "mode": "existing",
                "workflow_id": "official.long_novel",
            },
            "idempotency_key": key,
        }
    )


def _budget(**updates: object) -> Phase32ContinuityBudgetLimits:
    values: dict[str, object] = {
        "max_cost_usd": 20.0,
        "max_operations": 100,
        "max_total_tokens": 2_000_000,
    }
    values.update(updates)
    return Phase32ContinuityBudgetLimits.model_validate(values)


def _ready_clock() -> datetime:
    return datetime.fromisoformat(DEEPSEEK_PRICING_VERIFIED_AT) + timedelta(minutes=5)


def _authorize_live_candidate(
    api: TestClient,
    prepared: PreparedPhase32ContinuityAcceptance,
) -> None:
    api.app.state.phase32_live_candidate_authorization.authorize_run(
        prepared.definition,
        readiness=prepared.readiness,
        budget=prepared.budget,
    )


class _OfflineTransportFailureGateway:
    def __init__(self) -> None:
        self.requests: list[object] = []
        self.image_requests: list[object] = []

    async def generate(self, request, *, binding):
        self.requests.append(request)
        raise TimeoutError("offline acceptance transport failure")

    async def generate_cover_image(self, request, *, binding):
        self.image_requests.append(request)
        raise AssertionError("continuity acceptance must not call an image Provider")


@pytest.mark.parametrize(
    "field",
    ("max_cost_usd", "max_operations", "max_total_tokens"),
)
def test_private_budget_limits_reject_boolean_values(field: str) -> None:
    with pytest.raises(ValueError, match="cannot be boolean"):
        _budget(**{field: True})


def test_bootstrap_wires_one_private_admission_authority_without_provider_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    authority = api.app.state.phase32_continuity_acceptance

    assert authority.creation is api.app.state.phase32_creation_service
    assert authority.readiness is api.app.state.phase32_provider_readiness_store
    assert authority.budgets is api.app.state.phase32_run_budget_store
    assert authority.budget_admission is api.app.state.phase32_run_budget_admission
    assert authority.live_candidate_authorization is (
        api.app.state.phase32_live_candidate_authorization
    )
    assert api.app.state.phase32_writeback.text_operation_admission is authority
    assert api.app.state.phase32_execution_service.run_admission.__self__ is authority
    assert api.app.state.phase32_provider_operations.root.exists()
    assert list(api.app.state.phase32_provider_operations.root.rglob("*.json")) == []
    assert list(authority.readiness.root.rglob("*.json")) == []
    assert list(authority.budgets.root.rglob("*.json")) == []


def test_private_prepare_freezes_exact_12_readiness_and_immutable_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    authority = api.app.state.phase32_continuity_acceptance
    authority.clock = _ready_clock
    api.app.state.provider_secret_store.set_api_key(
        "provider-deepseek-text",
        "offline-secret-must-not-persist",
    )
    request = _request("continuity-acceptance-private-prepare")

    prepared = authority.prepare(request, budget=_budget())
    replay = authority.prepare(request, budget=_budget())

    profile = prepared.definition.scale_profile.payload
    assert prepared.definition.workflow_id == "official.long_novel"
    assert profile["profile_kind"] == "continuity_acceptance"
    assert profile["rolling_window"] == {
        "min_chapters": 12,
        "max_chapters": 12,
        "min_volumes": 1,
        "max_volumes": 1,
    }
    assert prepared.readiness.verdict == "ready"
    assert prepared.budget == replay.budget
    assert prepared.readiness == replay.readiness
    assert len(authority.readiness.list(prepared.definition.run_id)) == 1
    assert authority.budgets.list_admissions(prepared.definition.run_id) == []
    assert api.app.state.phase32_provider_operations.list(prepared.definition.run_id) == []
    persisted = prepared.readiness.model_dump_json()
    assert "offline-secret-must-not-persist" not in persisted
    assert '"base_url"' not in persisted
    assert '"secret_ref"' not in persisted

    with pytest.raises(Phase32ContinuityAdmissionError, match="immutable"):
        authority.prepare(request, budget=_budget(max_operations=99))


def test_private_prepare_fails_closed_on_current_unready_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    authority = api.app.state.phase32_continuity_acceptance
    authority.clock = lambda: datetime.fromisoformat(
        DEEPSEEK_PRICING_VERIFIED_AT
    ) + timedelta(hours=25)

    with pytest.raises(Phase32ProviderReadinessAdmissionError) as exc:
        authority.prepare(
            _request("continuity-acceptance-blocked-prepare"),
            budget=_budget(),
        )

    assert "secret_missing" in exc.value.verdict.issue_codes
    assert "pricing_verification_stale" in exc.value.verdict.issue_codes
    preparations = api.app.state.phase32_creation_preparations.list()
    assert len(preparations) == 1
    run_id = preparations[0].run_id
    assert authority.readiness.latest(run_id).verdict == "blocked"
    assert authority.budgets.read_authorization(run_id).run_id == run_id
    assert api.app.state.phase32_provider_operations.list(run_id) == []


@pytest.mark.asyncio
async def test_offline_transport_retry_reserves_each_attempt_without_image_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    authority = api.app.state.phase32_continuity_acceptance
    authority.clock = _ready_clock
    api.app.state.provider_secret_store.set_api_key(
        "provider-deepseek-text",
        "offline-only-secret",
    )
    prepared = authority.prepare(
        _request("continuity-acceptance-offline-retry"),
        budget=_budget(),
    )
    _authorize_live_candidate(api, prepared)
    gateway = _OfflineTransportFailureGateway()
    api.app.state.phase32_provider_gateway = gateway
    driver = api.app.state.phase32_execution_service.driver_factory(
        prepared.definition
    )
    assert driver.text_operation_admission is authority
    stage = prepared.definition.stage("brief")
    state = initial_route_run_state(prepared.definition)

    for _attempt in range(2):
        with pytest.raises(Phase32DriverError) as exc:
            await driver.generate_stage(
                definition=prepared.definition,
                state=state,
                stage=stage,
            )
        assert exc.value.code == "provider_transport_failed"

    admissions = authority.budgets.list_admissions(prepared.definition.run_id)
    receipts = api.app.state.phase32_provider_operations.list(
        prepared.definition.run_id
    )
    assert [item.transport_attempt for item in admissions] == [1, 2]
    assert [item.new_logical_operation for item in admissions] == [True, False]
    assert len(receipts) == 1
    assert receipts[0].status == "pending"
    assert receipts[0].transport_attempts == 2
    assert len(gateway.requests) == 2
    assert gateway.image_requests == []
