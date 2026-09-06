from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.api.routes.artifact_amendments import router as amendment_router
from novel_workflow.api.routes.runs import router as runs_router
from novel_workflow.orchestration.phase32_artifact_amendment import (
    Phase32ArtifactAmendmentBlocked,
    Phase32ArtifactAmendmentConflict,
    Phase32ArtifactAmendmentService,
)
from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32GraphExecutionService,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.orchestration.phase32_run_preflight import (
    Phase32PreflightError,
    Phase32RunPreflight,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    CoverArtifact,
    SceneDeckArtifact,
    SceneDeckScene,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32ProviderResponse,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.storage.phase32_artifact_amendment_store import (
    Phase32ArtifactAmendmentStore,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)
from tests.test_phase32_driver import _FixtureGateway


class _TwoSceneGateway(_FixtureGateway):
    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        if request.stage_id == "scene_deck":
            self.requests.append(request)
            return Phase32ProviderResponse(
                payload=SceneDeckArtifact(
                    scenes=(
                        SceneDeckScene(
                            scene_ref="scene-1",
                            heading="INT. 档案室 - NIGHT",
                            location_and_time="市档案馆，闭馆前十分钟",
                            cast_subject_refs=("maya",),
                            visible_goal="找到被调换的签名页。",
                            opposition="保安要求她离开。",
                            outcome="她带走一张带水印的复印件。",
                            soft_page_target=2.5,
                        ),
                        SceneDeckScene(
                            scene_ref="scene-2",
                            heading="INT. 听证室 - DAY",
                            location_and_time="次日上午的公开听证会",
                            cast_subject_refs=("maya",),
                            visible_goal="让签名链进入公开记录。",
                            opposition="委员会拒绝接收来源不明的副本。",
                            outcome="主角提交水印与原始登记表的对应证据。",
                            soft_page_target=2.0,
                        ),
                    )
                ).model_dump(mode="json")
            )
        return await super().generate(request, binding=binding)


async def _completed_screenplay(
    root: Path,
    *,
    two_scenes: bool = False,
):
    return await _completed_route(root, SCREENPLAY_SAMPLE_ROUTE, two_scenes=two_scenes)


async def _completed_route(
    root: Path,
    route: CreationRouteSpec,
    *,
    two_scenes: bool = False,
):
    fixture = create_phase32_run_fixture(
        root / "runtime",
        route=route,
        run_id=f"amendment-{route.route_id}-run",
        project_id=f"amendment-{route.route_id}-project",
        creative_intent="验证 committed planning Artifact 正式修订。",
    )
    artifacts = Phase32ArtifactStore(root / "artifacts")
    gateway = _TwoSceneGateway({}) if two_scenes else _FixtureGateway({})
    driver = Phase32RouteDriver(
        artifacts,
        gateway,
        exports=ExportStore(root / "exports"),
    )
    execution = Phase32GraphExecutionService(fixture.repository)
    checkpointer = InMemorySaver()
    result = await execution.step(
        fixture.definition.run_id,
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
            source = artifacts.read(
                fixture.definition.run_id,
                result.decision["artifact_ref"],
            )
            cover = CoverArtifact.model_validate(source.payload)
            selected = cover.model_copy(
                update={"selected_asset_ref": cover.candidates[0].asset_ref}
            )
            resume["candidate_ref"] = artifacts.save_candidate(
                run_id=fixture.definition.run_id,
                creation_route_id=fixture.definition.creation_route_id,
                stage_id="cover",
                artifact=selected,
                source_operation_key=f"amendment-test-cover:{source.artifact_ref}",
            ).artifact_ref
        result = await execution.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume=resume,
        )
    assert result.record.state.status == "completed"
    amendments = Phase32ArtifactAmendmentStore(root / "amendments")
    return (
        fixture,
        artifacts,
        Phase32ArtifactAmendmentService(
            fixture.repository,
            artifacts,
            amendments,
        ),
        amendments,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE),
    ids=lambda route: route.route_id,
)
async def test_formal_amendment_uses_each_official_route_manifest(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    fixture, artifacts, service, _ = await _completed_route(
        tmp_path / route.route_id,
        route,
    )
    before = fixture.repository.read(fixture.definition.run_id)
    source_ref = before.read_model.artifact_refs["brief"].artifact_ref
    proposed = dict(artifacts.read(fixture.definition.run_id, source_ref).payload)
    proposed["premise"] = "一份被替换的公开记录迫使主角在截止时间前重建证据链。"
    amendment, impact, _ = service.create(
        fixture.definition.run_id,
        "brief",
        source_artifact_ref=source_ref,
        proposed_payload=proposed,
        idempotency_key=f"create-{route.route_id}",
    )
    assert impact.restart_from_stage_scope == fixture.definition.stage_ids[1:]
    writing_stage_id = "script" if route.route_id == "screenplay_sample" else "text"
    accepted_before = before.state.sequential_stage_progress[writing_stage_id]

    outcome = service.apply(
        fixture.definition.run_id,
        amendment.amendment_id,
        scope="restart_from_stage",
        idempotency_key=f"apply-{route.route_id}",
    )
    after = fixture.repository.read(fixture.definition.run_id)
    assert outcome.receipt.committed_artifact_ref == (
        after.read_model.artifact_refs["brief"].artifact_ref
    )
    assert after.state.stale_stage_ids == fixture.definition.stage_ids[1:]
    assert after.state.historical_frozen_stage_ids == (writing_stage_id,)
    assert after.state.sequential_stage_progress[writing_stage_id] == accepted_before


@pytest.mark.asyncio
async def test_amendment_applies_new_version_preserves_prefix_and_blocks_preflight(
    tmp_path: Path,
) -> None:
    fixture, artifacts, service, _ = await _completed_screenplay(tmp_path)
    before = fixture.repository.read(fixture.definition.run_id)
    source_ref = before.read_model.artifact_refs["brief"].artifact_ref
    source = artifacts.read(fixture.definition.run_id, source_ref)
    proposed = dict(source.payload)
    proposed["premise"] = "记者必须在公开听证前复原被替换的签名链。"

    amendment, impact, reused = service.create(
        fixture.definition.run_id,
        "brief",
        source_artifact_ref=source_ref,
        proposed_payload=proposed,
        idempotency_key="create-brief-amendment",
        author_note="把调查时限前置到公开听证。",
    )
    assert reused is False
    assert impact.affected_only_scope == (
        "cast",
        "beat_board",
        "scene_deck",
        "script",
        "export",
    )
    assert [target.stage_id for target in impact.historical_frozen] == ["script"]
    assert impact.blocked_references == ()
    replayed_create = service.create(
        fixture.definition.run_id,
        "brief",
        source_artifact_ref=source_ref,
        proposed_payload=proposed,
        idempotency_key="create-brief-amendment",
        author_note="把调查时限前置到公开听证。",
    )
    assert replayed_create[2] is True
    conflicting_payload = dict(proposed)
    conflicting_payload["premise"] = "另一份互斥的修订命令。"
    with pytest.raises(Phase32ArtifactAmendmentConflict, match="idempotency"):
        service.create(
            fixture.definition.run_id,
            "brief",
            source_artifact_ref=source_ref,
            proposed_payload=conflicting_payload,
            idempotency_key="create-brief-amendment",
            author_note="把调查时限前置到公开听证。",
        )

    outcome = service.apply(
        fixture.definition.run_id,
        amendment.amendment_id,
        scope="affected_only",
        idempotency_key="apply-brief-amendment",
    )
    assert outcome.reused is False
    after = fixture.repository.read(fixture.definition.run_id)
    assert after.state.status == "needs_action"
    assert after.state.domain_revision == before.state.domain_revision + 1
    assert after.state.active_amendment_id == amendment.amendment_id
    assert after.state.stale_stage_ids == impact.affected_only_scope
    assert after.state.historical_frozen_stage_ids == ("script",)
    assert after.state.sequential_stage_progress == before.state.sequential_stage_progress
    new_ref = after.read_model.artifact_refs["brief"].artifact_ref
    assert new_ref == outcome.receipt.committed_artifact_ref
    assert new_ref != source_ref
    assert artifacts.read(fixture.definition.run_id, source_ref).payload == source.payload
    assert artifacts.read(fixture.definition.run_id, new_ref).payload == proposed

    with pytest.raises(Phase32PreflightError) as exc:
        Phase32RunPreflight().validate(
            after.definition,
            state=after.state,
            read_model=after.read_model,
        )
    assert exc.value.code == "stale_artifact_execution_blocked"

    replay = service.apply(
        fixture.definition.run_id,
        amendment.amendment_id,
        scope="affected_only",
        idempotency_key="apply-brief-amendment",
    )
    assert replay.reused is True
    assert replay.receipt == outcome.receipt
    with pytest.raises(Phase32ArtifactAmendmentConflict, match="scope"):
        service.apply(
            fixture.definition.run_id,
            amendment.amendment_id,
            scope="restart_from_stage",
            idempotency_key="apply-brief-amendment-other-scope",
        )
    assert fixture.repository.read(fixture.definition.run_id).state.domain_revision == (
        after.state.domain_revision
    )


@pytest.mark.asyncio
async def test_amendment_blocks_removing_scene_used_by_accepted_script(
    tmp_path: Path,
) -> None:
    fixture, artifacts, service, _ = await _completed_screenplay(
        tmp_path,
        two_scenes=True,
    )
    record = fixture.repository.read(fixture.definition.run_id)
    source_ref = record.read_model.artifact_refs["scene_deck"].artifact_ref
    source = artifacts.read(fixture.definition.run_id, source_ref)
    proposed = dict(source.payload)
    proposed["scenes"] = [source.payload["scenes"][0]]
    dangling = dict(source.payload)
    dangling["scenes"] = [
        {**source.payload["scenes"][0], "cast_subject_refs": ["unknown-subject"]},
        source.payload["scenes"][1],
    ]
    with pytest.raises(Phase32ArtifactAmendmentConflict, match="committed Cast"):
        service.create(
            fixture.definition.run_id,
            "scene_deck",
            source_artifact_ref=source_ref,
            proposed_payload=dangling,
            idempotency_key="dangling-scene-cast",
        )

    amendment, impact, _ = service.create(
        fixture.definition.run_id,
        "scene_deck",
        source_artifact_ref=source_ref,
        proposed_payload=proposed,
        idempotency_key="remove-accepted-scene",
    )
    assert {item.reference for item in impact.blocked_references} == {"scene-2"}
    assert {item.referenced_stage_id for item in impact.blocked_references} == {
        "script",
        "export",
    }
    script_blocker = next(
        item
        for item in impact.blocked_references
        if item.referenced_stage_id == "script"
    )
    assert script_blocker.unit_ref == "scene-2"
    with pytest.raises(Phase32ArtifactAmendmentBlocked):
        service.apply(
            fixture.definition.run_id,
            amendment.amendment_id,
            scope="affected_only",
            idempotency_key="apply-remove-accepted-scene",
        )
    unchanged = fixture.repository.read(fixture.definition.run_id)
    assert unchanged.state.status == "completed"
    assert unchanged.read_model.artifact_refs["scene_deck"].artifact_ref == source_ref


@pytest.mark.asyncio
async def test_amendment_recovers_receipt_after_projection_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, artifacts, service, store = await _completed_screenplay(tmp_path)
    record = fixture.repository.read(fixture.definition.run_id)
    source_ref = record.read_model.artifact_refs["brief"].artifact_ref
    proposed = dict(artifacts.read(fixture.definition.run_id, source_ref).payload)
    proposed["audience_promise"] = "观众会看到证据公开和个人代价同时发生。"
    amendment, _, _ = service.create(
        fixture.definition.run_id,
        "brief",
        source_artifact_ref=source_ref,
        proposed_payload=proposed,
        idempotency_key="recovery-create",
    )
    original_complete = store.complete_apply

    def interrupt_after_projection(_receipt):
        raise RuntimeError("simulated receipt interruption")

    monkeypatch.setattr(store, "complete_apply", interrupt_after_projection)
    with pytest.raises(RuntimeError, match="receipt interruption"):
        service.apply(
            fixture.definition.run_id,
            amendment.amendment_id,
            scope="restart_from_stage",
            idempotency_key="recovery-apply",
        )
    projected = fixture.repository.read(fixture.definition.run_id)
    assert projected.state.active_amendment_id == amendment.amendment_id
    assert store.receipt_for_amendment(fixture.definition.run_id, amendment.amendment_id) is None

    monkeypatch.setattr(store, "complete_apply", original_complete)
    recovered = service.apply(
        fixture.definition.run_id,
        amendment.amendment_id,
        scope="restart_from_stage",
        idempotency_key="recovery-apply",
    )
    assert recovered.reused is True
    assert recovered.receipt.domain_revision_after == projected.state.domain_revision


@pytest.mark.asyncio
async def test_amendment_rejects_non_planning_and_stale_source(
    tmp_path: Path,
) -> None:
    fixture, artifacts, service, _ = await _completed_screenplay(tmp_path)
    record = fixture.repository.read(fixture.definition.run_id)
    script_progress = record.read_model.sequential_stage_progress["script"]
    script_ref = script_progress.committed_artifact_refs["scene-1"]
    with pytest.raises(Phase32ArtifactAmendmentConflict, match="planning"):
        service.create(
            fixture.definition.run_id,
            "script",
            source_artifact_ref=script_ref,
            proposed_payload=artifacts.read(
                fixture.definition.run_id,
                script_ref,
            ).payload,
            idempotency_key="script-is-not-planning",
        )
    brief_ref = record.read_model.artifact_refs["brief"].artifact_ref
    proposed = dict(artifacts.read(fixture.definition.run_id, brief_ref).payload)
    proposed["tone"] = "冷峻、克制、以公开证据推进"
    scale_drift = dict(proposed)
    scale_drift["target_minutes"] = 99
    with pytest.raises(ValueError, match="Artifact payload"):
        service.create(
            fixture.definition.run_id,
            "brief",
            source_artifact_ref=brief_ref,
            proposed_payload=scale_drift,
            idempotency_key="frozen-scale-drift",
        )
    with pytest.raises(Phase32ArtifactAmendmentConflict, match="current committed"):
        service.create(
            fixture.definition.run_id,
            "brief",
            source_artifact_ref="p32-brief-committed-" + "0" * 64,
            proposed_payload=proposed,
            idempotency_key="stale-source",
        )


@pytest.mark.asyncio
async def test_amendment_http_adapter_uses_server_impact_and_returns_latest_run(
    tmp_path: Path,
) -> None:
    fixture, artifacts, service, _ = await _completed_screenplay(tmp_path)
    record = fixture.repository.read(fixture.definition.run_id)
    source_ref = record.read_model.artifact_refs["brief"].artifact_ref
    proposed = dict(artifacts.read(fixture.definition.run_id, source_ref).payload)
    proposed["visible_conflict"] = "主角必须在听证开始前证明签名页被替换。"
    app = FastAPI()
    app.include_router(runs_router)
    app.include_router(amendment_router)
    app.state.phase32_artifact_amendment_service = service
    app.state.phase32_run_repository = fixture.repository
    app.state.phase32_history_projection = Phase32HistoryProjection(fixture.repository)

    with TestClient(app) as client:
        invented_impact = client.post(
            f"/api/runs/{fixture.definition.run_id}/planning/brief/amendments",
            json={
                "source_artifact_ref": source_ref,
                "proposed_payload": proposed,
                "idempotency_key": "http-create-invalid",
                "stale_stage_ids": ["export"],
            },
        )
        assert invented_impact.status_code == 422

        created = client.post(
            f"/api/runs/{fixture.definition.run_id}/planning/brief/amendments",
            json={
                "source_artifact_ref": source_ref,
                "proposed_payload": proposed,
                "idempotency_key": "http-create",
            },
        )
        assert created.status_code == 200
        body = created.json()
        amendment_id = body["amendment"]["amendment_id"]
        assert body["impact"]["affected_only_scope"][-1] == "export"

        impact = client.get(
            f"/api/runs/{fixture.definition.run_id}/planning/amendments/"
            f"{amendment_id}/impact"
        )
        assert impact.status_code == 200
        assert impact.json()["impact"] == body["impact"]

        applied = client.post(
            f"/api/runs/{fixture.definition.run_id}/planning/amendments/"
            f"{amendment_id}/apply",
            json={
                "scope": "affected_only",
                "idempotency_key": "http-apply",
            },
        )
        assert applied.status_code == 200
        applied_body = applied.json()
        assert applied_body["run"]["read_model"]["status"] == "needs_action"
        assert applied_body["run"]["read_model"]["active_amendment_id"] == amendment_id
