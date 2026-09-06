from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from novel_workflow.providers.usage import freeze_phase32_pricing_snapshot
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationAttemptFenceConflict,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.storage.phase32_run_budget_store import (
    Phase32RunBudgetStore,
    Phase32RunBudgetStoreError,
)
from novel_workflow.usage.phase32_run_budget import (
    Phase32RunBudgetAdmissionDenied,
    Phase32RunBudgetAdmissionService,
    Phase32RunBudgetConflict,
    freeze_phase32_run_budget_authorization,
)


_TIME = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)
_DEFINITION_DIGEST = "d" * 64


def _signature(operation_key: str) -> str:
    return provider_request_signature(
        {"run_id": "run-1", "operation_key": operation_key, "stage_id": "text"}
    )


def _pricing() -> dict[str, object]:
    return freeze_phase32_pricing_snapshot(
        provider_profile_id="provider-test",
        provider_template_id="template-test",
        model_id="model-test",
        input_usd_per_million_tokens=1.0,
        output_usd_per_million_tokens=1.0,
        source_url="https://provider.example/pricing",
        verified_at="2026-09-05T07:00:00+00:00",
        estimate_basis="conservative_upper_bound",
        estimate_basis_note="Deterministic test rate.",
    )


def _stores(
    tmp_path: Path,
    *,
    max_cost_usd: float = 0.4,
    max_operations: int = 4,
    max_total_tokens: int = 400_000,
    max_transport_attempts: int = 3,
) -> tuple[Phase32RunBudgetStore, Phase32ProviderOperationStore]:
    budgets = Phase32RunBudgetStore(tmp_path / "budgets")
    budgets.save_authorization(
        freeze_phase32_run_budget_authorization(
            run_id="run-1",
            definition_digest="d" * 64,
            max_cost_usd=max_cost_usd,
            max_operations=max_operations,
            max_total_tokens=max_total_tokens,
            max_transport_attempts=max_transport_attempts,
            authorized_at="2026-09-05T08:00:00+00:00",
        )
    )
    return budgets, Phase32ProviderOperationStore(tmp_path / "operations")


def _service(
    budgets: Phase32RunBudgetStore,
    operations: Phase32ProviderOperationStore,
) -> Phase32RunBudgetAdmissionService:
    return Phase32RunBudgetAdmissionService(
        budgets,
        operations,
        clock=lambda: _TIME,
    )


def _begin(operations: Phase32ProviderOperationStore, operation_key: str) -> str:
    signature = _signature(operation_key)
    operations.begin(
        run_id="run-1",
        operation_key=operation_key,
        stage_id="text",
        request_signature=signature,
    )
    return signature


def _claim(
    budgets: Phase32RunBudgetStore,
    operations: Phase32ProviderOperationStore,
    operation_key: str,
    *,
    lease_owner: str,
    max_transport_attempts: int = 3,
    lease_seconds: int = 120,
    now: datetime | None = None,
):
    next_attempt = operations.read("run-1", operation_key).transport_attempts + 1
    admission = budgets.read_admission("run-1", operation_key, next_attempt)
    return operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=_signature(operation_key),
        lease_owner=lease_owner,
        admission_fence=admission,
        lease_seconds=lease_seconds,
        max_transport_attempts=max_transport_attempts,
        now=now,
    )


def _return(
    budgets: Phase32RunBudgetStore,
    operations: Phase32ProviderOperationStore,
    operation_key: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    lease_owner = f"test-owner-{operation_key}"
    claimed = _claim(
        budgets,
        operations,
        operation_key,
        lease_owner=lease_owner,
    )
    operations.record_return(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=_signature(operation_key),
        raw_provider_payload={"content": "durable test response"},
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
        pricing_snapshot=_pricing(),
        lease_owner=lease_owner,
        claimed_transport_attempt=claimed.transport_attempts,
    )


def test_authorization_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    budgets, _ = _stores(tmp_path)
    authorization = budgets.read_authorization("run-1")

    assert authorization.authorization_ref.startswith("p32-run-budget-")
    assert authorization.currency == "USD"
    assert authorization.max_cost_usd == 0.4
    assert authorization.max_transport_attempts == 3
    assert authorization.definition_digest == "d" * 64
    assert budgets.save_authorization(authorization) == authorization

    changed = freeze_phase32_run_budget_authorization(
        run_id="run-1",
        definition_digest="d" * 64,
        max_cost_usd=0.5,
        max_operations=4,
        max_total_tokens=400_000,
        authorized_at="2026-09-05T08:00:00+00:00",
    )
    with pytest.raises(Phase32RunBudgetStoreError, match="immutable"):
        budgets.save_authorization(changed)

    path = tmp_path / "budgets" / "run-1" / "authorization.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["max_operations"] = 99
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(Phase32RunBudgetStoreError, match="Malformed"):
        budgets.read_authorization("run-1")


def test_admission_uses_actual_returned_usage_instead_of_old_reserve(
    tmp_path: Path,
) -> None:
    budgets, operations = _stores(tmp_path)
    service = _service(budgets, operations)
    first_key = "run-1:text:chapter-01:generate"
    first = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=first_key,
        request_signature=_begin(operations, first_key),
        reserved_total_tokens=100_000,
        reserved_cost_usd=0.1,
    )
    assert first.replay is False
    assert first.admission.allocated_before.operations == 0
    assert first.admission.projected_after.total_tokens == 100_000

    _return(
        budgets,
        operations,
        first_key,
        prompt_tokens=20_000,
        completion_tokens=30_000,
    )
    second_key = "run-1:text:chapter-02:generate"
    second = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=second_key,
        request_signature=_begin(operations, second_key),
        reserved_total_tokens=80_000,
        reserved_cost_usd=0.08,
    )

    assert second.admission.allocated_before.operations == 1
    assert second.admission.allocated_before.total_tokens == 50_000
    assert second.admission.allocated_before.estimated_cost_usd == 0.05
    assert second.admission.projected_after.total_tokens == 130_000
    assert second.admission.projected_after.estimated_cost_usd == 0.13


@pytest.mark.parametrize(
    ("limits", "reservation", "issue_code"),
    [
        (
            {"max_operations": 1, "max_total_tokens": 1_000, "max_cost_usd": 1.0},
            {"reserved_total_tokens": 10, "reserved_cost_usd": 0.01},
            "operation_limit_exceeded",
        ),
        (
            {"max_operations": 3, "max_total_tokens": 100, "max_cost_usd": 1.0},
            {"reserved_total_tokens": 101, "reserved_cost_usd": 0.01},
            "token_limit_exceeded",
        ),
        (
            {"max_operations": 3, "max_total_tokens": 1_000, "max_cost_usd": 0.1},
            {"reserved_total_tokens": 10, "reserved_cost_usd": 0.11},
            "cost_limit_exceeded",
        ),
    ],
)
def test_operation_token_and_usd_limits_fail_before_admission(
    tmp_path: Path,
    limits: dict[str, int | float],
    reservation: dict[str, int | float],
    issue_code: str,
) -> None:
    budgets, operations = _stores(tmp_path, **limits)  # type: ignore[arg-type]
    service = _service(budgets, operations)
    if issue_code == "operation_limit_exceeded":
        first_key = "run-1:text:chapter-01:generate"
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=first_key,
            request_signature=_begin(operations, first_key),
            reserved_total_tokens=10,
            reserved_cost_usd=0.01,
        )
    operation_key = "run-1:text:chapter-02:generate"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=_begin(operations, operation_key),
            reserved_total_tokens=int(reservation["reserved_total_tokens"]),
            reserved_cost_usd=float(reservation["reserved_cost_usd"]),
        )

    assert issue_code in exc.value.issue_codes
    assert budgets.find_admission("run-1", operation_key) is None


@pytest.mark.parametrize(
    ("tokens", "cost", "issue_code"),
    [
        (None, 0.01, "reservation_total_tokens_unknown"),
        (100, None, "reservation_cost_unknown"),
        (100, 0.0, "reservation_cost_unknown"),
    ],
)
def test_unknown_or_non_conservative_reservation_fails_closed(
    tmp_path: Path,
    tokens: int | None,
    cost: float | None,
    issue_code: str,
) -> None:
    budgets, operations = _stores(tmp_path)
    service = _service(budgets, operations)
    operation_key = "run-1:text:chapter-01:generate"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=_signature(operation_key),
            reserved_total_tokens=tokens,
            reserved_cost_usd=cost,
        )
    assert issue_code in exc.value.issue_codes


def test_admission_rejects_another_frozen_definition(tmp_path: Path) -> None:
    budgets, operations = _stores(tmp_path)
    operation_key = "run-1:text:chapter-01:generate"

    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        _service(budgets, operations).admit(
            run_id="run-1",
            definition_digest="e" * 64,
            operation_key=operation_key,
            request_signature=_begin(operations, operation_key),
            reserved_total_tokens=100,
            reserved_cost_usd=0.01,
        )
    assert exc.value.issue_codes == ("budget_definition_mismatch",)
    assert budgets.list_admissions("run-1") == []


def test_unknown_historical_usage_or_cost_blocks_the_next_operation(
    tmp_path: Path,
) -> None:
    budgets, operations = _stores(tmp_path)
    service = _service(budgets, operations)

    unknown_usage_key = "run-1:text:unknown-usage"
    unknown_usage_signature = _begin(operations, unknown_usage_key)
    service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=unknown_usage_key,
        request_signature=unknown_usage_signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.01,
    )
    unknown_usage_claim = _claim(
        budgets,
        operations,
        unknown_usage_key,
        lease_owner="unknown-usage-owner",
    )
    fixed_pricing = freeze_phase32_pricing_snapshot(
        provider_profile_id="provider-test",
        provider_template_id="template-test",
        model_id="model-test",
        fixed_output_usd=0.01,
        source_url="https://provider.example/pricing",
        verified_at="2026-09-05T07:00:00+00:00",
        estimate_basis="fixed_output_estimate",
        estimate_basis_note="Deterministic fixed test price.",
    )
    operations.record_return(
        run_id="run-1",
        operation_key=unknown_usage_key,
        request_signature=_signature(unknown_usage_key),
        raw_provider_payload={"content": "response without usage"},
        usage={},
        pricing_snapshot=fixed_pricing,
        lease_owner="unknown-usage-owner",
        claimed_transport_attempt=unknown_usage_claim.transport_attempts,
    )
    next_key = "run-1:text:after-unknown-usage"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as usage_exc:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=next_key,
            request_signature=_begin(operations, next_key),
            reserved_total_tokens=100,
            reserved_cost_usd=0.01,
        )
    assert "receipt_token_usage_incomplete" in usage_exc.value.issue_codes

    other_budgets, other_operations = _stores(tmp_path / "unknown-cost")
    other_service = _service(other_budgets, other_operations)
    unknown_cost_key = "run-1:text:unknown-cost"
    unknown_cost_signature = _begin(other_operations, unknown_cost_key)
    other_service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=unknown_cost_key,
        request_signature=unknown_cost_signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.01,
    )
    unknown_cost_claim = _claim(
        other_budgets,
        other_operations,
        unknown_cost_key,
        lease_owner="unknown-cost-owner",
    )
    other_operations.record_return(
        run_id="run-1",
        operation_key=unknown_cost_key,
        request_signature=_signature(unknown_cost_key),
        raw_provider_payload={"content": "response without pricing"},
        usage={"total_tokens": 10},
        lease_owner="unknown-cost-owner",
        claimed_transport_attempt=unknown_cost_claim.transport_attempts,
    )
    other_next_key = "run-1:text:after-unknown-cost"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as cost_exc:
        other_service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=other_next_key,
            request_signature=_begin(other_operations, other_next_key),
            reserved_total_tokens=100,
            reserved_cost_usd=0.01,
        )
    assert "receipt_cost_unknown" in cost_exc.value.issue_codes


def test_same_operation_replay_never_allocates_twice(tmp_path: Path) -> None:
    budgets, operations = _stores(
        tmp_path,
        max_operations=1,
        max_total_tokens=100,
        max_cost_usd=0.1,
    )
    service = _service(budgets, operations)
    operation_key = "run-1:text:chapter-01:generate"
    signature = _begin(operations, operation_key)
    first = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    replay = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )

    assert replay.replay is True
    assert replay.admission == first.admission
    assert replay.admission.projected_after.operations == 1
    assert len(budgets.list_admissions("run-1")) == 1
    with pytest.raises(Phase32RunBudgetConflict, match="another budget reservation"):
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=signature,
            reserved_total_tokens=99,
            reserved_cost_usd=0.1,
        )


def test_released_transport_retry_gets_a_new_reserve_but_not_a_new_operation(
    tmp_path: Path,
) -> None:
    budgets, operations = _stores(
        tmp_path,
        max_operations=1,
        max_total_tokens=250,
        max_cost_usd=0.25,
    )
    service = _service(budgets, operations)
    operation_key = "run-1:text:chapter-01:generate"
    signature = _begin(operations, operation_key)
    first = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    first_claim = _claim(
        budgets,
        operations,
        operation_key,
        lease_owner="attempt-one",
    )
    operations.release_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="attempt-one",
        claimed_transport_attempt=first_claim.transport_attempts,
    )

    retry = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    replay_before_claim = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )

    assert first.admission.transport_attempt == 1
    assert retry.replay is False
    assert retry.admission.transport_attempt == 2
    assert retry.admission.new_logical_operation is False
    assert retry.admission.projected_after.operations == 1
    assert retry.admission.projected_after.total_tokens == 200
    assert retry.admission.projected_after.estimated_cost_usd == 0.2
    assert replay_before_claim.replay is True
    assert replay_before_claim.admission == retry.admission
    assert len(budgets.list_admissions("run-1")) == 2


def test_transport_retry_reserve_cannot_cross_run_cost_limit(tmp_path: Path) -> None:
    budgets, operations = _stores(
        tmp_path,
        max_operations=1,
        max_total_tokens=250,
        max_cost_usd=0.15,
    )
    service = _service(budgets, operations)
    operation_key = "run-1:text:chapter-01:generate"
    signature = _begin(operations, operation_key)
    service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    first_claim = _claim(
        budgets,
        operations,
        operation_key,
        lease_owner="attempt-one",
    )
    operations.release_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="attempt-one",
        claimed_transport_attempt=first_claim.transport_attempts,
    )

    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=signature,
            reserved_total_tokens=100,
            reserved_cost_usd=0.1,
        )
    assert exc.value.issue_codes == ("cost_limit_exceeded",)
    assert len(budgets.list_admissions("run-1")) == 1


def test_retry_cap_is_frozen_and_exhaustion_does_not_persist_future_grant(
    tmp_path: Path,
) -> None:
    budgets, operations = _stores(tmp_path, max_transport_attempts=1)
    service = _service(budgets, operations)
    operation_key = "run-1:text:retry-cap"
    signature = _begin(operations, operation_key)
    first = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
        max_transport_attempts=1,
    )
    claimed = operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="attempt-one",
        admission_fence=first.admission,
        max_transport_attempts=1,
    )
    operations.release_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="attempt-one",
        claimed_transport_attempt=claimed.transport_attempts,
    )

    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exhausted:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=signature,
            reserved_total_tokens=100,
            reserved_cost_usd=0.1,
            max_transport_attempts=1,
        )
    assert exhausted.value.issue_codes == ("transport_retry_limit_exhausted",)
    assert [item.transport_attempt for item in budgets.list_admissions("run-1")] == [1]

    with pytest.raises(Phase32RunBudgetAdmissionDenied) as mismatch:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=signature,
            reserved_total_tokens=100,
            reserved_cost_usd=0.1,
            max_transport_attempts=2,
        )
    assert mismatch.value.issue_codes == ("budget_transport_attempt_limit_mismatch",)


def test_stale_replayed_admission_cannot_claim_the_next_transport_attempt(
    tmp_path: Path,
) -> None:
    budgets, operations = _stores(tmp_path)
    service = _service(budgets, operations)
    operation_key = "run-1:text:lease-release-race"
    signature = _begin(operations, operation_key)
    first = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    claimed = operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-a",
        admission_fence=first.admission,
        now=_TIME,
    )
    stale_replay = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    assert stale_replay.replay is True
    operations.release_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-a",
        claimed_transport_attempt=claimed.transport_attempts,
    )

    with pytest.raises(Phase32ProviderOperationAttemptFenceConflict):
        operations.claim_pending(
            run_id="run-1",
            operation_key=operation_key,
            request_signature=signature,
            lease_owner="worker-b",
            admission_fence=stale_replay.admission,
            now=_TIME,
        )
    assert operations.read("run-1", operation_key).transport_attempts == 1

    second = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    recovered = operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-b",
        admission_fence=second.admission,
        now=_TIME,
    )
    assert second.admission.transport_attempt == 2
    assert recovered.transport_attempts == 2
    assert recovered.transport_admission_refs == (
        first.admission.admission_ref,
        second.admission.admission_ref,
    )


def test_late_return_implicitly_voids_one_unclaimed_future_grant(
    tmp_path: Path,
) -> None:
    budgets, operations = _stores(tmp_path, max_operations=3)
    service = _service(budgets, operations)
    operation_key = "run-1:text:late-return"
    signature = _begin(operations, operation_key)
    first = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    claimed = operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="worker-a",
        admission_fence=first.admission,
        lease_seconds=1,
        now=_TIME - timedelta(seconds=2),
    )
    future = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    operations.record_return(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        raw_provider_payload={"content": "late but durable"},
        usage={"prompt_tokens": 5, "completion_tokens": 5},
        pricing_snapshot=_pricing(),
        lease_owner="worker-a",
        claimed_transport_attempt=claimed.transport_attempts,
    )

    next_key = "run-1:text:after-late-return"
    next_admission = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=next_key,
        request_signature=_begin(operations, next_key),
        reserved_total_tokens=20,
        reserved_cost_usd=0.02,
    )

    assert future.admission.transport_attempt == 2
    assert operations.read("run-1", operation_key).transport_admission_refs == (
        first.admission.admission_ref,
    )
    assert next_admission.admission.allocated_before.total_tokens == 10
    assert next_admission.admission.allocated_before.estimated_cost_usd == 0.00001
    assert next_admission.admission.projected_after.total_tokens == 30
    assert len(budgets.list_admissions("run-1")) == 3


@pytest.mark.parametrize(
    ("usage", "issue_code"),
    [
        ({"prompt_tokens": 10}, "receipt_token_usage_incomplete"),
        ({"completion_tokens": 10}, "receipt_token_usage_incomplete"),
        (
            {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 5},
            "receipt_total_tokens_inconsistent",
        ),
    ],
)
def test_partial_or_inconsistent_terminal_usage_never_releases_reserve(
    tmp_path: Path,
    usage: dict[str, int],
    issue_code: str,
) -> None:
    budgets, operations = _stores(tmp_path)
    service = _service(budgets, operations)
    operation_key = "run-1:text:partial-usage"
    signature = _begin(operations, operation_key)
    admission = service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    claimed = operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="usage-worker",
        admission_fence=admission.admission,
    )
    operations.record_return(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        raw_provider_payload={"content": "usage fixture"},
        usage=usage,
        pricing_snapshot=_pricing(),
        lease_owner="usage-worker",
        claimed_transport_attempt=claimed.transport_attempts,
    )

    next_key = "run-1:text:after-partial-usage"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=next_key,
            request_signature=_begin(operations, next_key),
            reserved_total_tokens=10,
            reserved_cost_usd=0.01,
        )
    assert issue_code in exc.value.issue_codes


def test_budgeted_receipt_with_missing_claim_refs_fails_closed(tmp_path: Path) -> None:
    budgets, operations = _stores(tmp_path)
    service = _service(budgets, operations)
    operation_key = "run-1:text:missing-claim-ref"
    signature = _begin(operations, operation_key)
    service.admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100,
        reserved_cost_usd=0.1,
    )
    claimed = operations.claim_pending(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        lease_owner="legacy-worker",
    )
    operations.record_return(
        run_id="run-1",
        operation_key=operation_key,
        request_signature=signature,
        raw_provider_payload={"content": "unfenced"},
        usage={"prompt_tokens": 5, "completion_tokens": 5},
        pricing_snapshot=_pricing(),
        lease_owner="legacy-worker",
        claimed_transport_attempt=claimed.transport_attempts,
    )

    next_key = "run-1:text:after-unfenced"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        service.admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=next_key,
            request_signature=_begin(operations, next_key),
            reserved_total_tokens=10,
            reserved_cost_usd=0.01,
        )
    assert exc.value.issue_codes == ("transport_admission_ref_missing",)


def test_receipt_without_budget_admission_blocks_later_work(tmp_path: Path) -> None:
    budgets, operations = _stores(tmp_path)
    bypass_key = "run-1:text:bypassed"
    bypass_signature = _begin(operations, bypass_key)
    operations.claim_pending(
        run_id="run-1",
        operation_key=bypass_key,
        request_signature=bypass_signature,
        lease_owner="bypass-owner",
    )
    operations.record_return(
        run_id="run-1",
        operation_key=bypass_key,
        request_signature=bypass_signature,
        raw_provider_payload={"content": "bypassed"},
        usage={"prompt_tokens": 10, "completion_tokens": 10},
        pricing_snapshot=_pricing(),
        lease_owner="bypass-owner",
    )
    next_key = "run-1:text:next"

    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        _service(budgets, operations).admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=next_key,
            request_signature=_begin(operations, next_key),
            reserved_total_tokens=100,
            reserved_cost_usd=0.01,
        )
    assert exc.value.issue_codes == ("receipt_budget_admission_missing",)


def test_authorization_and_admission_survive_process_restart(tmp_path: Path) -> None:
    budgets, operations = _stores(tmp_path)
    operation_key = "run-1:text:chapter-01:generate"
    signature = _begin(operations, operation_key)
    original = _service(budgets, operations).admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100_000,
        reserved_cost_usd=0.1,
    )

    reopened_budgets = Phase32RunBudgetStore(tmp_path / "budgets")
    reopened_operations = Phase32ProviderOperationStore(tmp_path / "operations")
    replay = _service(reopened_budgets, reopened_operations).admit(
        run_id="run-1",
        definition_digest=_DEFINITION_DIGEST,
        operation_key=operation_key,
        request_signature=signature,
        reserved_total_tokens=100_000,
        reserved_cost_usd=0.1,
    )

    assert replay.replay is True
    assert replay.admission.admission_ref == original.admission.admission_ref
    assert reopened_budgets.read_authorization("run-1").authorization_ref == (
        original.admission.authorization_ref
    )


def test_missing_authorization_fails_closed(tmp_path: Path) -> None:
    budgets = Phase32RunBudgetStore(tmp_path / "budgets")
    operations = Phase32ProviderOperationStore(tmp_path / "operations")
    operation_key = "run-1:text:chapter-01:generate"
    with pytest.raises(Phase32RunBudgetAdmissionDenied) as exc:
        _service(budgets, operations).admit(
            run_id="run-1",
            definition_digest=_DEFINITION_DIGEST,
            operation_key=operation_key,
            request_signature=_signature(operation_key),
            reserved_total_tokens=100,
            reserved_cost_usd=0.01,
        )
    assert exc.value.issue_codes == ("budget_authorization_missing",)
