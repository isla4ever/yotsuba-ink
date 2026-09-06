from __future__ import annotations

from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.orchestration.phase32_run_preflight import Phase32RunPreflight
from novel_workflow.runtime.graph.route_graph import RouteStageCandidate, build_route_graph
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_graph_event_sink import Phase32RepositoryEventSink
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)


ROUTES = (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE)


class _FixtureDriver:
    def __init__(self) -> None:
        self.generated: list[str] = []
        self.validated: list[str] = []
        self.committed: list[str] = []

    async def generate_stage(self, *, definition, state, stage, direction=""):
        self.generated.append(stage.stage_id)
        return RouteStageCandidate(
            artifact_ref=f"fixture-candidate:{definition.run_id}:{stage.stage_id}",
            unit_ref=(
                f"{stage.stage_id}-unit-1"
                if stage.unitization in {"bounded_units", "sequential_units"}
                else ""
            ),
        )

    async def validate_stage(self, *, definition, state, stage, candidate):
        self.validated.append(stage.stage_id)

    async def commit_stage(self, *, definition, state, stage, candidate):
        self.committed.append(stage.stage_id)
        return f"fixture-artifact:{definition.run_id}:{stage.stage_id}"


@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.route_id)
@pytest.mark.asyncio
async def test_fixture_passes_preflight_and_shared_graph_until_brief_decision(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / route.route_id,
        route=route,
        run_id=f"integration-{route.route_id}",
        project_id="project-phase32-integration",
        creative_intent="验证 fixture、Preflight 和 Graph 共用同一冻结 identity。",
    )
    report = Phase32RunPreflight().validate(
        fixture.definition,
        state=fixture.state,
        read_model=fixture.read_model,
    )
    assert report.creation_route_id == route.route_id
    assert report.active_stage_id == "brief"
    assert report.status == "running"
    assert report.stage_ids == fixture.definition.stage_ids

    driver = _FixtureDriver()
    observed: list[tuple[str, str]] = []
    repository_sink = Phase32RepositoryEventSink(fixture.repository)

    def event_sink(definition, event_type, stage, state, payload):
        observed.append((event_type, stage.stage_id))
        repository_sink(definition, event_type, stage, state, payload)

    graph = build_route_graph(
        fixture.definition,
        driver,
        checkpointer=InMemorySaver(),
        event_sink=event_sink,
    )
    config = {"configurable": {"thread_id": fixture.definition.run_id}}
    interrupted = await graph.ainvoke(fixture.state, config=config)
    interrupt_value = interrupted["__interrupt__"][0].value

    assert interrupt_value["creation_route_id"] == route.route_id
    assert interrupt_value["stage_id"] == "brief"
    assert driver.generated == ["brief"]
    assert "export" not in driver.generated
    assert ("stage.started", "brief") in observed
    assert ("decision.required", "brief") in observed

    result = interrupted
    decisions = 0
    while "__interrupt__" in result:
        decision = result["__interrupt__"][0].value
        result = await graph.ainvoke(
            Command(
                resume={
                    "decision_id": decision["decision_id"],
                    "action": "accept",
                    "domain_revision": decision["domain_revision"],
                }
            ),
            config=config,
        )
        decisions += 1

    assert result["status"] == "completed"
    assert decisions >= 1
    assert set(driver.generated) == set(
        fixture.definition.route_contract.provider_stage_ids
    )
    assert "export" not in driver.generated

    events = fixture.repository.events(fixture.definition.run_id)
    assert tuple(event.sequence for event in events) == tuple(range(1, len(events) + 1))
    assert any(event.type == "decision.required" for event in events)
    assert any(event.type == "decision.resolved" for event in events)
    assert events[-1].type == "export.ready"

    projection = Phase32EventProjection(fixture.repository)
    tail = projection.page(fixture.definition.run_id, after=events[-2].sequence)
    assert tail.event_sequences == (events[-1].sequence,)
    assert tail.terminal is True
    assert projection.page(
        fixture.definition.run_id,
        after=events[-1].sequence,
    ).terminal is True


def test_repository_event_sink_deduplicates_writeback_replay_per_unit(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "writeback-events",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="integration-writeback-event-replay",
        project_id="project-writeback-event-replay",
        creative_intent="验证写回节点 replay 不复制正式事件。",
    )
    sink = Phase32RepositoryEventSink(fixture.repository)
    initial_event_count = len(fixture.repository.events(fixture.definition.run_id))
    stage = fixture.definition.stage("script")
    first_state = fixture.state.model_copy(
        update={"active_stage_id": "script", "active_unit_ref": "scene-1"}
    )
    replayed = (
        (
            "artifact.committed",
            {
                "node_id": "script.commit",
                "unit_ref": "scene-1",
                "artifact_ref": "p32-script-committed-a",
                "artifact_kind": "screenplay_draft",
            },
        ),
        (
            "evidence.completed",
            {
                "node_id": "script.writeback",
                "unit_ref": "scene-1",
                "receipt_ref": "writeback-scene-1",
                "evidence_count": 1,
                "fact_count": 1,
            },
        ),
        (
            "writeback.queued",
            {
                "node_id": "script.writeback",
                "unit_ref": "scene-1",
                "receipt_ref": "writeback-scene-1",
                "transaction_ref": "canon-scene-1",
            },
        ),
        (
            "writeback.committed",
            {
                "node_id": "script.writeback",
                "unit_ref": "scene-1",
                "receipt_ref": "writeback-scene-1",
                "transaction_ref": "canon-scene-1",
                "evidence_count": 1,
                "fact_count": 1,
            },
        ),
    )

    for event_type, payload in replayed:
        first = sink(fixture.definition, event_type, stage, first_state, payload)
        second = sink(fixture.definition, event_type, stage, first_state, payload)
        assert second.event_id == first.event_id

    second_state = first_state.model_copy(update={"active_unit_ref": "scene-2"})
    sink(
        fixture.definition,
        "stage.started",
        stage,
        first_state,
        {"node_id": "script.started"},
    )
    sink(
        fixture.definition,
        "stage.started",
        stage,
        second_state,
        {"node_id": "script.started"},
    )

    events = fixture.repository.events(fixture.definition.run_id)
    assert len(events) == initial_event_count + len(replayed) + 2
    assert [event.unit_ref for event in events[-2:]] == ["scene-1", "scene-2"]


def test_repository_event_sink_records_observed_event_time_not_run_creation_time(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "event-clock",
        route=SCREENPLAY_SAMPLE_ROUTE,
        run_id="integration-event-observed-time",
        project_id="project-event-observed-time",
        creative_intent="验证事件时间来自实际观测时钟。",
    )
    observed_at = "2026-09-05T14:03:02+00:00"
    sink = Phase32RepositoryEventSink(
        fixture.repository,
        clock=lambda: observed_at,
    )

    event = sink(
        fixture.definition,
        "stage.started",
        fixture.definition.stage("script"),
        fixture.state.model_copy(
            update={"active_stage_id": "script", "active_unit_ref": "scene-1"}
        ),
        {"node_id": "script.started"},
    )

    assert event.occurred_at == observed_at
    assert event.occurred_at != fixture.definition.created_at


def test_repository_event_sink_keeps_one_immutable_final_terminal_event(
    tmp_path: Path,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "terminal-events",
        route=SHORT_NOVEL_ROUTE,
        run_id="integration-terminal-event-singleton",
        project_id="project-terminal-event-singleton",
        creative_intent="验证图片暂缓终态在图重放后仍然唯一。",
    )
    sink = Phase32RepositoryEventSink(fixture.repository)
    stage = fixture.definition.stage("cover")
    state = fixture.state.model_copy(
        update={"active_stage_id": "cover", "status": "image_deferred"}
    )
    payload = {
        "node_id": "cover.image_deferred",
        "artifact_ref": "p32-cover-committed-stable",
        "reason": "image_acceptance_not_in_current_wave",
    }

    first = sink(fixture.definition, "image.deferred", stage, state, payload)
    replayed = sink(fixture.definition, "image.deferred", stage, state, payload)

    assert replayed == first
    assert [
        event.type
        for event in fixture.repository.events(fixture.definition.run_id)
        if event.type in {"image.deferred", "export.ready"}
    ] == ["image.deferred"]

    with pytest.raises(ValueError, match="final terminal event"):
        sink(
            fixture.definition,
            "image.deferred",
            stage,
            state,
            {**payload, "reason": "conflicting_reason"},
        )

    with pytest.raises(ValueError, match="final terminal event"):
        sink(
            fixture.definition,
            "export.ready",
            fixture.definition.stage("export"),
            state.model_copy(update={"active_stage_id": "export", "status": "completed"}),
            {
                "node_id": "export.ready",
                "artifact_ref": "p32-export-committed-conflict",
            },
        )
