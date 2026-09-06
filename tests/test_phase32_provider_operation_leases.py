from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.output_contracts.phase32_route_artifacts import ScreenplayBriefArtifact
from novel_workflow.orchestration.phase32_graph_execution import Phase32GraphExecutionService
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32ProviderResponse,
)
from novel_workflow.runtime.graph.phase32_driver import (
    Phase32DriverError,
    Phase32RouteDriver,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationAttemptFenceConflict,
    Phase32ProviderOperationLeaseConflict,
    Phase32ProviderOperationRetryExhausted,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from tests.test_phase32_route_graph import _definition


def _request_signature() -> str:
    return provider_request_signature(
        {"run_id": "run-1", "operation_key": "run-1:brief:1", "stage_id": "brief"}
    )


def _admission_fence(attempt: int) -> Phase32ProviderOperationAdmissionFence:
    digest = hashlib.sha256(f"run-1:brief:1\0{attempt}".encode("utf-8")).hexdigest()
    return Phase32ProviderOperationAdmissionFence(
        authorization_ref=f"p32-run-budget-{'b' * 64}",
        run_id="run-1",
        definition_digest="d" * 64,
        operation_key="run-1:brief:1",
        request_signature=_request_signature(),
        admission_ref=f"p32-budget-admission-{digest}",
        transport_attempt=attempt,
    )


def test_admission_fence_rejects_boolean_transport_attempt() -> None:
    with pytest.raises(ValueError, match="cannot be boolean"):
        _admission_fence(True)


def test_pending_operation_has_cross_process_lease_and_bounded_retries(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    signature = _request_signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
    )
    first_now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    first = store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        lease_seconds=30,
        now=first_now,
    )
    assert first.transport_attempts == 1
    assert first.lease_owner == "process-a"

    other_process_store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    with pytest.raises(Phase32ProviderOperationLeaseConflict):
        other_process_store.claim_pending(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            lease_owner="process-b",
            lease_seconds=30,
            now=first_now + timedelta(seconds=10),
        )

    recovered = other_process_store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-b",
        lease_seconds=30,
        max_transport_attempts=2,
        now=first_now + timedelta(seconds=31),
    )
    assert recovered.transport_attempts == 2
    other_process_store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-b",
    )
    with pytest.raises(Phase32ProviderOperationRetryExhausted):
        other_process_store.claim_pending(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            lease_owner="process-c",
            max_transport_attempts=2,
        )


def test_attempt_fence_rejects_stale_grant_without_incrementing_receipt(
    tmp_path: Path,
) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    signature = _request_signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
    )
    first = store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        admission_fence=_admission_fence(1),
    )
    store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        claimed_transport_attempt=first.transport_attempts,
    )

    with pytest.raises(Phase32ProviderOperationAttemptFenceConflict):
        store.claim_pending(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            lease_owner="process-b",
            admission_fence=_admission_fence(1),
        )

    unchanged = store.read("run-1", "run-1:brief:1")
    assert unchanged.transport_attempts == 1
    assert unchanged.lease_owner == ""
    assert unchanged.transport_admission_refs == (
        _admission_fence(1).admission_ref,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("definition_digest", "e" * 64),
        ("authorization_ref", f"p32-run-budget-{'c' * 64}"),
    ),
)
def test_attempt_fence_rejects_budget_authority_drift_without_incrementing_receipt(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    signature = _request_signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
    )
    first_fence = _admission_fence(1)
    first = store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        admission_fence=first_fence,
    )
    store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        claimed_transport_attempt=first.transport_attempts,
    )
    drifted_fence = _admission_fence(2).model_copy(update={field: value})

    with pytest.raises(Phase32ProviderOperationAttemptFenceConflict):
        store.claim_pending(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            lease_owner="process-b",
            admission_fence=drifted_fence,
        )

    unchanged = store.read("run-1", "run-1:brief:1")
    assert unchanged.transport_attempts == 1
    assert unchanged.transport_admission_refs == (first_fence.admission_ref,)
    assert unchanged.budget_definition_digest == first_fence.definition_digest
    assert unchanged.budget_authorization_ref == first_fence.authorization_ref
    assert unchanged.lease_owner == ""


def test_attempt_fence_rejects_reused_admission_ref_without_corrupting_receipt(
    tmp_path: Path,
) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    signature = _request_signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
    )
    first_fence = _admission_fence(1)
    first = store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        admission_fence=first_fence,
    )
    store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        claimed_transport_attempt=first.transport_attempts,
    )
    reused_ref = _admission_fence(2).model_copy(
        update={"admission_ref": first_fence.admission_ref}
    )

    with pytest.raises(Phase32ProviderOperationAttemptFenceConflict):
        store.claim_pending(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            lease_owner="process-b",
            admission_fence=reused_ref,
        )

    unchanged = Phase32ProviderOperationStore(
        tmp_path / "provider-operations"
    ).read("run-1", "run-1:brief:1")
    assert unchanged.transport_attempts == 1
    assert unchanged.transport_admission_refs == (first_fence.admission_ref,)
    assert unchanged.lease_owner == ""


def test_claimed_attempt_fence_rejects_stale_return_after_new_attempt(
    tmp_path: Path,
) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    signature = _request_signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
    )
    first = store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        admission_fence=_admission_fence(1),
    )
    store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-a",
        claimed_transport_attempt=first.transport_attempts,
    )
    second = store.claim_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-b",
        admission_fence=_admission_fence(2),
    )
    store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="process-b",
        claimed_transport_attempt=second.transport_attempts,
    )

    with pytest.raises(Phase32ProviderOperationAttemptFenceConflict):
        store.record_return(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            raw_provider_payload={"stale": True},
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            lease_owner="process-a",
            claimed_transport_attempt=first.transport_attempts,
        )
    assert store.read("run-1", "run-1:brief:1").status == "pending"


def test_usage_summary_rebuilds_from_receipts(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    returned_signature = provider_request_signature(
        {"run_id": "run-1", "operation_key": "run-1:brief:returned", "stage_id": "brief"}
    )
    pending_signature = provider_request_signature(
        {"run_id": "run-1", "operation_key": "run-1:brief:pending", "stage_id": "brief"}
    )
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:returned",
        stage_id="brief",
        request_signature=returned_signature,
    )
    store.record_return(
        run_id="run-1",
        operation_key="run-1:brief:returned",
        request_signature=returned_signature,
        raw_provider_payload={"payload": "raw"},
        usage={"prompt_tokens": 4, "completion_tokens": 6},
    )
    store.succeed(
        run_id="run-1",
        operation_key="run-1:brief:returned",
        request_signature=returned_signature,
        result={"artifact_ref": "candidate", "unit_ref": ""},
    )
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:pending",
        stage_id="brief",
        request_signature=pending_signature,
    )

    summary = store.usage_summary("run-1")
    assert summary.provider_operations == 2
    assert summary.succeeded_operations == 1
    assert summary.pending_operations == 1
    assert summary.total_tokens == 10


class _UsageGateway:
    def __init__(self) -> None:
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        payload = ScreenplayBriefArtifact(
            title="失序档案",
            sample_type="调查悬疑样片",
            target_minutes=12,
            premise="公共档案的签名链正在被有意抹除。",
            audience_promise="证据推动的调查样片。",
            visible_conflict="主角必须在闭馆前证明签名页被替换。",
            ending_effect="签名页在听证会上重新拼合。",
            tone="冷峻、克制",
        ).model_dump(mode="json")
        return Phase32ProviderResponse(
            payload=payload,
            usage={"prompt_tokens": 8, "completion_tokens": 12},
        )


class _FlakyGateway(_UsageGateway):
    def __init__(self) -> None:
        super().__init__()
        self.failures = 1

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        if self.failures:
            self.failures -= 1
            self.requests.append(request)
            raise TimeoutError("simulated Provider interruption")
        return await super().generate(request, binding=binding)


@pytest.mark.asyncio
async def test_driver_releases_transport_lease_and_retries_same_operation(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    gateway = _FlakyGateway()
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        gateway,
        provider_operations=operations,
        provider_max_transport_attempts=2,
    )

    with pytest.raises(Phase32DriverError, match="transport failed"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )
    operation_key = gateway.requests[0].operation_key
    first_receipt = operations.read(definition.run_id, operation_key)
    assert first_receipt.status == "pending"
    assert first_receipt.transport_attempts == 1
    assert first_receipt.lease_owner == ""

    candidate = await driver.generate_stage(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=definition.stage("brief"),
    )
    assert candidate.artifact_ref
    assert len(gateway.requests) == 2
    assert operations.read(definition.run_id, operation_key).transport_attempts == 2


@pytest.mark.asyncio
async def test_phase32_read_model_projects_provider_usage_from_receipts(tmp_path: Path) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="usage-read-model",
        project_id="project-usage-read-model",
        creative_intent="验证 usage projection 不依赖 UI 本地状态。",
    )
    gateway = _UsageGateway()
    driver = Phase32RouteDriver(Phase32ArtifactStore(tmp_path / "artifacts"), gateway)
    result = await Phase32GraphExecutionService(fixture.repository).step(
        fixture.definition.run_id,
        driver=driver,
        checkpointer=InMemorySaver(),
    )
    usage = result.record.read_model.provider_usage
    assert usage.provider_operations == 1
    assert usage.total_tokens == 20
    assert usage.pending_operations == 0
