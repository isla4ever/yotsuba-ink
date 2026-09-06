from __future__ import annotations

import json
from pathlib import Path

import pytest

from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32GraphExecutionService,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.output_contracts.phase32_delivery_artifacts import ChapterArtifact
from novel_workflow.output_contracts.phase32_route_artifacts import (
    BookArchitectureArtifact,
    CharacterBibleArtifact,
    DetailPlanIndexArtifact,
    NovelBriefArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.runtime.graph.phase32_driver import (
    Phase32DriverError,
    Phase32RouteDriver,
)
from novel_workflow.runtime.graph.phase32_provider_input import (
    compile_phase32_stage_context,
)
from novel_workflow.runtime.graph.route_run_state import (
    SequentialStageProgress,
    initial_route_run_state,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.route_run_read_model import (
    ArtifactRefProjection,
    initial_route_run_read_model,
)
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_specs import LONG_NOVEL_ROUTE
from tests.test_phase32_driver import (
    FakePhase32Gateway,
    _RecordingTextOperationAdmission,
    _FixtureGateway,
    _continuity_acceptance_definition,
    _definition,
    _payload_for,
    _rolling_detail_payload_with_chapter_count,
)


def test_long_novel_chapter_context_is_window_scoped_and_binds_previous_tail(
    tmp_path: Path,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    refs = _committed_long_novel_planning(store, definition.run_id)
    previous = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="text",
        artifact=ChapterArtifact(
            chapter_ref="chapter-1",
            volume_ref="volume-1",
            title="第一份证据",
            pov_subject_ref="maya",
            content="SHOULD-NOT-REACH-CONTEXT" + "旧正文" * 700 + "PREVIOUS-TAIL",
        ),
    )
    progress = SequentialStageProgress(
        ordered_unit_refs=("chapter-1", "chapter-2"),
        committed_artifact_refs={"chapter-1": previous.artifact_ref},
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "chapter-2",
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )

    context = compile_phase32_stage_context(
        artifact_store=store,
        definition=definition,
        state=state,
        stage=definition.stage("text"),
    )

    sequential = context["sequential_unit"]
    assert sequential["chapter_ref"] == "chapter-2"
    assert sequential["window_ref"] == "window-1"
    assert sequential["accepted_chapter_count"] == 1
    assert sequential["previous_chapter_handoff"] == "下一章追查异常封存日期。"
    assert sequential["previous_chapter_tail"].endswith("PREVIOUS-TAIL")
    assert len(sequential["previous_chapter_tail"]) <= 1_200
    assert "SHOULD-NOT-REACH-CONTEXT" not in sequential["previous_chapter_tail"]
    assert [
        item["part_ref"]
        for item in context["upstream_artifacts"]["book_architecture"]["payload"][
            "parts"
        ]
    ] == ["part-hearing"]
    assert [
        item["volume_ref"]
        for item in context["upstream_artifacts"]["volumes"]["payload"]["volumes"]
    ] == ["volume-2"]
    projected_windows = context["upstream_artifacts"]["rolling_detail"]["payload"][
        "windows"
    ]
    assert len(projected_windows) == 1
    assert [chapter["chapter_ref"] for chapter in projected_windows[0]["chapters"]] == [
        "chapter-2"
    ]
    assert "SHOULD-NOT-REACH-CONTEXT" not in json.dumps(context, ensure_ascii=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ("title", "volume_ref", "pov_subject_ref"))
async def test_long_novel_chapter_rejects_frozen_identity_drift(
    tmp_path: Path,
    field: str,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / field)
    refs = _committed_long_novel_planning(store, definition.run_id)
    payload = ChapterArtifact(
        chapter_ref="chapter-1",
        volume_ref="volume-1",
        title="第一份证据",
        pov_subject_ref="maya",
        content="正文非空。",
    ).model_dump(mode="json")
    payload[field] = {
        "title": "错误标题",
        "volume_ref": "volume-2",
        "pov_subject_ref": "ghost",
    }[field]
    progress = SequentialStageProgress(
        ordered_unit_refs=("chapter-1", "chapter-2")
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "chapter-1",
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))

    with pytest.raises(Phase32DriverError, match="frozen Rolling Detail"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("text"),
        )

    assert driver.provider_operations.list(definition.run_id)[0].status == "contract_rejected"


@pytest.mark.asyncio
async def test_long_novel_chapter_rejects_explicit_unregistered_character_name(
    tmp_path: Path,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "explicit-name")
    refs = _committed_long_novel_planning(store, definition.run_id)
    payload = ChapterArtifact(
        chapter_ref="chapter-1",
        volume_ref="volume-1",
        title="第一份证据",
        pov_subject_ref="maya",
        content="姓名：林晚。她把复印件放进证物袋。",
    ).model_dump(mode="json")
    progress = SequentialStageProgress(ordered_unit_refs=("chapter-1", "chapter-2"))
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "chapter-1",
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))

    with pytest.raises(Phase32DriverError, match="unregistered explicit character name"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("text"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    (
        "我的同事林文淇负责核对登记表。",
        "日志里的用户是陈誉，操作内容为清洁前检查。",
        "我请同事小陈复核流程记录。",
    ),
)
async def test_long_novel_chapter_rejects_role_bound_unregistered_name(
    tmp_path: Path,
    content: str,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "role-bound-name")
    refs = _committed_long_novel_planning(store, definition.run_id)
    payload = ChapterArtifact(
        chapter_ref="chapter-1",
        volume_ref="volume-1",
        title="第一份证据",
        pov_subject_ref="maya",
        content=content,
    ).model_dump(mode="json")
    progress = SequentialStageProgress(ordered_unit_refs=("chapter-1", "chapter-2"))
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "chapter-1",
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))

    with pytest.raises(Phase32DriverError, match="unregistered explicit character name"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("text"),
        )

    assert driver.provider_operations.list(definition.run_id)[0].status == "contract_rejected"


@pytest.mark.asyncio
async def test_long_novel_chapter_allows_explicit_registered_character_name(
    tmp_path: Path,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "registered-name")
    refs = _committed_long_novel_planning(store, definition.run_id)
    payload = ChapterArtifact(
        chapter_ref="chapter-1",
        volume_ref="volume-1",
        title="第一份证据",
        pov_subject_ref="maya",
        content="姓名：Maya。她把复印件放进证物袋。",
    ).model_dump(mode="json")
    progress = SequentialStageProgress(ordered_unit_refs=("chapter-1", "chapter-2"))
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "chapter-1",
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))

    candidate = await driver.generate_stage(
        definition=definition,
        state=state,
        stage=definition.stage("text"),
    )

    assert candidate.artifact_ref.startswith("p32-text-candidate-")
    assert driver.provider_operations.list(definition.run_id)[0].status == "succeeded"


@pytest.mark.asyncio
async def test_long_novel_recovers_durable_return_without_recalling_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    refs = _committed_long_novel_planning(store, definition.run_id)
    previous = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="text",
        artifact=ChapterArtifact(
            chapter_ref="chapter-1",
            volume_ref="volume-1",
            title="第一份证据",
            pov_subject_ref="maya",
            content="第一章冻结正文末尾：水印日期晚于官方封存日期。",
        ),
    )
    progress = SequentialStageProgress(
        ordered_unit_refs=("chapter-1", "chapter-2"),
        committed_artifact_refs={"chapter-1": previous.artifact_ref},
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": "chapter-2",
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    first_gateway = _FixtureGateway({})
    first_driver = Phase32RouteDriver(store, first_gateway)
    original_save_candidate = store.save_candidate
    interrupted = False

    def stop_after_provider_return(**kwargs):
        nonlocal interrupted
        if kwargs.get("stage_id") == "text" and not interrupted:
            interrupted = True
            raise RuntimeError("simulated stop after durable Provider return")
        return original_save_candidate(**kwargs)

    monkeypatch.setattr(store, "save_candidate", stop_after_provider_return)
    with pytest.raises(Phase32DriverError, match="Artifact persistence failed"):
        await first_driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("text"),
        )

    first_receipt = first_driver.provider_operations.list(definition.run_id)[0]
    assert first_receipt.status == "returned"
    assert first_receipt.transport_attempts == 1
    assert len(first_gateway.requests) == 1
    frozen_input = first_driver.provider_inputs.read(
        definition.run_id,
        first_receipt.provider_input_ref,
    )
    sequential = frozen_input.request["context"]["sequential_unit"]
    assert sequential["previous_chapter_version_ref"] == previous.artifact_ref
    assert sequential["previous_chapter_payload_digest"] == previous.payload_digest

    class ProviderMustNotRun(_FixtureGateway):
        async def generate(self, request, *, binding):
            self.requests.append(request)
            raise AssertionError("durable returned receipt must bypass Provider")

    restarted_gateway = ProviderMustNotRun({})
    restarted_store = Phase32ArtifactStore(store.root)
    restarted_driver = Phase32RouteDriver(restarted_store, restarted_gateway)
    recovered = await restarted_driver.generate_stage(
        definition=definition,
        state=state,
        stage=definition.stage("text"),
    )

    assert restarted_gateway.requests == []
    assert progress.committed_artifact_refs == {"chapter-1": previous.artifact_ref}
    recovered_receipt = restarted_driver.provider_operations.read(
        definition.run_id,
        first_receipt.operation_key,
    )
    assert recovered_receipt.status == "succeeded"
    assert recovered_receipt.transport_attempts == first_receipt.transport_attempts
    assert recovered_receipt.provider_input_ref == first_receipt.provider_input_ref
    assert recovered_receipt.request_signature == first_receipt.request_signature
    recovered_record = restarted_store.read(definition.run_id, recovered.artifact_ref)
    assert recovered_record.source_operation_key == first_receipt.operation_key
    assert recovered_record.payload["chapter_ref"] == "chapter-2"


@pytest.mark.asyncio
async def test_long_novel_reopens_sqlite_at_second_chapter_and_advances_to_cover(
    tmp_path: Path,
) -> None:
    policy = ReviewPolicy(
        policy_id="review.long_novel.chapter-recovery",
        revision="r1",
        route_id="long_novel",
        checkpoint_policy="every_unit",
        warning_policy="continue_and_surface",
        auto_continue_stages=(
            "brief",
            "book_architecture",
            "cast",
            "volumes",
            "rolling_detail",
        ),
        mandatory_decision_stages=("text", "cover"),
    )
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=LONG_NOVEL_ROUTE,
        run_id="long-chapter-two-unit-recovery",
        project_id="project-long-chapter-recovery",
        creative_intent="验证长篇正文按冻结章节顺序生成并跨进程恢复。",
        review_policy=policy,
    )
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    gateway = _FixtureGateway({})
    driver = Phase32RouteDriver(store, gateway)
    service = Phase32GraphExecutionService(fixture.repository)

    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        first = await service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )
        assert first.decision is not None
        assert first.decision["stage_id"] == "text"
        assert first.decision["unit_ref"] == "chapter-1"
        second = await service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume={
                "decision_id": first.decision["decision_id"],
                "action": "accept",
                "domain_revision": first.decision["domain_revision"],
            },
        )

    assert second.decision is not None
    assert second.decision["unit_ref"] == "chapter-2"
    progress = second.record.read_model.sequential_stage_progress["text"]
    first_ref = progress.committed_artifact_refs["chapter-1"]
    assert tuple(progress.committed_artifact_refs) == ("chapter-1",)

    reopened_repository = Phase32RunRepository(fixture.repository.root)
    reopened = reopened_repository.read(fixture.definition.run_id)
    assert reopened.read_model.active_unit_ref == "chapter-2"
    reopened_service = Phase32GraphExecutionService(reopened_repository)
    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        third = await reopened_service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume={
                "decision_id": second.decision["decision_id"],
                "action": "accept",
                "domain_revision": second.decision["domain_revision"],
            },
        )

    assert third.decision is not None
    assert third.decision["stage_id"] == "cover"
    final_progress = third.record.read_model.sequential_stage_progress["text"]
    assert final_progress.complete is True
    assert tuple(final_progress.committed_artifact_refs) == (
        "chapter-1",
        "chapter-2",
    )
    assert final_progress.committed_artifact_refs["chapter-1"] == first_ref
    text_requests = [request for request in gateway.requests if request.stage_id == "text"]
    assert len(text_requests) == 2
    second_context = text_requests[1].context["sequential_unit"]
    assert second_context["current_chapter"]["chapter_ref"] == "chapter-2"
    assert second_context["previous_chapter_tail"].endswith("的正文内容。")


@pytest.mark.asyncio
async def test_long_novel_exact_12_text_prefix_survives_store_and_driver_restarts(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    artifact_root = tmp_path / "artifacts"
    repository_root = tmp_path / "runtime"
    store = Phase32ArtifactStore(artifact_root)
    detail = DetailPlanIndexArtifact.model_validate(
        _rolling_detail_payload_with_chapter_count(12)
    )
    refs = _committed_long_novel_planning(
        store,
        definition.run_id,
        detail=detail,
    )
    brief = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="brief",
        artifact=NovelBriefArtifact.model_validate(
            _payload_for("long_novel", "brief")
        ),
    )
    refs["brief"] = brief.artifact_ref
    ordered_refs = tuple(
        chapter.chapter_ref
        for window in detail.windows
        for chapter in window.chapters
    )
    assert ordered_refs == tuple(f"chapter-{ordinal:02d}" for ordinal in range(1, 13))

    progress = SequentialStageProgress(ordered_unit_refs=ordered_refs)
    stage_status = definition.initial_stage_status()
    for stage_id in refs:
        stage_status[stage_id] = "completed"
    stage_status["text"] = "running"
    state = initial_route_run_state(definition).model_copy(
        update={
            "status": "running",
            "active_stage_id": "text",
            "active_unit_ref": progress.next_unit_ref,
            "stage_status": stage_status,
            "artifact_refs": refs,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    read_model = initial_route_run_read_model(
        definition,
        updated_at=definition.created_at,
    ).model_copy(
        update={
            "status": "running",
            "active_stage_id": "text",
            "active_unit_ref": progress.next_unit_ref,
            "stage_status": stage_status,
            "artifact_refs": {
                stage_id: ArtifactRefProjection(
                    artifact_kind=definition.stage(stage_id).artifact_kind,
                    artifact_ref=artifact_ref,
                )
                for stage_id, artifact_ref in refs.items()
            },
            "sequential_stage_progress": {"text": progress},
        }
    )
    repository = Phase32RunRepository(repository_root)
    record = repository.create(
        definition,
        state=state,
        read_model=read_model,
    )
    gateways = [_FixtureGateway({})]
    admission = _RecordingTextOperationAdmission()
    driver = Phase32RouteDriver(
        store,
        gateways[-1],
        text_operation_admission=admission,
    )
    restart_prefixes: list[dict[str, str]] = []

    for ordinal, expected_unit_ref in enumerate(ordered_refs, start=1):
        assert record.state.active_unit_ref == expected_unit_ref
        candidate = await driver.generate_stage(
            definition=definition,
            state=record.state,
            stage=definition.stage("text"),
        )
        assert candidate.unit_ref == expected_unit_ref
        await driver.validate_stage(
            definition=definition,
            state=record.state,
            stage=definition.stage("text"),
            candidate=candidate,
        )
        committed_ref = await driver.commit_stage(
            definition=definition,
            state=record.state,
            stage=definition.stage("text"),
            candidate=candidate,
        )
        progress = record.state.sequential_progress("text")
        assert progress is not None
        progress = progress.accept(expected_unit_ref, committed_ref)
        state = record.state.model_copy(
            update={
                "active_unit_ref": progress.next_unit_ref,
                "sequential_stage_progress": {
                    "text": progress.model_dump(mode="json")
                },
                "domain_revision": record.state.domain_revision + 1,
            }
        )
        read_model = record.read_model.model_copy(
            update={
                "active_unit_ref": progress.next_unit_ref,
                "sequential_stage_progress": {"text": progress},
                "updated_at": f"2026-08-26T12:{ordinal:02d}:00+08:00",
            }
        )
        record = repository.commit_projection(
            definition.run_id,
            state=state,
            read_model=read_model,
        )

        if ordinal in {4, 8}:
            frozen_prefix = dict(progress.committed_artifact_refs)
            restart_prefixes.append(frozen_prefix)
            repository = Phase32RunRepository(repository_root)
            record = repository.read(definition.run_id)
            restored = record.state.sequential_progress("text")
            assert restored is not None
            assert restored.ordered_unit_refs == ordered_refs
            assert restored.committed_artifact_refs == frozen_prefix
            store = Phase32ArtifactStore(artifact_root)
            for unit_ref, artifact_ref in frozen_prefix.items():
                accepted = store.read(definition.run_id, artifact_ref)
                assert accepted.status == "committed"
                assert accepted.payload["chapter_ref"] == unit_ref
            gateways.append(_FixtureGateway({}))
            driver = Phase32RouteDriver(
                store,
                gateways[-1],
                text_operation_admission=admission,
            )
            assert len(driver.provider_operations.list(definition.run_id)) == ordinal

    repository = Phase32RunRepository(repository_root)
    final_record = repository.read(definition.run_id)
    final_progress = final_record.state.sequential_progress("text")
    assert final_progress is not None and final_progress.complete
    assert final_progress.ordered_unit_refs == ordered_refs
    assert tuple(final_progress.committed_artifact_refs) == ordered_refs
    for frozen_prefix in restart_prefixes:
        assert tuple(frozen_prefix.items()) == tuple(
            final_progress.committed_artifact_refs.items()
        )[: len(frozen_prefix)]

    final_driver = Phase32RouteDriver(
        Phase32ArtifactStore(artifact_root),
        _FixtureGateway({}),
        text_operation_admission=admission,
    )
    receipts = final_driver.provider_operations.list(definition.run_id)
    assert len(receipts) == 12
    assert len({receipt.operation_key for receipt in receipts}) == 12
    assert all(receipt.status == "succeeded" for receipt in receipts)
    assert all(receipt.transport_attempts == 1 for receipt in receipts)
    operations_by_unit: dict[str, set[str]] = {}
    for receipt in receipts:
        frozen_input = final_driver.provider_inputs.read(
            definition.run_id,
            receipt.provider_input_ref,
        )
        unit_ref = str(frozen_input.request["context"]["active_unit_ref"])
        operations_by_unit.setdefault(unit_ref, set()).add(receipt.operation_key)
    assert tuple(sorted(operations_by_unit)) == ordered_refs
    assert all(len(operation_keys) == 1 for operation_keys in operations_by_unit.values())
    assert sum(len(gateway.requests) for gateway in gateways) == 12
    assert len(admission.admitted_requests) == 12
    assert all(gateway.image_requests == [] for gateway in gateways)


def _committed_long_novel_planning(
    store: Phase32ArtifactStore,
    run_id: str,
    *,
    detail: DetailPlanIndexArtifact | None = None,
) -> dict[str, str]:
    models = {
        "book_architecture": BookArchitectureArtifact,
        "cast": CharacterBibleArtifact,
        "volumes": VolumeArchitectureArtifact,
        "rolling_detail": DetailPlanIndexArtifact,
    }
    refs: dict[str, str] = {}
    for stage_id, model in models.items():
        artifact = (
            detail
            if stage_id == "rolling_detail" and detail is not None
            else model.model_validate(_payload_for("long_novel", stage_id))
        )
        record = store.save_deterministic(
            run_id=run_id,
            creation_route_id="long_novel",
            stage_id=stage_id,
            artifact=artifact,
        )
        refs[stage_id] = record.artifact_ref
    return refs
