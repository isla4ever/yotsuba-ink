from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.orchestration.phase32_run_fixture import (
    phase32_fixture_provider_bindings,
)
from novel_workflow.workflows.frozen_route_contract import freeze_route_contract
from novel_workflow.workflows.graph_run_definition import (
    GraphRunDefinition,
    freeze_phase32_scale_profile,
    freeze_contract_payload,
    freeze_graph_run_definition,
)
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_INPUTS_CONTRACT_REVISION,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.review_policy import (
    LONG_NOVEL_REVIEW_POLICY,
    SCREENPLAY_REVIEW_POLICY,
    SHORT_NOVEL_REVIEW_POLICY,
)
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)
from novel_workflow.workflows.phase32_scale import (
    ScaleProfile,
    freeze_continuity_acceptance_scale_profile,
    freeze_release_smoke_scale_profile,
    freeze_scale_profile,
)


OFFICIAL_CASES = (
    (SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY),
    (SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY),
    (LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY),
)


def _definition(route, policy) -> GraphRunDefinition:
    route_contract = freeze_route_contract(RouteGraphCompiler().compile(route), policy)
    workflow_id = f"workflow-{route.route_id}"
    provider_bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id=workflow_id,
    )
    return freeze_graph_run_definition(
        run_id=f"run-{route.route_id}",
        project_id="project-phase32",
        workflow_id=workflow_id,
        workflow_revision="route-r1",
        workflow_digest="a" * 64,
        route_contract=route_contract,
        scale_profile=freeze_contract_payload(
            contract_id=f"scale.{route.route_id}",
            contract_revision="r1",
            payload={"target": 12_000, "unit": "characters"},
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id(route.route_id),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "一份明确、可冻结的创作意图",
            },
        ),
        provider_bindings_by_stage=provider_bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at="2026-08-22T12:00:00+08:00",
    )


@pytest.mark.parametrize(
    ("route", "policy"),
    OFFICIAL_CASES,
    ids=lambda value: getattr(value, "route_id", getattr(value, "policy_id", "case")),
)
def test_graph_run_definition_round_trips_each_official_route(route, policy) -> None:
    definition = _definition(route, policy)
    restored = GraphRunDefinition.model_validate_json(definition.model_dump_json())

    assert restored == definition
    assert restored.creation_route_id == route.route_id
    assert restored.route_revision == route.revision
    assert restored.stage_ids == tuple(stage.stage_id for stage in route.stages)
    assert tuple(restored.initial_stage_status()) == restored.stage_ids
    assert restored.initial_stage_status()[restored.stage_ids[0]] == "available"
    assert set(restored.initial_stage_status().values()) == {"available", "locked"}


@pytest.mark.parametrize(
    ("route", "policy"),
    OFFICIAL_CASES,
    ids=lambda value: getattr(value, "route_id", getattr(value, "policy_id", "case")),
)
def test_graph_run_definition_freezes_typed_scale_profile(route, policy) -> None:
    route_contract = freeze_route_contract(RouteGraphCompiler().compile(route), policy)
    workflow_id = f"workflow-{route.route_id}"
    provider_bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id=workflow_id,
    )
    definition = freeze_graph_run_definition(
        run_id=f"typed-scale-{route.route_id}",
        project_id="project-phase32-scale",
        workflow_id=workflow_id,
        workflow_revision="route-r1",
        workflow_digest="c" * 64,
        route_contract=route_contract,
        scale_profile=freeze_phase32_scale_profile(freeze_scale_profile(route.route_id)),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id(route.route_id),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "typed scale fixture",
            },
        ),
        provider_bindings_by_stage=provider_bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at="2026-08-23T12:00:00+08:00",
    )

    restored_profile = ScaleProfile.model_validate(definition.scale_profile.payload)
    assert definition.scale_profile.contract_id == f"length.{route.route_id}.v1"
    assert restored_profile.route_id == route.route_id


@pytest.mark.parametrize("route", (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE))
def test_graph_run_definition_accepts_explicit_release_smoke_scale_profile(route) -> None:
    policy = {
        "screenplay_sample": SCREENPLAY_REVIEW_POLICY,
        "short_novel": SHORT_NOVEL_REVIEW_POLICY,
        "long_novel": LONG_NOVEL_REVIEW_POLICY,
    }[route.route_id]
    route_contract = freeze_route_contract(RouteGraphCompiler().compile(route), policy)
    workflow_id = f"workflow-{route.route_id}-smoke"
    definition = freeze_graph_run_definition(
        run_id=f"release-smoke-{route.route_id}",
        project_id="project-phase32-smoke",
        workflow_id=workflow_id,
        workflow_revision="route-r1",
        workflow_digest="d" * 64,
        route_contract=route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_release_smoke_scale_profile(route.route_id)
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id(route.route_id),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "release smoke fixture",
            },
        ),
        provider_bindings_by_stage=phase32_fixture_provider_bindings(
            route_contract,
            workflow_id=workflow_id,
        ),
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at="2026-08-26T12:00:00+08:00",
    )

    restored = GraphRunDefinition.model_validate_json(definition.model_dump_json())
    assert restored.scale_profile.contract_id == (
        f"length.{route.route_id}.release_smoke.v1"
    )
    assert restored.scale_profile.payload["profile_kind"] == "release_smoke"


def test_graph_run_definition_accepts_private_long_continuity_scale_profile() -> None:
    route_contract = freeze_route_contract(
        RouteGraphCompiler().compile(LONG_NOVEL_ROUTE),
        LONG_NOVEL_REVIEW_POLICY,
    )
    workflow_id = "workflow-long-novel-continuity"
    definition = freeze_graph_run_definition(
        run_id="continuity-acceptance-long-novel",
        project_id="continuity-acceptance-project",
        workflow_id=workflow_id,
        workflow_revision="route-r1",
        workflow_digest="e" * 64,
        route_contract=route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_continuity_acceptance_scale_profile("long_novel")
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id("long_novel"),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "exact-12 continuity acceptance fixture",
            },
        ),
        provider_bindings_by_stage=phase32_fixture_provider_bindings(
            route_contract,
            workflow_id=workflow_id,
        ),
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at="2026-09-05T12:00:00+08:00",
    )

    restored = GraphRunDefinition.model_validate_json(definition.model_dump_json())
    assert restored.scale_profile.contract_id == (
        "length.long_novel.continuity_acceptance.v1"
    )
    assert restored.scale_profile.payload["profile_kind"] == "continuity_acceptance"


def test_graph_run_definition_rejects_typed_scale_profile_from_another_route() -> None:
    route_contract = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    provider_bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id="workflow-short-novel",
    )

    with pytest.raises(ValidationError, match="does not match its Run route"):
        freeze_graph_run_definition(
            run_id="typed-scale-mismatch",
            project_id="project-phase32-scale",
            workflow_id="workflow-short-novel",
            workflow_revision="route-r1",
            workflow_digest="c" * 64,
            route_contract=route_contract,
            scale_profile=freeze_phase32_scale_profile(freeze_scale_profile("long_novel")),
            inputs=freeze_contract_payload(
                contract_id=phase32_inputs_contract_id("short_novel"),
                contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
                payload={
                    "creation_language": PHASE32_CREATION_LANGUAGE,
                    "creative_intent": "mismatch",
                },
            ),
            provider_bindings_by_stage=provider_bindings,
            export_profile=route_contract.route_manifest.export_profiles[0],
            created_at="2026-08-23T12:00:00+08:00",
        )


def test_graph_run_definition_requires_every_provider_stage_in_manifest_order() -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY)
    payload = definition.model_dump(mode="json")
    payload["provider_bindings_by_stage"] = payload["provider_bindings_by_stage"][:-1]

    with pytest.raises(ValidationError, match="exactly match the compiled route order"):
        GraphRunDefinition.model_validate(payload)


def test_graph_run_definition_rejects_binding_for_deterministic_export() -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY)
    payload = definition.model_dump(mode="json")
    payload["provider_bindings_by_stage"].append(
        {
            "stage_id": "export",
            "binding": payload["provider_bindings_by_stage"][0]["binding"],
        }
    )

    with pytest.raises(ValidationError, match="exactly match the compiled route order"):
        GraphRunDefinition.model_validate(payload)


def test_graph_run_definition_rejects_export_profile_from_another_route() -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY)
    payload = definition.model_dump(mode="json")
    payload["export_profile"] = "epub"

    with pytest.raises(ValidationError, match="not supported"):
        GraphRunDefinition.model_validate(payload)


def test_graph_run_definition_rejects_tampered_nested_contract_payload() -> None:
    definition = _definition(LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY)
    payload = definition.model_dump(mode="json")
    payload["scale_profile"]["payload"]["target"] = 4_000

    with pytest.raises(ValidationError, match="payload digest"):
        GraphRunDefinition.model_validate(payload)


def test_graph_run_definition_rejects_tampered_definition_payload() -> None:
    definition = _definition(LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY)
    payload = definition.model_dump(mode="json")
    payload["project_id"] = "project-tampered"

    with pytest.raises(ValidationError, match="definition digest"):
        GraphRunDefinition.model_validate(payload)


def test_graph_run_definition_rejects_retired_quality_mode_field() -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY)
    payload = definition.model_dump(mode="json")
    payload["quality_mode"] = "balanced"

    with pytest.raises(ValidationError, match="quality_mode"):
        GraphRunDefinition.model_validate(payload)


def test_graph_run_definition_has_no_phase27_execution_dependencies() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "novel_workflow"
        / "workflows"
        / "graph_run_definition.py"
    ).read_text(encoding="utf-8")

    for retired_term in (
        "QualityMode",
        "STAGE_ORDER",
        "PHASE27_EDGES",
        "RunDefinition",
        '"fast"',
        '"balanced"',
        '"deep"',
    ):
        if retired_term == "RunDefinition":
            assert "narrative_run_repository import RunDefinition" not in source
        else:
            assert retired_term not in source
