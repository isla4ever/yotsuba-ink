from __future__ import annotations

from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32GraphExecutionService,
)
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.runtime.graph.route_graph import RouteStageCandidate
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)
from tests.test_phase32_route_graph import SequentialWritebackRecoveryDriver, _definition


class _Driver:
    async def generate_stage(self, *, stage, **kwargs):
        return RouteStageCandidate(artifact_ref=f"candidate:{stage.stage_id}")

    async def validate_stage(self, **kwargs):
        return None

    async def commit_stage(self, *, stage, **kwargs):
        return f"artifact:{stage.stage_id}"


class _SequentialScriptDriver(_Driver):
    scene_refs = ("scene-1", "scene-2", "scene-3")

    def sequential_unit_refs(self, *, stage, **kwargs):
        return self.scene_refs if stage.stage_id == "script" else ()

    async def generate_stage(self, *, stage, state, **kwargs):
        unit_ref = state.active_unit_ref if stage.stage_id == "script" else ""
        return RouteStageCandidate(
            artifact_ref=f"candidate:{stage.stage_id}:{unit_ref or 'aggregate'}",
            unit_ref=unit_ref,
        )

    async def commit_stage(self, *, stage, candidate, **kwargs):
        suffix = f":{candidate.unit_ref}" if candidate.unit_ref else ""
        return f"artifact:{stage.stage_id}{suffix}"


class _LongNovelSequentialDriver(_Driver):
    def sequential_unit_refs(self, *, stage, **kwargs):
        return ("chapter_01", "chapter_02") if stage.stage_id == "text" else ()

    async def generate_stage(self, *, stage, state, **kwargs):
        unit_ref = state.active_unit_ref if stage.stage_id == "text" else ""
        return RouteStageCandidate(
            artifact_ref=f"candidate:{stage.stage_id}:{unit_ref or 'aggregate'}",
            unit_ref=unit_ref,
        )

    async def commit_stage(self, *, stage, candidate, **kwargs):
        suffix = f":{candidate.unit_ref}" if candidate.unit_ref else ""
        return f"artifact:{stage.stage_id}{suffix}"


def _fixture(tmp_path: Path):
    return create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SHORT_NOVEL_ROUTE,
        run_id="execution-short-novel",
        project_id="project-execution",
        creative_intent="验证图执行结果会回写原生 read model。",
    )


@pytest.mark.asyncio
async def test_graph_step_projects_decision_and_checkpoint_to_native_read_model(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    service = Phase32GraphExecutionService(fixture.repository)

    result = await service.step(
        fixture.definition.run_id,
        driver=_Driver(),
        checkpointer=InMemorySaver(),
    )

    assert result.interrupted is True
    assert result.decision is not None
    assert result.decision["stage_id"] == "brief"
    assert result.record.state.status == "awaiting_decision"
    assert result.record.read_model.status == "awaiting_decision"
    assert result.record.read_model.active_stage_id == "brief"
    assert result.record.read_model.pending_decisions[0].decision_id == result.decision["decision_id"]
    assert result.record.read_model.pending_decisions[0].domain_revision == 0
    assert result.record.read_model.pending_decisions[0].allowed_actions == tuple(
        result.decision["allowed_actions"]
    )
    assert result.record.read_model.checkpoint_id
    assert result.record.read_model.stage_status["brief"] == "awaiting_decision"


@pytest.mark.asyncio
async def test_graph_steps_resume_from_same_checkpointer_until_export(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    service = Phase32GraphExecutionService(fixture.repository)
    checkpointer = InMemorySaver()

    result = await service.step(
        fixture.definition.run_id,
        driver=_Driver(),
        checkpointer=checkpointer,
    )
    decisions = 0
    while result.interrupted:
        assert result.decision is not None
        result = await service.step(
            fixture.definition.run_id,
            driver=_Driver(),
            checkpointer=checkpointer,
            resume={
                "decision_id": result.decision["decision_id"],
                "action": "accept",
                "domain_revision": result.decision["domain_revision"],
            },
        )
        decisions += 1

    restored = Phase32RunRepository(fixture.repository.root).read(fixture.definition.run_id)
    assert decisions >= 2
    assert result.record.state.status == "completed"
    assert restored.read_model.status == "completed"
    assert restored.read_model.active_stage_id == "export"
    assert restored.read_model.pending_decisions == ()
    assert any(event.type == "export.ready" for event in fixture.repository.events(fixture.definition.run_id))


@pytest.mark.asyncio
async def test_canonical_short_route_projects_image_deferred_and_never_exports(
    tmp_path: Path,
) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, workflow_id="official.short_novel")
    repository = Phase32RunRepository(tmp_path / "runtime")
    repository.create(definition, updated_at=definition.created_at)
    service = Phase32GraphExecutionService(repository)
    checkpointer = InMemorySaver()

    result = await service.step(
        definition.run_id,
        driver=_Driver(),
        checkpointer=checkpointer,
    )
    while result.interrupted:
        assert result.decision is not None
        result = await service.step(
            definition.run_id,
            driver=_Driver(),
            checkpointer=checkpointer,
            resume={
                "decision_id": result.decision["decision_id"],
                "action": "accept",
                "domain_revision": result.decision["domain_revision"],
            },
        )

    assert result.record.state.status == "image_deferred"
    assert result.record.read_model.status == "image_deferred"
    assert result.record.read_model.active_stage_id == "cover"
    assert result.record.read_model.stage_status["cover"] == "completed"
    assert result.record.read_model.stage_status["export"] == "locked"
    assert not any(event.type == "export.ready" for event in repository.events(definition.run_id))
    assert any(event.type == "image.deferred" for event in repository.events(definition.run_id))


@pytest.mark.asyncio
async def test_image_deferred_terminal_is_stable_across_restart_and_sse_reconnect(
    tmp_path: Path,
) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, workflow_id="official.short_novel")
    repository = Phase32RunRepository(tmp_path / "runtime")
    repository.create(definition, updated_at=definition.created_at)
    checkpointer_path = tmp_path / "checkpoints"
    driver = _Driver()

    async with open_phase32_checkpointer(checkpointer_path) as checkpointer:
        service = Phase32GraphExecutionService(repository)
        result = await service.step(
            definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )
        while result.interrupted:
            assert result.decision is not None
            result = await service.step(
                definition.run_id,
                driver=driver,
                checkpointer=checkpointer,
                resume={
                    "decision_id": result.decision["decision_id"],
                    "action": "accept",
                    "domain_revision": result.decision["domain_revision"],
                },
            )

    terminal_history = repository.events(definition.run_id)
    terminal = [event for event in terminal_history if event.type == "image.deferred"]
    assert len(terminal) == 1
    assert not any(event.type == "export.ready" for event in terminal_history)

    reopened = Phase32RunRepository(repository.root)
    async with open_phase32_checkpointer(checkpointer_path) as checkpointer:
        replayed = await Phase32GraphExecutionService(reopened).step(
            definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )
        replayed_again = await Phase32GraphExecutionService(reopened).step(
            definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )

    assert replayed.record.state.status == "image_deferred"
    assert replayed_again.record.state.status == "image_deferred"
    assert reopened.events(definition.run_id) == terminal_history
    terminal_cursor = terminal[0].sequence
    projection = Phase32EventProjection(reopened)
    assert projection.page(
        definition.run_id,
        after=terminal_cursor - 1,
    ).event_sequences == (terminal_cursor,)
    assert projection.page(
        definition.run_id,
        after=terminal_cursor,
    ).events == ()


@pytest.mark.asyncio
async def test_canonical_long_route_resumes_sequential_text_into_mandatory_cover(
    tmp_path: Path,
) -> None:
    policy = ReviewPolicy(
        policy_id="review.long_novel.graph-execution",
        revision="r1",
        route_id="long_novel",
        checkpoint_policy="every_unit",
        warning_policy="pause_at_milestone",
        mandatory_decision_stages=(
            "brief",
            "book_architecture",
            "cast",
            "volumes",
            "rolling_detail",
            "text",
            "cover",
        ),
    )
    definition = _definition(
        LONG_NOVEL_ROUTE,
        workflow_id="official.long_novel",
        policy=policy,
    )
    repository = Phase32RunRepository(tmp_path / "runtime")
    repository.create(definition, updated_at=definition.created_at)
    service = Phase32GraphExecutionService(repository)
    checkpointer = InMemorySaver()
    driver = _LongNovelSequentialDriver()

    result = await service.step(
        definition.run_id,
        driver=driver,
        checkpointer=checkpointer,
    )
    while result.interrupted:
        assert result.decision is not None
        result = await service.step(
            definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume={
                "decision_id": result.decision["decision_id"],
                "action": "accept",
                "domain_revision": result.decision["domain_revision"],
            },
        )

    assert result.record.state.status == "image_deferred"
    assert result.record.state.stage_status["text"] == "completed"
    assert result.record.state.stage_status["cover"] == "completed"
    assert result.record.state.stage_status["export"] == "locked"
    assert result.record.read_model.pending_decisions == ()
    assert any(event.type == "image.deferred" for event in repository.events(definition.run_id))


@pytest.mark.asyncio
async def test_graph_step_projects_cast_gate_before_beat_board(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="execution-screenplay-nested-interrupt",
        project_id="project-execution-screenplay",
        creative_intent="验证人物注册表先停在人工门，再推进到决策节拍。",
    )
    service = Phase32GraphExecutionService(fixture.repository)
    checkpointer = InMemorySaver()

    brief = await service.step(
        fixture.definition.run_id,
        driver=_Driver(),
        checkpointer=checkpointer,
    )
    assert brief.decision is not None
    cast = await service.step(
        fixture.definition.run_id,
        driver=_Driver(),
        checkpointer=checkpointer,
        resume={
            "decision_id": brief.decision["decision_id"],
            "action": "accept",
            "domain_revision": brief.decision["domain_revision"],
        },
    )

    assert cast.interrupted is True
    assert cast.decision is not None
    assert cast.decision["stage_id"] == "cast"
    assert cast.record.state.stage_status["brief"] == "completed"
    assert cast.record.state.stage_status["cast"] == "awaiting_decision"

    beat = await service.step(
        fixture.definition.run_id,
        driver=_Driver(),
        checkpointer=checkpointer,
        resume={
            "decision_id": cast.decision["decision_id"],
            "action": "accept",
            "domain_revision": cast.decision["domain_revision"],
        },
    )

    assert beat.interrupted is True
    assert beat.decision is not None
    assert beat.decision["stage_id"] == "beat_board"
    assert beat.record.state.active_stage_id == "beat_board"
    assert beat.record.state.stage_status["brief"] == "completed"
    assert beat.record.state.stage_status["cast"] == "completed"
    assert beat.record.state.stage_status["beat_board"] == "awaiting_decision"
    assert beat.record.state.candidate_artifact_refs["beat_board"] == beat.decision["artifact_ref"]
    assert beat.record.read_model.active_stage_id == "beat_board"
    assert beat.record.read_model.pending_decisions[0].stage_id == "beat_board"


@pytest.mark.asyncio
async def test_screenplay_process_reopens_and_continues_at_next_frozen_scene(
    tmp_path: Path,
) -> None:
    policy = ReviewPolicy(
        policy_id="review.screenplay_sample.sequential-recovery",
        revision="r1",
        route_id="screenplay_sample",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=("brief", "cast", "beat_board", "scene_deck"),
        mandatory_decision_stages=("script",),
    )
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="execution-screenplay-sequential-recovery",
        project_id="project-execution-screenplay-recovery",
        creative_intent="验证逐 Scene checkpoint 在进程重开后继续冻结顺序。",
        review_policy=policy,
    )
    service = Phase32GraphExecutionService(fixture.repository)

    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        first = await service.step(
            fixture.definition.run_id,
            driver=_SequentialScriptDriver(),
            checkpointer=checkpointer,
        )
        assert first.decision is not None
        assert first.decision["unit_ref"] == "scene-1"
        second = await service.step(
            fixture.definition.run_id,
            driver=_SequentialScriptDriver(),
            checkpointer=checkpointer,
            resume={
                "decision_id": first.decision["decision_id"],
                "action": "accept",
                "domain_revision": first.decision["domain_revision"],
            },
        )

    assert second.decision is not None
    assert second.decision["unit_ref"] == "scene-2"
    second_progress = second.record.read_model.sequential_stage_progress["script"]
    assert tuple(second_progress.committed_artifact_refs) == ("scene-1",)

    reopened_repository = Phase32RunRepository(fixture.repository.root)
    reopened_service = Phase32GraphExecutionService(reopened_repository)
    async with open_phase32_checkpointer(tmp_path / "checkpoints") as checkpointer:
        third = await reopened_service.step(
            fixture.definition.run_id,
            driver=_SequentialScriptDriver(),
            checkpointer=checkpointer,
            resume={
                "decision_id": second.decision["decision_id"],
                "action": "accept",
                "domain_revision": second.decision["domain_revision"],
            },
        )

    assert third.decision is not None
    assert third.decision["unit_ref"] == "scene-3"
    third_progress = third.record.read_model.sequential_stage_progress["script"]
    assert tuple(third_progress.committed_artifact_refs) == (
        "scene-1",
        "scene-2",
    )
    assert third.record.read_model.active_unit_ref == "scene-3"


@pytest.mark.asyncio
async def test_execution_service_projects_committed_writeback_recovery_frontier(
    tmp_path: Path,
) -> None:
    policy = ReviewPolicy(
        policy_id="review.screenplay_sample.writeback-recovery",
        revision="r1",
        route_id="screenplay_sample",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=("brief", "cast", "beat_board", "scene_deck"),
        mandatory_decision_stages=("script",),
    )
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="execution-screenplay-writeback-recovery",
        project_id="project-execution-screenplay-writeback",
        creative_intent="验证已接受正文的写回恢复可由正式 execution service 投影。",
        review_policy=policy,
    )
    service = Phase32GraphExecutionService(fixture.repository)
    driver = SequentialWritebackRecoveryDriver()
    checkpointer = InMemorySaver()

    first = await service.step(
        fixture.definition.run_id,
        driver=driver,
        checkpointer=checkpointer,
    )
    assert first.decision is not None
    assert first.decision["unit_ref"] == "scene-1"

    recovery = await service.step(
        fixture.definition.run_id,
        driver=driver,
        checkpointer=checkpointer,
        resume={
            "decision_id": first.decision["decision_id"],
            "action": "accept",
            "domain_revision": first.decision["domain_revision"],
        },
    )

    assert recovery.decision is not None
    assert recovery.decision["type"] == "writeback_recovery"
    assert recovery.decision["artifact_ref"].startswith("artifact:")
    assert recovery.record.state.candidate_artifact_refs["script"].startswith(
        "candidate:"
    )
    projected = recovery.record.read_model.pending_decisions[0]
    assert projected.kind == "writeback_recovery"
    assert projected.artifact_ref == recovery.decision["artifact_ref"]
    assert projected.allowed_actions == ("retry_writeback", "cancel")
    progress = recovery.record.read_model.sequential_stage_progress["script"]
    assert progress.committed_artifact_refs == {}

    resumed = await service.step(
        fixture.definition.run_id,
        driver=driver,
        checkpointer=checkpointer,
        resume={
            "decision_id": recovery.decision["decision_id"],
            "action": "retry_writeback",
            "domain_revision": recovery.decision["domain_revision"],
        },
    )

    assert resumed.decision is not None
    assert resumed.decision["type"] == "route_stage_decision"
    assert resumed.decision["unit_ref"] == "scene-2"
    assert driver.generated_units == ["scene-1", "scene-2"]
    scene_writebacks = [
        call for call in driver.writeback_calls if call[0] == "scene-1"
    ]
    assert scene_writebacks[-1] == ("scene-1", True)
    assert sum(1 for _, retry in scene_writebacks if retry) == 1
