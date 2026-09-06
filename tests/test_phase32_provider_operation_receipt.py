from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.output_contracts.phase32_route_artifacts import ScreenplayBriefArtifact
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
    Phase32ProviderOperationReceiptConflict,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from tests.test_phase32_route_graph import _definition


def _brief_payload() -> dict[str, object]:
    return ScreenplayBriefArtifact(
        title="失序档案",
        sample_type="调查悬疑样片",
        target_minutes=12,
        premise="公共档案的签名链正在被有意抹除。",
        audience_promise="一部节奏克制、证据驱动的调查样片。",
        visible_conflict="主角必须在闭馆前证明签名页被替换。",
        ending_effect="被撕开的签名页在听证会上重新拼合。",
        tone="冷峻、克制、证据驱动",
    ).model_dump(mode="json")


class _Gateway:
    def __init__(self, payload: dict[str, object], *, fail_once: bool = False) -> None:
        self.payload = payload
        self.fail_once = fail_once
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        if self.fail_once:
            self.fail_once = False
            raise TimeoutError("fake transport timeout")
        return Phase32ProviderResponse(payload=self.payload, usage={"total_tokens": 7})


class _MalformedEnvelopeGateway(_Gateway):
    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> dict[str, object]:
        self.requests.append(request)
        return {"payload": ["not", "an", "object"]}


@pytest.mark.asyncio
async def test_same_operation_reuses_succeeded_candidate_without_gateway_call(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    gateway = _Gateway(_brief_payload())
    driver = Phase32RouteDriver(
        artifact_store,
        gateway,
        provider_operations=operations,
    )

    first = await driver.generate_stage(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=definition.stage("brief"),
    )
    second = await driver.generate_stage(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=definition.stage("brief"),
    )

    assert second == first
    assert len(gateway.requests) == 1
    receipt = operations.read(definition.run_id, gateway.requests[0].operation_key)
    assert receipt.status == "succeeded"
    assert receipt.result == {"artifact_ref": first.artifact_ref, "unit_ref": ""}
    assert receipt.usage == {"total_tokens": 7}


@pytest.mark.asyncio
async def test_restarted_driver_recovers_returned_candidate_without_gateway_call(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    first_gateway = _Gateway(_brief_payload())
    first_driver = Phase32RouteDriver(
        artifact_store,
        first_gateway,
        provider_operations=operations,
    )
    first = await first_driver.generate_stage(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=definition.stage("brief"),
    )

    # A new process/context gets the same durable stores but a gateway that
    # would fail if called; the succeeded receipt must be enough to recover.
    restarted_gateway = _Gateway({}, fail_once=True)
    restarted_driver = Phase32RouteDriver(
        artifact_store,
        restarted_gateway,
        provider_operations=Phase32ProviderOperationStore(tmp_path / "provider-operations"),
    )
    recovered = await restarted_driver.generate_stage(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=definition.stage("brief"),
    )

    assert recovered == first
    assert restarted_gateway.requests == []


def test_operation_key_rejects_changed_frozen_request_signature(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    first = {"operation_key": "run-1:brief:1", "model": "fake", "direction": ""}
    second = {"operation_key": "run-1:brief:1", "model": "fake", "direction": "改写冲突"}
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=provider_request_signature(first),
    )

    with pytest.raises(Phase32ProviderOperationReceiptConflict, match="different frozen request"):
        store.begin(
            run_id="run-1",
            operation_key="run-1:brief:1",
            stage_id="brief",
            request_signature=provider_request_signature(second),
        )


@pytest.mark.asyncio
async def test_malformed_artifact_is_recorded_as_contract_rejection(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    gateway = _Gateway({"not": "a brief"})
    driver = Phase32RouteDriver(artifact_store, gateway, provider_operations=operations)

    with pytest.raises(Phase32DriverError, match="Artifact payload"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )

    operation_key = gateway.requests[0].operation_key
    receipt = operations.read(definition.run_id, operation_key)
    assert receipt.status == "contract_rejected"
    assert receipt.raw_provider_payload == {"not": "a brief"}
    assert receipt.diagnostic["code"] == "artifact_contract_rejected"

    with pytest.raises(Phase32DriverError, match="contract was rejected"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
async def test_malformed_provider_envelope_is_also_recorded_as_contract_rejection(
    tmp_path: Path,
) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    gateway = _MalformedEnvelopeGateway({})
    driver = Phase32RouteDriver(artifact_store, gateway, provider_operations=operations)

    with pytest.raises(Phase32DriverError, match="response contract is invalid"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )

    operation_key = gateway.requests[0].operation_key
    receipt = operations.read(definition.run_id, operation_key)
    assert receipt.status == "contract_rejected"
    assert receipt.raw_provider_payload == {}
    assert receipt.diagnostic["code"] == "provider_response_invalid"


@pytest.mark.asyncio
async def test_transport_failure_keeps_pending_and_allows_same_operation_retry(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    gateway = _Gateway(_brief_payload(), fail_once=True)
    driver = Phase32RouteDriver(artifact_store, gateway, provider_operations=operations)

    with pytest.raises(Phase32DriverError, match="transport failed"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )
    operation_key = gateway.requests[0].operation_key
    assert operations.read(definition.run_id, operation_key).status == "pending"

    candidate = await driver.generate_stage(
        definition=definition,
        state=initial_route_run_state(definition),
        stage=definition.stage("brief"),
    )
    assert candidate.artifact_ref
    assert len(gateway.requests) == 2
    assert operations.read(definition.run_id, operation_key).status == "succeeded"
