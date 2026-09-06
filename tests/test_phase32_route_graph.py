from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from novel_workflow.runtime.graph.route_graph import (
    RouteStageCandidate,
    build_route_graph,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.orchestration.phase32_run_fixture import (
    phase32_fixture_provider_bindings,
)
from novel_workflow.workflows.frozen_route_contract import freeze_route_contract
from novel_workflow.workflows.graph_run_definition import (
    GraphRunDefinition,
    freeze_contract_payload,
    freeze_graph_run_definition,
)
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_INPUTS_CONTRACT_REVISION,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.review_policy import ReviewPolicy
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)


ROUTES = (
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    LONG_NOVEL_ROUTE,
)


def _definition(
    route: CreationRouteSpec,
    *,
    policy: ReviewPolicy | None = None,
    workflow_id: str | None = None,
) -> GraphRunDefinition:
    manifest = RouteGraphCompiler().compile(route)
    route_policy = policy or ReviewPolicy(
        policy_id=f"review.{route.route_id}.graph-test",
        revision="r1",
        route_id=route.route_id,
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        mandatory_decision_stages=("brief",),
    )
    route_contract = freeze_route_contract(manifest, route_policy)
    workflow_id = workflow_id or f"workflow-{route.route_id}"
    bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id=workflow_id,
    )
    target = {
        "screenplay_sample": 12,
        "short_novel": 20_000,
        "long_novel": 150_000,
    }[route.route_id]
    return freeze_graph_run_definition(
        run_id=f"graph-{route.route_id}",
        project_id="project-phase32-graph",
        workflow_id=workflow_id,
        workflow_revision="route-r1",
        workflow_digest="a" * 64,
        route_contract=route_contract,
        scale_profile=freeze_contract_payload(
            contract_id=f"scale.{route.route_id}",
            contract_revision="r1",
            payload={
                "target": target,
                "unit": "minutes" if route.route_id == "screenplay_sample" else "characters",
            },
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id(route.route_id),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "graph fixture",
            },
        ),
        provider_bindings_by_stage=bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at="2026-08-23T12:00:00+08:00",
    )


class FakeRouteDriver:
    def __init__(self) -> None:
        self.generated: list[str] = []
        self.validated: list[str] = []
        self.committed: list[str] = []

    async def generate_stage(self, *, definition, state, stage, direction=""):
        self.generated.append(stage.stage_id)
        suffix = f"-redraft-{len(self.generated)}" if direction else ""
        return RouteStageCandidate(
            artifact_ref=f"candidate:{definition.run_id}:{stage.stage_id}{suffix}",
            unit_ref=(f"{stage.stage_id}-unit-1" if stage.unitization in {"bounded_units", "sequential_units"} else ""),
        )

    async def validate_stage(self, *, definition, state, stage, candidate):
        self.validated.append(stage.stage_id)

    async def commit_stage(self, *, definition, state, stage, candidate):
        self.committed.append(stage.stage_id)
        return f"artifact:{definition.run_id}:{stage.stage_id}"


class SequentialScriptDriver(FakeRouteDriver):
    scene_refs = ("scene-1", "scene-2", "scene-3")

    def __init__(self, *, jump_to: str = "") -> None:
        super().__init__()
        self.jump_to = jump_to
        self.generated_units: list[str] = []

    def sequential_unit_refs(self, *, stage, **kwargs):
        return self.scene_refs if stage.stage_id == "script" else ()

    async def generate_stage(self, *, definition, state, stage, direction=""):
        if stage.stage_id != "script":
            return await super().generate_stage(
                definition=definition,
                state=state,
                stage=stage,
                direction=direction,
            )
        unit_ref = self.jump_to or state.active_unit_ref
        self.generated.append(stage.stage_id)
        self.generated_units.append(unit_ref)
        return RouteStageCandidate(
            artifact_ref=f"candidate:{definition.run_id}:script:{unit_ref}",
            unit_ref=unit_ref,
        )

    async def commit_stage(self, *, definition, state, stage, candidate):
        self.committed.append(stage.stage_id)
        if stage.stage_id == "script":
            return f"artifact:{definition.run_id}:script:{candidate.unit_ref}"
        return f"artifact:{definition.run_id}:{stage.stage_id}"


@dataclass(frozen=True)
class _WritebackReceipt:
    status: str
    receipt_ref: str
    unit_ref: str
    transaction_ref: str = ""
    evidence_refs: tuple[str, ...] = ()
    fact_refs: tuple[str, ...] = ()
    error_code: str = ""
    error_message: str = ""
    recovery_count: int = 0


class SequentialWritebackRecoveryDriver(SequentialScriptDriver):
    scene_refs = ("scene-1", "scene-2")

    def __init__(self) -> None:
        super().__init__()
        self.writeback_calls: list[tuple[str, bool]] = []
        self.cancelled_receipts: list[str] = []

    async def commit_writeback(
        self,
        *,
        definition,
        state,
        stage,
        artifact_ref,
        unit_ref,
        retry=False,
    ):
        self.writeback_calls.append((unit_ref, retry))
        receipt_ref = f"writeback:{definition.run_id}:{unit_ref}"
        if unit_ref == "scene-1" and not retry:
            return _WritebackReceipt(
                status="needs_action",
                receipt_ref=receipt_ref,
                unit_ref=unit_ref,
                error_code="wiki_projection_unavailable",
                error_message="Wiki 投影暂时不可用",
            )
        return _WritebackReceipt(
            status="committed",
            receipt_ref=receipt_ref,
            unit_ref=unit_ref,
            transaction_ref=f"canon:{unit_ref}",
            evidence_refs=(f"evidence:{unit_ref}",),
            fact_refs=(f"fact:{unit_ref}",),
            recovery_count=1 if retry else 0,
        )

    def cancel_writeback(self, run_id: str, receipt_ref: str) -> None:
        self.cancelled_receipts.append(receipt_ref)


class RepeatedWritebackRecoveryDriver(SequentialWritebackRecoveryDriver):
    """Keep the first retry in recovery so the graph must replay twice."""

    def __init__(self) -> None:
        super().__init__()
        self.recovery_count = 0

    async def commit_writeback(
        self,
        *,
        definition,
        state,
        stage,
        artifact_ref,
        unit_ref,
        retry=False,
    ):
        self.writeback_calls.append((unit_ref, retry))
        receipt_ref = f"writeback:{definition.run_id}:{unit_ref}"
        if unit_ref == "scene-1" and not retry:
            return _WritebackReceipt(
                status="needs_action",
                receipt_ref=receipt_ref,
                unit_ref=unit_ref,
                error_code="evidence_proposal_failed",
                error_message="still unavailable",
                recovery_count=self.recovery_count,
            )
        if unit_ref == "scene-1" and retry and self.recovery_count == 0:
            self.recovery_count = 1
            return _WritebackReceipt(
                status="needs_action",
                receipt_ref=receipt_ref,
                unit_ref=unit_ref,
                error_code="evidence_proposal_failed",
                error_message="still unavailable",
                recovery_count=self.recovery_count,
            )
        return _WritebackReceipt(
            status="committed",
            receipt_ref=receipt_ref,
            unit_ref=unit_ref,
            transaction_ref=f"canon:{unit_ref}",
            evidence_refs=(f"evidence:{unit_ref}",),
            fact_refs=(f"fact:{unit_ref}",),
            recovery_count=self.recovery_count,
        )


@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.route_id)
def test_one_builder_uses_the_frozen_manifest_for_each_route(route: CreationRouteSpec) -> None:
    definition = _definition(route)
    graph = build_route_graph(definition, FakeRouteDriver(), checkpointer=InMemorySaver())

    graph_nodes = set(graph.get_graph().nodes)
    assert set(definition.stage_ids) <= graph_nodes
    assert "spine" not in graph_nodes
    assert "volumes" in graph_nodes if route.route_id == "long_novel" else "volumes" not in graph_nodes
    assert "quality_mode" not in Path(
        Path(__file__).resolve().parents[1] / "src/novel_workflow/runtime/graph/route_graph.py"
    ).read_text(encoding="utf-8")

    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
    assert ("__start__", "brief") in edges
    assert ("export", "__end__") in edges
    for stage in definition.route_contract.route_manifest.stages:
        for downstream in stage.downstream_stage_ids:
            assert (stage.stage_id, downstream) in edges


@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.route_id)
@pytest.mark.asyncio
async def test_route_graph_runs_all_routes_and_never_generates_export(route: CreationRouteSpec) -> None:
    manifest = RouteGraphCompiler().compile(route)
    provider_stage_ids = tuple(
        stage.stage_id for stage in manifest.stages if stage.provider_task_kind is not None
    )
    policy = ReviewPolicy(
        policy_id=f"review.{route.route_id}.graph-auto",
        revision="r1",
        route_id=route.route_id,
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=provider_stage_ids[1:],
        mandatory_decision_stages=(provider_stage_ids[0],),
    )
    definition = _definition(route, policy=policy)
    driver = FakeRouteDriver()
    events: list[tuple[str, str]] = []

    def observe(definition, event_type, stage, state, payload):
        events.append((event_type, stage.stage_id))

    graph = build_route_graph(
        definition,
        driver,
        checkpointer=InMemorySaver(),
        event_sink=observe,
    )
    config = {"configurable": {"thread_id": definition.run_id}}
    interrupted = await graph.ainvoke(initial_route_run_state(definition), config=config)
    interrupt_value = interrupted["__interrupt__"][0].value
    assert interrupt_value["stage_id"] == provider_stage_ids[0]

    completed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": interrupt_value["decision_id"],
                "action": "accept",
                "domain_revision": interrupt_value["domain_revision"],
            }
        ),
        config=config,
    )

    assert completed["status"] == "completed"
    assert completed["active_stage_id"] == "export"
    assert set(completed["artifact_refs"]) == set(definition.stage_ids)
    assert driver.generated == list(provider_stage_ids)
    assert "export" not in driver.generated
    assert driver.committed == list(definition.stage_ids)
    assert ("export.ready", "export") in events


@pytest.mark.asyncio
async def test_mandatory_decision_and_auto_continue_are_policy_driven() -> None:
    route = SHORT_NOVEL_ROUTE
    manifest = RouteGraphCompiler().compile(route)
    policy = ReviewPolicy(
        policy_id="review.short_novel.policy-driven",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=("story_map", "cast", "section_plan", "text", "cover"),
        mandatory_decision_stages=("brief",),
    )
    definition = _definition(route, policy=policy)
    driver = FakeRouteDriver()
    graph = build_route_graph(definition, driver, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": definition.run_id}}
    interrupted = await graph.ainvoke(initial_route_run_state(definition), config=config)
    decision = interrupted["__interrupt__"][0].value
    assert decision["stage_id"] == "brief"
    assert graph.get_state(config).next

    completed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            }
        ),
        config=config,
    )
    assert completed["status"] == "completed"
    assert driver.generated == [stage.stage_id for stage in manifest.stages if stage.provider_task_kind]


@pytest.mark.asyncio
async def test_canonical_short_route_stops_at_cover_with_image_deferred_status() -> None:
    definition = _definition(
        SHORT_NOVEL_ROUTE,
        workflow_id="official.short_novel",
        policy=ReviewPolicy(
            policy_id="review.short_novel.image-deferred",
            revision="r1",
            route_id="short_novel",
            checkpoint_policy="milestone",
            warning_policy="continue_and_surface",
            auto_continue_stages=(
                "story_map",
                "cast",
                "section_plan",
                "text",
                "cover",
            ),
            mandatory_decision_stages=("brief",),
        ),
    )
    events: list[tuple[str, str]] = []

    def observe(_definition, event_type, stage, _state, _payload):
        events.append((event_type, stage.stage_id))

    driver = FakeRouteDriver()
    graph = build_route_graph(
        definition,
        driver,
        checkpointer=InMemorySaver(),
        event_sink=observe,
    )
    config = {"configurable": {"thread_id": definition.run_id}}
    first = await graph.ainvoke(initial_route_run_state(definition), config=config)
    decision = first["__interrupt__"][0].value
    completed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            }
        ),
        config=config,
    )

    assert completed["status"] == "image_deferred"
    assert completed["active_stage_id"] == "cover"
    assert completed["stage_status"]["cover"] == "completed"
    assert completed["stage_status"]["export"] == "locked"
    assert "export" not in driver.committed
    assert ("image.deferred", "cover") in events


@pytest.mark.asyncio
async def test_route_graph_rejects_state_from_another_definition() -> None:
    source = _definition(SHORT_NOVEL_ROUTE)
    target = _definition(LONG_NOVEL_ROUTE)
    graph = build_route_graph(target, FakeRouteDriver(), checkpointer=InMemorySaver())

    with pytest.raises(ValueError, match="does not match its definition"):
        await graph.ainvoke(initial_route_run_state(source), config={"configurable": {"thread_id": target.run_id}})


def test_route_graph_source_has_no_retired_fixed_execution_terms() -> None:
    source = Path(__file__).resolve().parents[1] / "src/novel_workflow/runtime/graph/route_graph.py"
    text = source.read_text(encoding="utf-8")
    for retired_term in ("STAGE_ORDER", "PHASE27_EDGES", "quality_mode", "NarrativeRunState"):
        assert retired_term not in text


@pytest.mark.asyncio
async def test_directed_redraft_is_bounded_and_keeps_export_deterministic() -> None:
    route = SHORT_NOVEL_ROUTE
    policy = ReviewPolicy(
        policy_id="review.short_novel.redraft",
        revision="r1",
        route_id="short_novel",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        directed_redraft_limit_by_stage={"brief": 1},
        mandatory_decision_stages=("brief",),
    )
    definition = _definition(route, policy=policy)
    driver = FakeRouteDriver()
    graph = build_route_graph(definition, driver, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": definition.run_id}}

    first = await graph.ainvoke(initial_route_run_state(definition), config=config)
    first_decision = first["__interrupt__"][0].value
    second = await graph.ainvoke(
        Command(
            resume={
                "decision_id": first_decision["decision_id"],
                "action": "regenerate",
                "direction": "收紧开场冲突并保留原有承诺",
                "domain_revision": first_decision["domain_revision"],
            }
        ),
        config=config,
    )
    second_decision = second["__interrupt__"][0].value
    assert second_decision["decision_id"] != first_decision["decision_id"]
    assert second_decision["redraft_used"] == 1
    assert driver.generated.count("brief") == 2

    completed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": second_decision["decision_id"],
                "action": "accept",
                "domain_revision": second_decision["domain_revision"],
            }
        ),
        config=config,
    )
    assert completed["status"] == "completed"
    assert driver.generated.count("brief") == 2
    assert "export" not in driver.generated


def _sequential_script_definition() -> GraphRunDefinition:
    policy = ReviewPolicy(
        policy_id="review.screenplay_sample.sequential-script",
        revision="r1",
        route_id="screenplay_sample",
        checkpoint_policy="milestone",
        warning_policy="continue_and_surface",
        auto_continue_stages=("brief", "cast", "beat_board", "scene_deck"),
        mandatory_decision_stages=("script",),
    )
    return _definition(SCREENPLAY_SAMPLE_ROUTE, policy=policy)


@pytest.mark.asyncio
async def test_script_stage_commits_three_scenes_in_frozen_prefix_order() -> None:
    definition = _sequential_script_definition()
    driver = SequentialScriptDriver()
    graph = build_route_graph(definition, driver, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": definition.run_id}}

    result = await graph.ainvoke(initial_route_run_state(definition), config=config)
    for expected_scene_ref in driver.scene_refs:
        decision = result["__interrupt__"][0].value
        assert decision["stage_id"] == "script"
        assert decision["unit_ref"] == expected_scene_ref
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

    progress = result["sequential_stage_progress"]["script"]
    assert result["status"] == "completed"
    assert result["active_stage_id"] == "export"
    assert "script" not in result["artifact_refs"]
    assert tuple(progress["committed_artifact_refs"]) == driver.scene_refs
    assert tuple(progress["committed_artifact_refs"].values()) == tuple(
        f"artifact:{definition.run_id}:script:{scene_ref}"
        for scene_ref in driver.scene_refs
    )
    assert driver.generated_units == list(driver.scene_refs)


@pytest.mark.asyncio
async def test_script_stage_rejects_provider_jump_outside_frozen_cursor() -> None:
    definition = _sequential_script_definition()
    graph = build_route_graph(
        definition,
        SequentialScriptDriver(jump_to="scene-3"),
        checkpointer=InMemorySaver(),
    )

    with pytest.raises(ValueError, match="outside the frozen cursor"):
        await graph.ainvoke(
            initial_route_run_state(definition),
            config={"configurable": {"thread_id": definition.run_id}},
        )


@pytest.mark.asyncio
async def test_writeback_recovery_blocks_prefix_until_retry_then_advances_unit() -> None:
    definition = _sequential_script_definition()
    driver = SequentialWritebackRecoveryDriver()
    events: list[tuple[str, str]] = []

    def observe(definition, event_type, stage, state, payload):
        events.append((event_type, str(payload.get("unit_ref") or state.active_unit_ref)))

    graph = build_route_graph(
        definition,
        driver,
        checkpointer=InMemorySaver(),
        event_sink=observe,
    )
    config = {"configurable": {"thread_id": definition.run_id}}
    first = await graph.ainvoke(initial_route_run_state(definition), config=config)
    script_decision = first["__interrupt__"][0].value
    assert script_decision["type"] == "route_stage_decision"
    assert script_decision["unit_ref"] == "scene-1"

    blocked = await graph.ainvoke(
        Command(
            resume={
                "decision_id": script_decision["decision_id"],
                "action": "accept",
                "domain_revision": script_decision["domain_revision"],
            }
        ),
        config=config,
    )
    recovery = blocked["__interrupt__"][0].value

    assert recovery["type"] == "writeback_recovery"
    assert recovery["allowed_actions"] == ["retry_writeback", "cancel"]
    assert recovery["unit_ref"] == "scene-1"
    progress = blocked["sequential_stage_progress"].get("script")
    assert progress is None or progress["committed_artifact_refs"] == {}
    assert driver.generated_units == ["scene-1"]
    assert ("writeback.failed", "scene-1") in events

    resumed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": recovery["decision_id"],
                "action": "retry_writeback",
                "domain_revision": recovery["domain_revision"],
            }
        ),
        config=config,
    )
    next_decision = resumed["__interrupt__"][0].value

    assert next_decision["type"] == "route_stage_decision"
    assert next_decision["unit_ref"] == "scene-2"
    assert driver.generated_units == ["scene-1", "scene-2"]
    assert ("scene-1", True) in driver.writeback_calls
    assert ("writeback.committed", "scene-1") in events

    completed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": next_decision["decision_id"],
                "action": "accept",
                "domain_revision": next_decision["domain_revision"],
            }
        ),
        config=config,
    )
    assert completed["status"] == "completed"
    assert tuple(
        completed["sequential_stage_progress"]["script"]["committed_artifact_refs"]
    ) == driver.scene_refs


@pytest.mark.asyncio
async def test_writeback_recovery_replays_prior_interrupt_before_next_retry() -> None:
    definition = _sequential_script_definition()
    driver = RepeatedWritebackRecoveryDriver()
    graph = build_route_graph(definition, driver, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": definition.run_id}}

    first = await graph.ainvoke(initial_route_run_state(definition), config=config)
    stage_decision = first["__interrupt__"][0].value
    blocked = await graph.ainvoke(
        Command(
            resume={
                "decision_id": stage_decision["decision_id"],
                "action": "accept",
                "domain_revision": stage_decision["domain_revision"],
            }
        ),
        config=config,
    )
    recovery_one = blocked["__interrupt__"][0].value

    blocked_again = await graph.ainvoke(
        Command(
            resume={
                "decision_id": recovery_one["decision_id"],
                "action": "retry_writeback",
                "domain_revision": recovery_one["domain_revision"],
            }
        ),
        config=config,
    )
    recovery_two = blocked_again["__interrupt__"][0].value
    assert recovery_two["decision_id"].endswith("recovery-2")

    resumed = await graph.ainvoke(
        Command(
            resume={
                "decision_id": recovery_two["decision_id"],
                "action": "retry_writeback",
                "domain_revision": recovery_two["domain_revision"],
            }
        ),
        config=config,
    )
    next_stage_decision = resumed["__interrupt__"][0].value
    assert next_stage_decision["type"] == "route_stage_decision"
    assert next_stage_decision["unit_ref"] == "scene-2"
    assert driver.writeback_calls.count(("scene-1", True)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ("accept", "regenerate", "ignore"))
async def test_writeback_recovery_rejects_stage_decision_actions(action: str) -> None:
    definition = _sequential_script_definition()
    driver = SequentialWritebackRecoveryDriver()
    graph = build_route_graph(definition, driver, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": definition.run_id}}
    first = await graph.ainvoke(initial_route_run_state(definition), config=config)
    script_decision = first["__interrupt__"][0].value
    blocked = await graph.ainvoke(
        Command(
            resume={
                "decision_id": script_decision["decision_id"],
                "action": "accept",
                "domain_revision": script_decision["domain_revision"],
            }
        ),
        config=config,
    )
    recovery = blocked["__interrupt__"][0].value

    with pytest.raises(ValueError, match="not allowed"):
        await graph.ainvoke(
            Command(
                resume={
                    "decision_id": recovery["decision_id"],
                    "action": action,
                    "domain_revision": recovery["domain_revision"],
                }
            ),
            config=config,
        )


@pytest.mark.asyncio
async def test_writeback_recovery_cancel_keeps_prefix_unaccepted() -> None:
    definition = _sequential_script_definition()
    driver = SequentialWritebackRecoveryDriver()
    graph = build_route_graph(definition, driver, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": definition.run_id}}
    first = await graph.ainvoke(initial_route_run_state(definition), config=config)
    script_decision = first["__interrupt__"][0].value
    blocked = await graph.ainvoke(
        Command(
            resume={
                "decision_id": script_decision["decision_id"],
                "action": "accept",
                "domain_revision": script_decision["domain_revision"],
            }
        ),
        config=config,
    )
    recovery = blocked["__interrupt__"][0].value

    cancelled = await graph.ainvoke(
        Command(
            resume={
                "decision_id": recovery["decision_id"],
                "action": "cancel",
                "domain_revision": recovery["domain_revision"],
            }
        ),
        config=config,
    )

    assert cancelled["status"] == "cancelled"
    progress = cancelled["sequential_stage_progress"].get("script")
    assert progress is None or progress["committed_artifact_refs"] == {}
    assert driver.cancelled_receipts == [recovery["writeback_receipt_ref"]]
