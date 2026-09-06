from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32DecisionCommand,
    Phase32ExecutionConflict,
    Phase32RunAdmissionRequired,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    Phase32ProviderReadinessAdmissionError,
    Phase32ProviderReadinessAdmissionVerdict,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.output_contracts.phase32_delivery_artifacts import CoverArtifact
from novel_workflow.runtime.graph.route_graph import RouteStageCandidate
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_artifact_draft_store import Phase32ArtifactDraftStore
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptConflict,
    Phase32DecisionReceiptStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE
from tests.test_phase32_driver import (
    _FixtureGateway,
    _continuity_acceptance_definition,
)
from tests.test_phase32_route_graph import FakeRouteDriver


def test_decision_receipt_is_idempotent_and_command_bound(tmp_path: Path) -> None:
    store = Phase32DecisionReceiptStore(tmp_path)
    command = {
        "decision_id": "run-1:brief:candidate",
        "action": "accept",
        "domain_revision": 1,
        "direction": "",
    }
    first = store.begin(
        run_id="run-1",
        operation_key="decision:run-1:brief:candidate",
        decision_id=command["decision_id"],
        command=command,
    )
    repeated = store.begin(
        run_id="run-1",
        operation_key="decision:run-1:brief:candidate",
        decision_id=command["decision_id"],
        command=command,
    )
    assert first == repeated
    with pytest.raises(Phase32DecisionReceiptConflict):
        store.begin(
            run_id="run-1",
            operation_key="decision:run-1:brief:candidate",
            decision_id=command["decision_id"],
            command={**command, "action": "cancel"},
        )
    succeeded = store.succeed(
        run_id="run-1",
        operation_key="decision:run-1:brief:candidate",
        result={"status": "running"},
    )
    assert succeeded.status == "succeeded"
    assert store.read("run-1", "decision:run-1:brief:candidate") == succeeded
    assert store.succeed(
        run_id="run-1",
        operation_key="decision:run-1:brief:candidate",
        result={"status": "running"},
    ) == succeeded


@pytest.mark.asyncio
async def test_execution_service_starts_resumes_and_reuses_decision_receipt(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="service-short-novel",
        project_id="project-service-short-novel",
        creative_intent="验证 start/resume orchestration 的决策幂等性。",
    )
    gateway = _FixtureGateway({})
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    driver = Phase32RouteDriver(artifacts, gateway)
    editing = Phase32ArtifactEditingService(
        fixture.repository,
        artifacts,
        Phase32ArtifactDraftStore(tmp_path / "artifact-drafts"),
    )
    receipts = Phase32DecisionReceiptStore(tmp_path / "decisions")
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: driver,
        decisions=receipts,
        artifact_editing=editing,
    )

    started = await service.start(fixture.definition.run_id)
    assert started.result.interrupted is True
    assert started.result.decision is not None
    command = Phase32DecisionCommand.model_validate(
        {
            "decision_id": started.result.decision["decision_id"],
            "action": "accept",
            "domain_revision": started.result.decision["domain_revision"],
        }
    )
    resumed = await service.resume(fixture.definition.run_id, command)
    repeated = await service.resume(fixture.definition.run_id, command)
    assert resumed.reused is False
    assert repeated.reused is True
    assert repeated.record.state == resumed.record.state

    outcome = resumed
    while outcome.result.interrupted:
        assert outcome.result.decision is not None
        decision = outcome.result.decision
        draft_ref = ""
        if decision["stage_id"] == "cover":
            source = artifacts.read(
                fixture.definition.run_id,
                decision["artifact_ref"],
            )
            cover = CoverArtifact.model_validate(source.payload)
            selected = cover.model_copy(
                update={"selected_asset_ref": cover.candidates[0].asset_ref}
            )
            draft = editing.save_draft(
                fixture.definition.run_id,
                decision["decision_id"],
                domain_revision=decision["domain_revision"],
                source_artifact_ref=decision["artifact_ref"],
                payload=selected.model_dump(mode="json"),
            )
            draft_ref = draft.draft_ref
        next_command = Phase32DecisionCommand.model_validate(
            {
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
                "draft_ref": draft_ref,
            }
        )
        outcome = await service.resume(fixture.definition.run_id, next_command)

    assert outcome.record.state.status == "completed"
    assert len(receipts.list(fixture.definition.run_id)) >= 2
    assert len(gateway.requests) == len(fixture.definition.route_contract.provider_stage_ids)


@pytest.mark.asyncio
async def test_execution_service_does_not_restart_awaiting_run(tmp_path: Path) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="service-awaiting-short",
        project_id="project-service-awaiting-short",
        creative_intent="验证 start 的 awaiting 幂等。",
    )
    gateway = _FixtureGateway({})
    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: Phase32RouteDriver(
            Phase32ArtifactStore(tmp_path / "artifacts"), gateway
        ),
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
    )
    started = await service.start(fixture.definition.run_id)
    repeated = await service.start(fixture.definition.run_id)
    assert repeated.reused is True
    assert repeated.result.interrupted is True
    assert len(gateway.requests) == 1


def _continuity_repository(
    root: Path,
    *,
    running: bool = False,
) -> tuple[Phase32RunRepository, GraphRunDefinition]:
    definition = _continuity_acceptance_definition()
    repository = Phase32RunRepository(root)
    record = repository.create(definition, updated_at=definition.created_at)
    if running:
        stage_status = dict(record.state.stage_status)
        stage_status[record.state.active_stage_id] = "running"
        repository.commit_projection(
            definition.run_id,
            state=record.state.model_copy(
                update={"status": "running", "stage_status": stage_status}
            ),
            read_model=record.read_model.model_copy(
                update={"status": "running", "stage_status": stage_status}
            ),
        )
    return repository, definition


def _expired_admission_error(definition) -> Phase32ProviderReadinessAdmissionError:
    return Phase32ProviderReadinessAdmissionError(
        Phase32ProviderReadinessAdmissionVerdict(
            run_id=definition.run_id,
            definition_digest=definition.definition_digest,
            policy_digest="a" * 64,
            admission_ref="p32-provider-readiness-" + "b" * 64,
            observed_at="2026-09-05T08:00:00+00:00",
            expires_at="2026-09-05T08:15:00+00:00",
            ready=False,
            issue_codes=("readiness_admission_expired",),
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("running", (False, True), ids=("created", "running"))
async def test_continuity_start_without_admission_fails_before_driver_creation(
    tmp_path: Path,
    running: bool,
) -> None:
    repository, definition = _continuity_repository(
        tmp_path / ("running" if running else "created"),
        running=running,
    )
    driver_calls: list[str] = []

    def driver_factory(current_definition):
        driver_calls.append(current_definition.run_id)
        return FakeRouteDriver()

    service = Phase32RunExecutionService(
        repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=driver_factory,
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
    )

    with pytest.raises(Phase32RunAdmissionRequired):
        await service.start(definition.run_id)
    assert driver_calls == []


@pytest.mark.asyncio
async def test_continuity_expired_callback_fails_before_driver_creation(
    tmp_path: Path,
) -> None:
    repository, definition = _continuity_repository(tmp_path / "runtime")
    expired = _expired_admission_error(definition)
    callback_calls: list[str] = []
    driver_calls: list[str] = []

    def require_admission(current_definition):
        callback_calls.append(current_definition.definition_digest)
        raise expired

    def driver_factory(current_definition):
        driver_calls.append(current_definition.run_id)
        return FakeRouteDriver()

    service = Phase32RunExecutionService(
        repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=driver_factory,
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
        run_admission=require_admission,
    )

    with pytest.raises(Phase32ProviderReadinessAdmissionError) as captured:
        await service.start(definition.run_id)
    assert captured.value is expired
    assert callback_calls == [definition.definition_digest]
    assert driver_calls == []


@pytest.mark.asyncio
async def test_production_run_does_not_enter_private_admission_gate(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="production-admission-bypass",
        project_id="production-admission-bypass-project",
        creative_intent="普通生产 Run 保持既有执行行为。",
    )
    callback_calls: list[str] = []

    def private_admission(current_definition):
        callback_calls.append(current_definition.run_id)
        raise AssertionError("Production must not enter the private acceptance gate")

    service = Phase32RunExecutionService(
        fixture.repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=lambda _definition: FakeRouteDriver(),
        decisions=Phase32DecisionReceiptStore(tmp_path / "decisions"),
        run_admission=private_admission,
    )

    started = await service.start(fixture.definition.run_id)
    assert started.result.interrupted is True
    assert callback_calls == []


@pytest.mark.asyncio
async def test_admission_runs_only_for_real_step_and_resume_stops_before_new_driver(
    tmp_path: Path,
) -> None:
    repository, definition = _continuity_repository(tmp_path / "runtime")
    decisions = Phase32DecisionReceiptStore(tmp_path / "decisions")
    order: list[str] = []
    expired = _expired_admission_error(definition)
    reject = False

    def require_admission(_definition):
        nonlocal reject
        order.append("admission")
        if reject:
            raise expired

    def driver_factory(_definition):
        order.append("driver")
        return FakeRouteDriver()

    service = Phase32RunExecutionService(
        repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=driver_factory,
        decisions=decisions,
        run_admission=require_admission,
    )

    started = await service.start(definition.run_id)
    assert started.result.interrupted is True
    assert order == ["admission", "driver"]

    reject = True
    frontier_replay = await service.start(definition.run_id)
    assert frontier_replay.reused is True
    assert order == ["admission", "driver"]

    decision = started.result.decision
    assert decision is not None
    command = Phase32DecisionCommand(
        decision_id=str(decision["decision_id"]),
        action="accept",
        domain_revision=int(decision["domain_revision"]),
    )
    with pytest.raises(Phase32ProviderReadinessAdmissionError):
        await service.resume(definition.run_id, command)
    assert order == ["admission", "driver", "admission"]

    operation_key = f"decision:{command.decision_id}"
    decisions.succeed(
        run_id=definition.run_id,
        operation_key=operation_key,
        result={"status": "awaiting_decision"},
    )
    replay = await service.resume(definition.run_id, command)
    assert replay.reused is True
    assert order == ["admission", "driver", "admission"]


@pytest.mark.asyncio
async def test_pending_decision_reconciliation_is_local_when_admission_expired(
    tmp_path: Path,
) -> None:
    repository, definition = _continuity_repository(tmp_path / "runtime")
    current = repository.read(definition.run_id)
    repository.commit_projection(
        definition.run_id,
        state=current.state.model_copy(update={"status": "cancelled"}),
        read_model=current.read_model.model_copy(update={"status": "cancelled"}),
    )
    decisions = Phase32DecisionReceiptStore(tmp_path / "decisions")
    command = Phase32DecisionCommand(
        decision_id="locally-consumed-decision",
        action="accept",
        domain_revision=0,
    )
    operation_key = f"decision:{command.decision_id}"
    decisions.begin(
        run_id=definition.run_id,
        operation_key=operation_key,
        decision_id=command.decision_id,
        command=command.model_dump(mode="json"),
    )
    callback_calls: list[str] = []
    driver_calls: list[str] = []

    def reject_admission(current_definition):
        callback_calls.append(current_definition.run_id)
        raise _expired_admission_error(current_definition)

    def driver_factory(current_definition):
        driver_calls.append(current_definition.run_id)
        return FakeRouteDriver()

    service = Phase32RunExecutionService(
        repository,
        checkpoint_root=tmp_path / "checkpoints",
        driver_factory=driver_factory,
        decisions=decisions,
        run_admission=reject_admission,
    )

    terminal_replay = await service.start(definition.run_id)
    assert terminal_replay.reused is True
    with pytest.raises(Phase32ExecutionConflict, match="different command"):
        await service.resume(
            definition.run_id,
            Phase32DecisionCommand(
                decision_id=command.decision_id,
                action="cancel",
                domain_revision=command.domain_revision,
            ),
        )
    assert decisions.read(definition.run_id, operation_key).status == "pending"
    reconciled = await service.resume(definition.run_id, command)
    assert reconciled.reused is True
    assert decisions.read(definition.run_id, operation_key).status == "succeeded"
    assert callback_calls == []
    assert driver_calls == []
