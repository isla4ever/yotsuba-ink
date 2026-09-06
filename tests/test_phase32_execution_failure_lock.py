from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from novel_workflow.output_contracts.phase32_route_artifacts import ScreenplayBriefArtifact
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32DecisionCommand,
    Phase32ExecutionConflict,
    Phase32ExecutionLockConflict,
    Phase32FailureRecoveryCommand,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_graph_execution import Phase32ExecutionError
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32ProviderResponse,
)
from novel_workflow.runtime.graph.phase32_driver import (
    Phase32RouteDriver,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_decision_receipt_store import Phase32DecisionReceiptStore
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from novel_workflow.workflows.review_policy import SCREENPLAY_REVIEW_POLICY
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from tests.test_phase32_driver import _payload_for


def _payload() -> dict[str, object]:
    return ScreenplayBriefArtifact(
        title="失序档案",
        sample_type="调查悬疑样片",
        target_minutes=12,
        premise="公共档案的签名链正在被有意抹除。",
        audience_promise="证据推动的调查样片。",
        visible_conflict="主角必须在闭馆前证明签名页被替换。",
        ending_effect="签名页在听证会上重新拼合。",
        tone="冷峻、克制",
    ).model_dump(mode="json")


class _FailOnceGateway:
    def __init__(self) -> None:
        self.failed = False
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        if not self.failed:
            self.failed = True
            raise TimeoutError("simulated upstream interruption")
        return Phase32ProviderResponse(
            payload=_payload(),
            usage={"prompt_tokens": 5, "completion_tokens": 7},
        )


class _ContractFailOnceGateway:
    def __init__(self) -> None:
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        payload = {"title": "被截断的候选"} if len(self.requests) == 1 else _payload()
        return Phase32ProviderResponse(
            payload=payload,
            usage={"prompt_tokens": 5, "completion_tokens": 7},
        )


class _ContractRejectOnRedraftGateway:
    def __init__(self) -> None:
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        payload = _payload() if len(self.requests) == 1 else {"title": "无效重写"}
        return Phase32ProviderResponse(
            payload=payload,
            usage={"prompt_tokens": 5, "completion_tokens": 7},
        )


@pytest.mark.asyncio
async def test_retryable_failure_is_projected_and_next_start_recovers(tmp_path: Path) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="failure-projection-run",
        project_id="failure-projection-project",
        creative_intent="验证 transport failure 的监控投影和恢复。",
    )
    gateway = _FailOnceGateway()
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: Phase32RouteDriver(artifact_store, gateway),
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
    )

    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await service.start(fixture.definition.run_id)

    failed = fixture.repository.read(fixture.definition.run_id)
    assert failed.state.status == "running"
    assert failed.read_model.failure is not None
    assert failed.read_model.failure.code == "provider_transport_failed"
    assert failed.read_model.failure.retryable is True
    assert failed.read_model.provider_usage.pending_operations == 1
    failure_event = fixture.repository.events(fixture.definition.run_id)[-1]
    assert failure_event.type == "stage.failed"
    assert failure_event.payload == {
        "code": "provider_transport_failed",
        "retryable": True,
        "message": "simulated upstream interruption",
    }
    assert Phase32EventProjection(fixture.repository).page(
        fixture.definition.run_id,
        after=failure_event.sequence - 1,
    ).terminal is True

    recovered = await service.start(fixture.definition.run_id)
    assert recovered.result.interrupted is True
    restored = fixture.repository.read(fixture.definition.run_id)
    assert restored.read_model.failure is None
    assert restored.read_model.provider_usage.succeeded_operations == 1
    resumed_events = fixture.repository.events(fixture.definition.run_id)
    assert resumed_events[-1].type == "decision.required"
    assert Phase32EventProjection(fixture.repository).page(
        fixture.definition.run_id,
        after=failure_event.sequence,
    ).terminal is True


@pytest.mark.asyncio
async def test_contract_failure_requires_one_explicit_policy_bounded_recovery(
    tmp_path: Path,
) -> None:
    review_policy = SCREENPLAY_REVIEW_POLICY.model_copy(
        update={
            "policy_id": "review.screenplay.failure-recovery",
            "directed_redraft_limit_by_stage": {
                **SCREENPLAY_REVIEW_POLICY.directed_redraft_limit_by_stage,
                "brief": 1,
            },
        }
    )
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="contract-failure-recovery-run",
        project_id="contract-failure-recovery-project",
        creative_intent="验证合同失败只允许一次显式定向恢复。",
        review_policy=review_policy,
    )
    gateway = _ContractFailOnceGateway()
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    decisions = Phase32DecisionReceiptStore(tmp_path / "decisions")
    driver = Phase32RouteDriver(artifact_store, gateway)
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=decisions,
    )

    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await service.start(fixture.definition.run_id)
    failed = fixture.repository.read(fixture.definition.run_id)
    assert failed.state.status == "failed"
    assert failed.read_model.failure is not None
    assert failed.read_model.failure.code == "provider_contract_failed"

    direction = "只输出完整、简洁且可闭合的合同 JSON。"
    recovered = await service.recover(
        fixture.definition.run_id,
        Phase32FailureRecoveryCommand(
            recovery_id="brief-contract-recovery-1",
            domain_revision=failed.state.domain_revision,
            direction=direction,
        ),
    )

    assert recovered.result.interrupted is True
    assert recovered.result.decision is not None
    assert recovered.result.decision["stage_id"] == "brief"
    restored = fixture.repository.read(fixture.definition.run_id)
    assert restored.state.status == "awaiting_decision"
    assert restored.read_model.failure is None
    assert restored.state.stage_attempts["brief"] == 1
    assert restored.state.stage_revision_directions["brief"] == direction
    assert [request.direction for request in gateway.requests] == ["", direction]
    provider_statuses = [
        receipt.status
        for receipt in driver.provider_operations.list(fixture.definition.run_id)
    ]
    assert provider_statuses.count("contract_rejected") == 1
    assert provider_statuses.count("succeeded") == 1

    replay = await service.recover(
        fixture.definition.run_id,
        {
            "recovery_id": "brief-contract-recovery-1",
            "domain_revision": failed.state.domain_revision,
            "direction": direction,
        },
    )
    assert replay.reused is True
    assert len(gateway.requests) == 2


@pytest.mark.asyncio
async def test_contract_rejected_redraft_consumes_decision_and_clears_pending_projection(
    tmp_path: Path,
) -> None:
    review_policy = SCREENPLAY_REVIEW_POLICY.model_copy(
        update={
            "policy_id": "review.screenplay.failed-redraft",
            "directed_redraft_limit_by_stage": {
                **SCREENPLAY_REVIEW_POLICY.directed_redraft_limit_by_stage,
                "brief": 1,
            },
        }
    )
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="failed-redraft-reconciliation-run",
        project_id="failed-redraft-reconciliation-project",
        creative_intent="验证失败重生成不会留下幽灵决策。",
        review_policy=review_policy,
    )
    gateway = _ContractRejectOnRedraftGateway()
    decisions = Phase32DecisionReceiptStore(tmp_path / "decisions")
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"), gateway
    )
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=decisions,
    )

    started = await service.start(fixture.definition.run_id)
    assert started.result.decision is not None
    decision = started.result.decision
    command = Phase32DecisionCommand(
        decision_id=decision["decision_id"],
        action="regenerate",
        domain_revision=decision["domain_revision"],
        direction="只输出符合合同的完整 JSON。",
    )

    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await service.resume(fixture.definition.run_id, command)

    failed = fixture.repository.read(fixture.definition.run_id)
    assert failed.state.status == "failed"
    assert failed.state.pending_decision_action == "regenerate"
    assert failed.state.pending_decision_redraft_count == 1
    assert failed.read_model.pending_decisions == ()
    assert failed.read_model.failure is not None
    assert failed.read_model.failure.code == "provider_contract_failed"
    decision_receipt = decisions.find(
        fixture.definition.run_id,
        f"decision:{command.decision_id}",
    )
    assert decision_receipt is not None
    assert decision_receipt.status == "succeeded"
    assert decision_receipt.result["downstream_failure"] is True

    replay = await service.resume(fixture.definition.run_id, command)
    assert replay.reused is True
    assert len(gateway.requests) == 2
    with pytest.raises(
        Phase32ExecutionConflict,
        match="exceeds the frozen ReviewPolicy redraft limit",
    ):
        await service.recover(
            fixture.definition.run_id,
            Phase32FailureRecoveryCommand(
                recovery_id="failed-redraft-recovery-1",
                domain_revision=failed.state.domain_revision,
                direction="再次重写。",
            ),
        )
    assert len(gateway.requests) == 2


class _Wave21RejectedBeatGateway:
    def __init__(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures/phase32_wave21_beat_board_contract_rejected.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.rejected_payload = fixture["payload"]
        self.fixture_digest = fixture["source"]["canonical_payload_sha256"]
        self.requests: list[Phase32ProviderRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        payload = (
            self.rejected_payload
            if request.stage_id == "beat_board"
            else _payload_for(request.creation_route_id, request.stage_id)
        )
        return Phase32ProviderResponse(
            payload=payload,
            usage={"prompt_tokens": 5, "completion_tokens": 7},
        )


@pytest.mark.asyncio
async def test_accepted_cast_then_beat_contract_rejection_projects_checkpoint_frontier(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="wave21-beat-contract-rejection",
        project_id="wave21-beat-contract-project",
        creative_intent="回放真实 Beat Board 合同拒绝，不调用外部 Provider。",
    )
    gateway = _Wave21RejectedBeatGateway()
    assert canonical_digest(gateway.rejected_payload) == gateway.fixture_digest
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    driver = Phase32RouteDriver(artifact_store, gateway)
    decisions = Phase32DecisionReceiptStore(tmp_path / "decisions")
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=decisions,
    )

    started = await service.start(fixture.definition.run_id)
    assert started.result.decision is not None
    brief_decision = started.result.decision
    cast = await service.resume(
        fixture.definition.run_id,
        {
            "decision_id": brief_decision["decision_id"],
            "action": "accept",
            "domain_revision": brief_decision["domain_revision"],
        },
    )
    assert cast.result.decision is not None
    cast_decision = cast.result.decision
    assert cast_decision["stage_id"] == "cast"
    with pytest.raises(Phase32ExecutionError, match="graph step failed"):
        await service.resume(
            fixture.definition.run_id,
            {
                "decision_id": cast_decision["decision_id"],
                "action": "accept",
                "domain_revision": cast_decision["domain_revision"],
            },
        )

    failed = fixture.repository.read(fixture.definition.run_id)
    assert failed.state.status == "failed"
    assert failed.state.active_stage_id == "beat_board"
    assert failed.state.stage_status == {
        "brief": "completed",
        "cast": "completed",
        "beat_board": "failed",
        "scene_deck": "locked",
        "script": "locked",
        "export": "locked",
    }
    assert set(failed.state.artifact_refs) == {"brief", "cast"}
    assert failed.state.domain_revision == 2
    assert failed.read_model.status == "failed"
    assert failed.read_model.active_stage_id == "beat_board"
    assert set(failed.read_model.artifact_refs) == {"brief", "cast"}
    assert failed.read_model.pending_decisions == ()
    assert failed.read_model.checkpoint_id
    assert failed.read_model.failure is not None
    assert failed.read_model.failure.code == "provider_contract_failed"
    assert failed.read_model.failure.stage_id == "beat_board"
    assert failed.read_model.failure.retryable is False
    assert str(failed.read_model.failure.message).endswith("screenplay_sample/beat_board")
    assert failed.read_model.provider_usage.provider_operations == 3
    assert failed.read_model.provider_usage.contract_rejected_operations == 1

    decision_receipts = decisions.list(fixture.definition.run_id)
    assert len(decision_receipts) == 2
    assert all(receipt.status == "succeeded" for receipt in decision_receipts)
    assert sum(
        receipt.result
        == {
            "status": "failed",
            "active_stage_id": "beat_board",
            "downstream_failure": True,
        }
        for receipt in decision_receipts
    ) == 1
    provider_receipts = driver.provider_operations.list(fixture.definition.run_id)
    assert [receipt.status for receipt in provider_receipts].count("contract_rejected") == 1
    assert len(gateway.requests) == 3
    failure_event = fixture.repository.events(fixture.definition.run_id)[-1]
    assert failure_event.type == "stage.failed"
    assert failure_event.stage_id == "beat_board"
    assert failure_event.node_id == "beat_board.generate"
    assert failure_event.status == "failed"
    assert failure_event.payload["code"] == "provider_contract_failed"
    assert [
        event.type for event in fixture.repository.events(fixture.definition.run_id)
    ].count("decision.required") == 2

    with pytest.raises(Phase32ExecutionConflict, match="explicit recovery path"):
        await service.start(fixture.definition.run_id)
    assert len(gateway.requests) == 3


class _GateGateway:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.started.set()
        await self.release.wait()
        return Phase32ProviderResponse(payload=_payload())


@pytest.mark.asyncio
async def test_second_service_cannot_execute_same_run_while_first_holds_lock(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="execution-lock-run",
        project_id="execution-lock-project",
        creative_intent="验证跨进程 Run execution lock。",
    )
    gateway = _GateGateway()
    service_a = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints-a",
        driver_factory=lambda _definition: Phase32RouteDriver(
            Phase32ArtifactStore(tmp_path / "artifacts-a"), gateway
        ),
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions-a"),
        execution_lock_timeout_seconds=1.0,
    )
    service_b = Phase32RunExecutionService(
        type(fixture.repository)(fixture.repository.root),
        checkpoint_root=tmp_path / "checkpoints-b",
        driver_factory=lambda _definition: Phase32RouteDriver(
            Phase32ArtifactStore(tmp_path / "artifacts-b"), _FailOnceGateway()
        ),
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions-b"),
        execution_lock_timeout_seconds=0.1,
    )

    first_task = asyncio.create_task(service_a.start(fixture.definition.run_id))
    await asyncio.wait_for(gateway.started.wait(), timeout=1.0)
    with pytest.raises(Phase32ExecutionLockConflict, match="already executing"):
        await service_b.start(fixture.definition.run_id)

    gateway.release.set()
    first = await first_task
    assert first.result.interrupted is True
