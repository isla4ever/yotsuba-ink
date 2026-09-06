from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.phase32_continuity_acceptance import (
    Phase32ContinuityBudgetLimits,
)
from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
)
from novel_workflow.orchestration.phase32_live_candidate_preflight import (
    Phase32LiveCandidatePreflightError,
)
from novel_workflow.orchestration.phase32_quality_review import (
    Phase32QualityReviewCommand,
    Phase32QualityReviewService,
)
from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    admit_phase32_provider_readiness,
    continuity_acceptance_provider_readiness_policy,
)
from novel_workflow.orchestration.phase32_release_harness import (
    Phase32ReleaseStopPolicy,
)
from novel_workflow.orchestration.phase32_release_evidence_validation import (
    _unrecovered_contract_rejection_refs,
)
from novel_workflow.providers.phase32_contract import Phase32ProviderResponse
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32PricingAttestationCommand,
)
from novel_workflow.workflows.definition_schemas import ProviderProfile
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.templates import (
    DEEPSEEK_PRICING_SOURCE_URL,
    DEEPSEEK_PRICING_VERIFIED_AT,
)
from tests.test_phase32_driver import (
    _FixtureGateway,
    _rolling_detail_payload_with_chapter_count,
)


_USAGE = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}


def _rejected_receipt(
    *,
    receipt_ref: str = "p32-provider-operation-" + "a" * 64,
    operation_key: str = "run-1:rolling_detail:1",
):
    return SimpleNamespace(
        receipt_ref=receipt_ref,
        operation_key=operation_key,
        stage_id="rolling_detail" if ":writeback:" not in operation_key else "text",
        status="contract_rejected",
        updated_at="2026-09-06T10:00:00+00:00",
    )


def test_release_evidence_accepts_only_durably_recovered_contract_rejections() -> None:
    stage_rejection = _rejected_receipt()
    stage_events = (
        SimpleNamespace(
            type="stage.failed",
            stage_id="rolling_detail",
            sequence=1,
            occurred_at="2026-09-06T10:00:01+00:00",
            payload={"code": "provider_contract_failed"},
        ),
        SimpleNamespace(
            type="candidate.created",
            stage_id="rolling_detail",
            sequence=2,
            occurred_at="2026-09-06T10:00:02+00:00",
            payload={},
        ),
        SimpleNamespace(
            type="artifact.committed",
            stage_id="rolling_detail",
            sequence=3,
            occurred_at="2026-09-06T10:00:03+00:00",
            payload={},
        ),
    )
    assert _unrecovered_contract_rejection_refs(
        rejected_receipts=(stage_rejection,),
        receipts=(stage_rejection,),
        events=stage_events,
        writebacks=(),
    ) == ()
    assert _unrecovered_contract_rejection_refs(
        rejected_receipts=(stage_rejection,),
        receipts=(stage_rejection,),
        events=stage_events[:2],
        writebacks=(),
    ) == (stage_rejection.receipt_ref,)

    writeback_rejection = _rejected_receipt(
        receipt_ref="p32-provider-operation-" + "b" * 64,
        operation_key="run-1:writeback:chapter-1:contract-1",
    )
    success = SimpleNamespace(
        receipt_ref="p32-provider-operation-" + "c" * 64,
        status="succeeded",
    )
    committed_writeback = SimpleNamespace(
        status="committed",
        provider_operation_refs=(
            writeback_rejection.receipt_ref,
            success.receipt_ref,
        ),
    )
    assert _unrecovered_contract_rejection_refs(
        rejected_receipts=(writeback_rejection,),
        receipts=(writeback_rejection, success),
        events=(),
        writebacks=(committed_writeback,),
    ) == ()


class _ReleaseFakeGateway(_FixtureGateway):
    def __init__(self) -> None:
        super().__init__({})
        self.writeback_requests: list[object] = []

    async def generate(self, request, *, binding):
        if request.stage_id == "rolling_detail":
            self.requests.append(request)
            return Phase32ProviderResponse(
                payload=_rolling_detail_payload_with_chapter_count(12),
                usage=_USAGE,
            )
        response = await super().generate(request, binding=binding)
        return response.model_copy(update={"usage": _USAGE})

    async def generate_writeback(self, request, *, binding):
        self.writeback_requests.append(request)
        return Phase32ProviderResponse(payload={"claims": []}, usage=_USAGE)

    async def generate_cover_image(self, request, *, binding):
        self.image_requests.append(request)
        raise AssertionError("Wave 60 continuity rehearsal must not call image Provider")


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


def _budget() -> Phase32ContinuityBudgetLimits:
    return Phase32ContinuityBudgetLimits(
        max_cost_usd=20,
        max_operations=100,
        max_total_tokens=2_000_000,
    )


def _ready_clock() -> datetime:
    return datetime.fromisoformat(DEEPSEEK_PRICING_VERIFIED_AT) + timedelta(minutes=5)


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gateway: _ReleaseFakeGateway | None = None,
) -> TestClient:
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())
    client.app.state.phase32_continuity_acceptance.clock = _ready_clock
    client.app.state.phase32_release_evidence.clock = _ready_clock
    client.app.state.phase32_live_candidate_preflight.clock = _ready_clock
    client.app.state.provider_secret_store.set_api_key(
        "provider-deepseek-text",
        "offline-release-secret",
    )
    preflight = client.app.state.phase32_live_candidate_preflight
    if preflight.store.latest_attestation() is None:
        profile = ProviderProfile.model_validate(
            client.app.state.provider_store.read("provider-deepseek-text")
        )
        pricing = profile.model_pricing["deepseek-v4-pro"]
        preflight.attest_pricing(
            Phase32PricingAttestationCommand(
                idempotency_key="wave60-offline-pricing-attestation",
                expected_profile_digest=canonical_digest(
                    profile.model_dump(mode="json")
                ),
                input_usd_per_million_tokens=(
                    pricing.input_usd_per_million_tokens or 1.32
                ),
                output_usd_per_million_tokens=(
                    pricing.output_usd_per_million_tokens or 3.96
                ),
                source_url=DEEPSEEK_PRICING_SOURCE_URL,
                verified_at=DEEPSEEK_PRICING_VERIFIED_AT,
                estimate_basis_note="Offline release fixture conservative pricing.",
                attested_by="offline-release-test",
            )
        )
    if gateway is not None:
        client.app.state.phase32_provider_gateway = gateway
        client.app.state.phase32_writeback.gateway = gateway
    return client


def test_transport_attempt_ledger_preserves_failed_attempt_before_success(
    tmp_path: Path,
) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "operations")
    operation_key = "run-1:text:chapter-01"
    signature = provider_request_signature(
        {"run_id": "run-1", "operation_key": operation_key, "stage_id": "text"}
    )
    store.begin(
        run_id="run-1",
        operation_key=operation_key,
        stage_id="text",
        request_signature=signature,
    )
    first = store.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-secret-a",
    )
    store.release_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-secret-a",
        claimed_transport_attempt=first.transport_attempts,
        diagnostic={"code": "provider_timeout"},
    )
    second = store.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-secret-b",
    )
    returned = store.record_return(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        raw_provider_payload={"content": "fixture"},
        usage=_USAGE,
        lease_owner="worker-secret-b",
        claimed_transport_attempt=second.transport_attempts,
    )

    assert [event.event_kind for event in returned.transport_attempt_events] == [
        "claimed",
        "transport_failed",
        "claimed",
        "provider_returned",
    ]
    assert returned.transport_attempt_events[1].error_code == "provider_timeout"
    serialized = returned.model_dump_json()
    assert "worker-secret-a" not in serialized
    assert "worker-secret-b" not in serialized
    assert all(event.elapsed_ms is not None for event in returned.transport_attempt_events[1::2])


def test_attempt_ledger_rejects_a_rehashed_inconsistent_duration(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "operations")
    operation_key = "run-1:text:chapter-02"
    signature = provider_request_signature(
        {"run_id": "run-1", "operation_key": operation_key, "stage_id": "text"}
    )
    receipt = store.begin(
        run_id="run-1",
        operation_key=operation_key,
        stage_id="text",
        request_signature=signature,
    )
    claimed = store.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-a",
    )
    returned = store.record_return(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        raw_provider_payload={"content": "fixture"},
        usage=_USAGE,
        lease_owner="worker-a",
        claimed_transport_attempt=claimed.transport_attempts,
    )
    payload = returned.model_dump(mode="json")
    event = dict(payload["transport_attempt_events"][-1])
    event["elapsed_ms"] += 1
    event["event_ref"] = "p32-transport-attempt-event-" + canonical_digest(
        {key: value for key, value in event.items() if key != "event_ref"}
    )
    payload["transport_attempt_events"][-1] = event
    path = store.root / "run-1" / f"{receipt.receipt_ref}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed Phase 32 Provider operation receipt"):
        store.read("run-1", operation_key)


def test_bootstrap_wires_private_release_harness_to_production_authorities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    harness = client.app.state.phase32_release_harness

    assert harness.continuity is client.app.state.phase32_continuity_acceptance
    assert harness.execution is client.app.state.phase32_execution_service
    assert harness.provider_operations is client.app.state.phase32_provider_operations
    assert harness.evidence is client.app.state.phase32_release_evidence
    assert harness.live_candidate_authorization is (
        client.app.state.phase32_live_candidate_authorization
    )
    assert client.app.state.phase32_release_evidence.bundles is (
        client.app.state.phase32_release_evidence_store
    )


def test_incomplete_bundle_is_redacted_persisted_and_cold_verifiable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    prepared = client.app.state.phase32_release_harness.prepare(
        _request("wave60-incomplete-bundle"),
        budget=_budget(),
    )
    operation_key = f"{prepared.definition.run_id}:brief:legacy-receipt"
    signature = provider_request_signature(
        {
            "run_id": prepared.definition.run_id,
            "operation_key": operation_key,
            "stage_id": "brief",
        }
    )
    client.app.state.phase32_provider_operations.begin(
        run_id=prepared.definition.run_id,
        operation_key=operation_key,
        stage_id="brief",
        request_signature=signature,
    )

    bundle = client.app.state.phase32_release_evidence.export(
        prepared.definition.run_id
    )
    verification = client.app.state.phase32_release_evidence.verify(
        prepared.definition.run_id,
        bundle.bundle_ref,
    )

    assert bundle.summary.verdict == "blocked"
    assert "text_progress_missing" in bundle.summary.issue_codes
    assert "provider_input_missing" in bundle.summary.issue_codes
    assert "provider_execution_identity_mismatch" in bundle.summary.issue_codes
    assert "receipt_budget_identity_mismatch" in bundle.summary.issue_codes
    assert "transport_attempt_evidence_incomplete" in bundle.summary.issue_codes
    assert verification.issue_codes == bundle.summary.issue_codes
    persisted = (
        client.app.state.phase32_release_evidence_store.root
        / prepared.definition.run_id
        / f"{bundle.bundle_ref}.json"
    ).read_text(encoding="utf-8")
    assert "offline-release-secret" not in persisted
    for forbidden in ('"base_url"', '"source_url"', '"rendered_prompt"', '"payload"'):
        assert forbidden not in persisted
    assert json.loads(persisted)["bundle_ref"] == bundle.bundle_ref

    admit_phase32_provider_readiness(
        prepared.definition,
        store=client.app.state.phase32_provider_readiness_store,
        policy=continuity_acceptance_provider_readiness_policy(),
        secret_resolver=client.app.state.provider_secret_store.get_api_key,
        now=_ready_clock() + timedelta(minutes=1),
    )
    drifted = client.app.state.phase32_release_evidence.verify(
        prepared.definition.run_id,
        bundle.bundle_ref,
    )
    assert "evidence_authority_drift" in drifted.issue_codes


@pytest.mark.asyncio
async def test_release_harness_defaults_to_operator_decision_not_auto_accept(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _ReleaseFakeGateway()
    client = _client(tmp_path, monkeypatch, gateway)
    prepared = client.app.state.phase32_release_harness.prepare(
        _request("wave60-operator-stop"),
        budget=_budget(),
    )
    authorization = (
        client.app.state.phase32_live_candidate_preflight_store.latest_authorization(
            prepared.definition.run_id
        )
    )

    assert authorization is not None
    assert authorization.definition_digest == prepared.definition.definition_digest
    assert authorization.readiness_admission_ref == prepared.readiness.admission_ref
    assert authorization.budget_authorization_ref == prepared.budget.authorization_ref
    assert authorization.billable_call_count_at_issue == 0

    outcome = await client.app.state.phase32_release_harness.advance(
        prepared.definition.run_id,
        stop_policy=Phase32ReleaseStopPolicy(),
    )

    assert outcome.stop_reason == "awaiting_operator"
    assert outcome.record.read_model.pending_decisions[0].stage_id == "brief"
    assert len(gateway.requests) == 1
    assert gateway.image_requests == []


@pytest.mark.asyncio
async def test_release_harness_blocks_profile_drift_before_provider_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _ReleaseFakeGateway()
    client = _client(tmp_path, monkeypatch, gateway)
    prepared = client.app.state.phase32_release_harness.prepare(
        _request("wave61-profile-drift-stop"),
        budget=_budget(),
    )
    profile = client.app.state.provider_store.read("provider-deepseek-text")
    profile["name"] = "Concurrent operator edit"
    client.app.state.provider_store.write("provider-deepseek-text", profile)

    with pytest.raises(Phase32LiveCandidatePreflightError, match="drifted"):
        await client.app.state.phase32_release_harness.advance(
            prepared.definition.run_id,
            stop_policy=Phase32ReleaseStopPolicy(),
        )

    assert gateway.requests == []
    assert gateway.writeback_requests == []
    assert gateway.image_requests == []
    assert client.app.state.phase32_provider_operations.list(
        prepared.definition.run_id
    ) == []


@pytest.mark.asyncio
async def test_fake_exact12_rehearsal_survives_two_cold_restarts_and_verifies_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateways: list[_ReleaseFakeGateway] = []

    def reopen() -> TestClient:
        gateway = _ReleaseFakeGateway()
        gateways.append(gateway)
        return _client(tmp_path, monkeypatch, gateway)

    client = reopen()
    prepared = client.app.state.phase32_release_harness.prepare(
        _request("wave60-exact12-rehearsal"),
        budget=_budget(),
    )
    run_id = prepared.definition.run_id
    planning_stages = (
        "brief",
        "book_architecture",
        "cast",
        "volumes",
        "rolling_detail",
    )
    first = await client.app.state.phase32_release_harness.advance(
        run_id,
        stop_policy=Phase32ReleaseStopPolicy(auto_accept_stages=planning_stages),
    )
    assert first.stop_reason == "awaiting_operator"
    assert first.record.state.active_unit_ref == "chapter-01"

    prefixes: list[tuple[str, ...]] = []
    for expected_count in (4, 8):
        client.close()
        client = reopen()
        partial = await client.app.state.phase32_release_harness.advance(
            run_id,
            stop_policy=Phase32ReleaseStopPolicy(
                max_graph_transitions=4,
                auto_accept_stages=(*planning_stages, "text"),
            ),
        )
        assert partial.stop_reason == "transition_limit"
        progress = partial.record.state.sequential_progress("text")
        assert progress is not None
        assert len(progress.committed_artifact_refs) == expected_count
        prefixes.append(tuple(progress.committed_artifact_refs.values()))

    client.close()
    client = reopen()
    terminal = await client.app.state.phase32_release_harness.advance(
        run_id,
        stop_policy=Phase32ReleaseStopPolicy(
            auto_accept_stages=(*planning_stages, "text", "cover"),
        ),
    )
    assert terminal.stop_reason == "image_deferred"
    progress = terminal.record.state.sequential_progress("text")
    assert progress is not None and progress.complete
    assert tuple(progress.committed_artifact_refs.values())[:4] == prefixes[0]
    assert tuple(progress.committed_artifact_refs.values())[:8] == prefixes[1]

    quality = Phase32QualityReviewService(
        client.app.state.phase32_run_repository,
        client.app.state.phase32_artifact_store,
        client.app.state.phase32_quality_reports,
        clock=lambda: _ready_clock().isoformat(),
    )
    quality.record_review(
        run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="offline-fixture-reader",
            reviewer_role="cold_reader",
            outcome="continue_reading",
            summary="离线 Fake exact-12 仅验证系统连续性，不代表真实文学质量。",
        ),
    )
    client.app.state.phase32_release_evidence.clock = _ready_clock
    bundle = client.app.state.phase32_release_harness.finalize_evidence(run_id)

    assert bundle.summary.verdict == "ready"
    assert bundle.summary.committed_chapter_count == 12
    assert bundle.summary.committed_writeback_count == 12
    assert bundle.summary.pending_writeback_count == 0
    assert bundle.summary.pending_provider_operation_count == 0
    assert bundle.summary.image_provider_operation_count == 0
    assert bundle.summary.collaboration_provider_operation_count == 0
    assert bundle.summary.terminal_status == "image_deferred"
    assert bundle.summary.terminal_event_count == 1
    assert bundle.summary.transport_attempt_count == bundle.summary.budget_admission_count
    assert sum(len(gateway.image_requests) for gateway in gateways) == 0
    assert sum(len(gateway.requests) for gateway in gateways) == 18
    assert sum(len(gateway.writeback_requests) for gateway in gateways) == 12

    client.close()
    cold = reopen()
    cold.app.state.phase32_release_evidence.clock = _ready_clock
    verified = cold.app.state.phase32_release_evidence.require_valid(
        run_id,
        bundle.bundle_ref,
    )
    assert verified.bundle_ref == bundle.bundle_ref

    cold_quality = Phase32QualityReviewService(
        cold.app.state.phase32_run_repository,
        cold.app.state.phase32_artifact_store,
        cold.app.state.phase32_quality_reports,
        clock=lambda: _ready_clock().isoformat(),
    )
    cold_quality.record_review(
        run_id,
        Phase32QualityReviewCommand(
            reviewer_ref="offline-fixture-revision-reader",
            reviewer_role="cold_reader",
            outcome="revision_recommended",
            summary="返工建议必须阻断 release-ready 结论。",
        ),
    )
    blocked = cold.app.state.phase32_release_evidence.export(run_id)
    assert blocked.summary.verdict == "blocked"
    assert "continuity_quality_report_invalid" in blocked.summary.issue_codes
