from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.api.routes.artifact_amendments import router as amendment_router
from novel_workflow.orchestration.phase32_amendment_branch import (
    Phase32AmendmentBranchConflict,
    Phase32AmendmentBranchService,
)
from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32GraphExecutionService,
)
from novel_workflow.output_contracts.phase32_route_artifacts import CoverArtifact
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.phase32_amendment_branch_store import (
    Phase32AmendmentBranchIdempotencyConflict,
    Phase32AmendmentBranchStore,
)
from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.storage.phase32_project_catalog_store import (
    Phase32ProjectCatalogRecord,
    Phase32ProjectCatalogStore,
)
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)
from tests.test_phase32_artifact_amendment import _completed_route
from tests.test_phase32_driver import _FixtureGateway


NOW = "2026-08-25T06:30:00+08:00"


async def _applied_amendment(root: Path, route: CreationRouteSpec):
    fixture, artifacts, amendments, amendment_store = await _completed_route(
        root,
        route,
    )
    projects = Phase32ProjectCatalogStore(root / "projects")
    projects.register(
        Phase32ProjectCatalogRecord(
            project_id=fixture.definition.project_id,
            run_ids=(fixture.definition.run_id,),
            accent_hue=210,
            created_at=fixture.definition.created_at,
        )
    )
    branches = Phase32AmendmentBranchStore(root / "branches")
    service = Phase32AmendmentBranchService(
        fixture.repository,
        artifacts,
        amendment_store,
        branches,
        projects,
        clock=lambda: NOW,
    )
    source = fixture.repository.read(fixture.definition.run_id)
    source_ref = source.read_model.artifact_refs["brief"].artifact_ref
    proposed = dict(artifacts.read(fixture.definition.run_id, source_ref).payload)
    proposed["premise"] = f"{route.route_id} 修订后必须从新的规划分支继续。"
    amendment, _, _ = amendments.create(
        fixture.definition.run_id,
        "brief",
        source_artifact_ref=source_ref,
        proposed_payload=proposed,
        idempotency_key=f"branch-create-{route.route_id}",
    )
    applied = amendments.apply(
        fixture.definition.run_id,
        amendment.amendment_id,
        scope="restart_from_stage",
        idempotency_key=f"branch-apply-{route.route_id}",
    )
    return fixture, artifacts, projects, branches, service, amendment, applied


async def _complete_target(
    root: Path,
    target_run_id: str,
    repository,
    artifacts,
):
    gateway = _FixtureGateway({})
    driver = Phase32RouteDriver(
        artifacts,
        gateway,
        exports=ExportStore(root / "target-exports"),
    )
    execution = Phase32GraphExecutionService(repository)
    checkpointer = InMemorySaver()
    result = await execution.step(
        target_run_id,
        driver=driver,
        checkpointer=checkpointer,
    )
    while result.interrupted:
        assert result.decision is not None
        resume = {
            "decision_id": result.decision["decision_id"],
            "action": "accept",
            "domain_revision": result.decision["domain_revision"],
        }
        if result.decision["stage_id"] == "cover":
            source = artifacts.read(target_run_id, result.decision["artifact_ref"])
            cover = CoverArtifact.model_validate(source.payload)
            selected = cover.model_copy(
                update={"selected_asset_ref": cover.candidates[0].asset_ref}
            )
            resume["candidate_ref"] = artifacts.save_candidate(
                run_id=target_run_id,
                creation_route_id=result.record.definition.creation_route_id,
                stage_id="cover",
                artifact=selected,
                source_operation_key=f"branch-test-cover:{source.artifact_ref}",
            ).artifact_ref
        result = await execution.step(
            target_run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume=resume,
        )
    first_provider_stage_id = gateway.requests[0].stage_id if gateway.requests else ""
    return result, gateway, first_provider_stage_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE),
    ids=lambda route: route.route_id,
)
async def test_amendment_branch_preserves_source_and_completes_each_route(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    root = tmp_path / route.route_id
    fixture, artifacts, projects, _, service, amendment, applied = (
        await _applied_amendment(root, route)
    )
    source_before = fixture.repository.read(fixture.definition.run_id)
    writing_stage_id = "script" if route.route_id == "screenplay_sample" else "text"
    accepted_prefix = source_before.state.sequential_stage_progress[writing_stage_id]

    outcome = service.branch(
        fixture.definition.run_id,
        amendment.amendment_id,
        apply_receipt_id=applied.receipt.receipt_id,
        source_domain_revision=source_before.state.domain_revision,
        idempotency_key=f"branch-{route.route_id}",
    )
    target = outcome.target
    expected_frontier = fixture.definition.stage_ids[1]
    assert outcome.reused is False
    assert target.state.status == "created"
    assert target.state.active_stage_id == expected_frontier
    assert target.state.artifact_refs == {
        "brief": source_before.state.artifact_refs["brief"]
    }
    assert target.state.sequential_stage_progress == {}
    assert artifacts.list(target.definition.run_id, stage_id=writing_stage_id) == []
    assert projects.get(fixture.definition.project_id).run_ids == (
        fixture.definition.run_id,
        target.definition.run_id,
    )

    completed, gateway, first_provider_stage_id = await _complete_target(
        root,
        target.definition.run_id,
        fixture.repository,
        artifacts,
    )
    assert first_provider_stage_id == expected_frontier
    assert completed.record.state.status == "completed"
    assert all(request.stage_id != "brief" for request in gateway.requests)
    source_after = fixture.repository.read(fixture.definition.run_id)
    assert source_after.state.status == "needs_action"
    assert source_after.state.sequential_stage_progress[writing_stage_id] == accepted_prefix
    assert any(
        event.type == "run.branched" and event.status == "amendment_branched"
        for event in fixture.repository.events(fixture.definition.run_id)
    )
    assert any(
        event.type == "run.branched" and event.status == "amendment_branch_seeded"
        for event in fixture.repository.events(target.definition.run_id)
    )


@pytest.mark.asyncio
async def test_amendment_branch_is_idempotent_and_recovers_after_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, projects, branches, service, amendment, applied = (
        await _applied_amendment(tmp_path, SCREENPLAY_SAMPLE_ROUTE)
    )
    source = fixture.repository.read(fixture.definition.run_id)
    original_complete = branches.complete

    def stop_before_receipt(_receipt):
        raise RuntimeError("simulated branch receipt interruption")

    monkeypatch.setattr(branches, "complete", stop_before_receipt)
    with pytest.raises(RuntimeError, match="receipt interruption"):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id=applied.receipt.receipt_id,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="recover-branch",
        )
    target_run_id = projects.get(fixture.definition.project_id).run_ids[-1]
    assert target_run_id != fixture.definition.run_id
    assert branches.receipt_for_amendment(
        fixture.definition.run_id,
        amendment.amendment_id,
    ) is None

    projects.append_run(
        fixture.definition.project_id,
        source_run_id=target_run_id,
        target_run_id="run-created-after-amendment-successor",
    )

    monkeypatch.setattr(branches, "complete", original_complete)
    recovered = service.branch(
        fixture.definition.run_id,
        amendment.amendment_id,
        apply_receipt_id=applied.receipt.receipt_id,
        source_domain_revision=source.state.domain_revision,
        idempotency_key="recover-branch",
    )
    assert recovered.receipt.target_run_id == target_run_id
    assert projects.get(fixture.definition.project_id).run_ids == (
        fixture.definition.run_id,
        target_run_id,
        "run-created-after-amendment-successor",
    )
    replay = service.branch(
        fixture.definition.run_id,
        amendment.amendment_id,
        apply_receipt_id=applied.receipt.receipt_id,
        source_domain_revision=source.state.domain_revision,
        idempotency_key="recover-branch",
    )
    assert replay.reused is True
    assert replay.receipt == recovered.receipt
    assert sum(
        event.type == "run.branched"
        for event in fixture.repository.events(fixture.definition.run_id)
    ) == 1
    assert sum(
        event.type == "run.branched"
        for event in fixture.repository.events(target_run_id)
    ) == 1
    with pytest.raises(Phase32AmendmentBranchConflict):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id="p32-amendment-receipt-" + "0" * 32,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="recover-branch",
        )


@pytest.mark.asyncio
async def test_amendment_branch_rejects_a_second_plan_with_another_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, _, branches, service, amendment, applied = await _applied_amendment(
        tmp_path,
        SHORT_NOVEL_ROUTE,
    )
    source = fixture.repository.read(fixture.definition.run_id)
    original_materialize = service._materialize

    def stop_after_plan(_plan):
        raise RuntimeError("simulated interruption after branch plan")

    monkeypatch.setattr(service, "_materialize", stop_after_plan)
    with pytest.raises(RuntimeError, match="after branch plan"):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id=applied.receipt.receipt_id,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="first-branch-plan",
        )
    assert branches.find_plan_for_amendment(
        fixture.definition.run_id,
        amendment.amendment_id,
    ) is not None

    monkeypatch.setattr(service, "_materialize", original_materialize)
    with pytest.raises(
        Phase32AmendmentBranchIdempotencyConflict,
        match="another successor Run plan",
    ):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id=applied.receipt.receipt_id,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="second-branch-plan",
        )
    recovered = service.branch(
        fixture.definition.run_id,
        amendment.amendment_id,
        apply_receipt_id=applied.receipt.receipt_id,
        source_domain_revision=source.state.domain_revision,
        idempotency_key="first-branch-plan",
    )
    assert recovered.receipt.target_run_id == recovered.target.definition.run_id


@pytest.mark.asyncio
async def test_completed_branch_rejects_project_lineage_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, projects, _, service, amendment, applied = await _applied_amendment(
        tmp_path,
        SCREENPLAY_SAMPLE_ROUTE,
    )
    source = fixture.repository.read(fixture.definition.run_id)
    outcome = service.branch(
        fixture.definition.run_id,
        amendment.amendment_id,
        apply_receipt_id=applied.receipt.receipt_id,
        source_domain_revision=source.state.domain_revision,
        idempotency_key="lineage-drift",
    )
    project = projects.get(fixture.definition.project_id)
    monkeypatch.setattr(
        projects,
        "get",
        lambda _project_id: project.model_copy(
            update={"run_ids": (fixture.definition.run_id,)}
        ),
    )

    with pytest.raises(Phase32AmendmentBranchConflict, match="Project lineage"):
        service.receipt(fixture.definition.run_id, amendment.amendment_id)
    with pytest.raises(Phase32AmendmentBranchConflict, match="Project lineage"):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id=applied.receipt.receipt_id,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="lineage-drift",
        )
    assert outcome.target.definition.run_id == project.run_ids[-1]


@pytest.mark.asyncio
async def test_amendment_branch_rejects_unbound_or_superseded_source(
    tmp_path: Path,
) -> None:
    fixture, _, projects, _, service, amendment, applied = await _applied_amendment(
        tmp_path,
        LONG_NOVEL_ROUTE,
    )
    source = fixture.repository.read(fixture.definition.run_id)
    with pytest.raises(Phase32AmendmentBranchConflict, match="stale amendment frontier"):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id=applied.receipt.receipt_id,
            source_domain_revision=source.state.domain_revision - 1,
            idempotency_key="wrong-revision",
        )
    with pytest.raises(Phase32AmendmentBranchConflict, match="apply receipt"):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id="p32-amendment-receipt-" + "0" * 32,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="wrong-receipt",
        )

    projects.append_run(
        fixture.definition.project_id,
        source_run_id=fixture.definition.run_id,
        target_run_id="run-superseding-amendment-source",
    )
    with pytest.raises(Phase32AmendmentBranchConflict, match="latest Run"):
        service.branch(
            fixture.definition.run_id,
            amendment.amendment_id,
            apply_receipt_id=applied.receipt.receipt_id,
            source_domain_revision=source.state.domain_revision,
            idempotency_key="superseded-source",
        )


@pytest.mark.asyncio
async def test_amendment_branch_api_rejects_client_target_and_restores_receipt(
    tmp_path: Path,
) -> None:
    fixture, _, _, _, service, amendment, applied = await _applied_amendment(
        tmp_path,
        SHORT_NOVEL_ROUTE,
    )
    source = fixture.repository.read(fixture.definition.run_id)
    app = FastAPI()
    app.include_router(amendment_router)
    app.state.phase32_amendment_branch_service = service
    app.state.phase32_run_repository = fixture.repository
    app.state.phase32_history_projection = Phase32HistoryProjection(fixture.repository)

    payload = {
        "apply_receipt_id": applied.receipt.receipt_id,
        "source_domain_revision": source.state.domain_revision,
        "idempotency_key": "branch-http",
    }
    path = (
        f"/api/runs/{fixture.definition.run_id}/planning/amendments/"
        f"{amendment.amendment_id}/branch"
    )
    with TestClient(app) as client:
        invented = client.post(path, json={**payload, "target_run_id": "client-run"})
        assert invented.status_code == 422
        pending = client.get(path)
        assert pending.status_code == 200
        assert pending.json()["apply_receipt"] == applied.receipt.model_dump(mode="json")
        assert pending.json()["receipt"] is None
        assert pending.json()["target_run"] is None
        created = client.post(path, json=payload)
        assert created.status_code == 200
        body = created.json()
        assert body["source_run"]["read_model"]["status"] == "needs_action"
        assert body["target_run"]["read_model"]["status"] == "created"
        restored = client.get(path)
        assert restored.status_code == 200
        assert restored.json()["apply_receipt"] == applied.receipt.model_dump(mode="json")
        assert restored.json()["receipt"] == body["receipt"]
        assert restored.json()["target_run"] == body["target_run"]
