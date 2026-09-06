from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.orchestration.phase32_run_fixture import (
    phase32_fixture_provider_bindings,
)
from novel_workflow.runtime.graph.route_run_state import (
    initial_route_run_state,
    restore_route_run_state,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json
from novel_workflow.storage.route_run_event import (
    create_route_run_event,
    restore_route_run_event,
)
from novel_workflow.storage.route_run_read_model import (
    RouteRunReadModel,
    initial_route_run_read_model,
    restore_route_run_read_model,
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


OFFICIAL_CASES = (
    (SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY),
    (SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY),
    (LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY),
)
NOW = "2026-08-22T14:00:00+08:00"


def _definition(route, policy) -> GraphRunDefinition:
    route_contract = freeze_route_contract(RouteGraphCompiler().compile(route), policy)
    workflow_id = f"workflow-{route.route_id}"
    bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id=workflow_id,
    )
    return freeze_graph_run_definition(
        run_id=f"run-{route.route_id}",
        project_id="project-phase32-projection",
        workflow_id=workflow_id,
        workflow_revision="route-r1",
        workflow_digest="b" * 64,
        route_contract=route_contract,
        scale_profile=freeze_contract_payload(
            contract_id=f"scale.{route.route_id}",
            contract_revision="r1",
            payload={"target": 12_000},
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id(route.route_id),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "冻结输入",
            },
        ),
        provider_bindings_by_stage=bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at=NOW,
    )


@pytest.mark.parametrize(
    ("route", "policy"),
    OFFICIAL_CASES,
    ids=lambda value: getattr(value, "route_id", getattr(value, "policy_id", "case")),
)
def test_definition_state_read_model_and_event_round_trip_from_disk(
    tmp_path: Path,
    route,
    policy,
) -> None:
    definition = _definition(route, policy)
    state = initial_route_run_state(definition)
    read_model = initial_route_run_read_model(definition, updated_at=NOW)
    start_stage = definition.route_contract.route_manifest.start_stage_id
    event = create_route_run_event(
        definition,
        event_id=f"event-{route.route_id}",
        sequence=1,
        occurred_at=NOW,
        type="stage.started",
        stage_id=start_stage,
        status="running",
    )
    run_root = tmp_path / definition.run_id
    atomic_write_json(
        run_root / "definition.json", definition.model_dump(mode="json")
    )
    atomic_write_json(run_root / "state.json", state.model_dump(mode="json"))
    atomic_write_json(
        run_root / "read_model.json", read_model.model_dump(mode="json")
    )
    (run_root / "events.jsonl").write_text(
        event.model_dump_json() + "\n", encoding="utf-8"
    )

    restored_definition = GraphRunDefinition.model_validate(
        read_json(run_root / "definition.json")
    )
    restored_state = restore_route_run_state(
        restored_definition,
        read_json(run_root / "state.json"),
    )
    restored_read_model = restore_route_run_read_model(
        restored_definition,
        read_json(run_root / "read_model.json"),
    )
    restored_event = restore_route_run_event(
        restored_definition,
        json.loads((run_root / "events.jsonl").read_text(encoding="utf-8")),
    )

    assert restored_state == state
    assert restored_read_model == read_model
    assert restored_event == event
    assert tuple(restored_state.stage_status) == restored_definition.stage_ids
    assert tuple(stage.stage_id for stage in restored_read_model.stage_manifest) == (
        restored_definition.stage_ids
    )
    assert restored_event.creation_route_id == route.route_id


def test_state_rejects_missing_and_unknown_dynamic_stage_keys() -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY)
    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["stage_status"].pop("cover")

    with pytest.raises(ValueError, match="must cover every compiled route stage"):
        restore_route_run_state(definition, payload)

    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["artifact_refs"]["scene_deck"] = "artifact-outside-route"
    with pytest.raises(ValueError, match="outside the compiled route"):
        restore_route_run_state(definition, payload)


def test_state_rejects_route_identity_drift_and_unit_on_aggregate_stage() -> None:
    definition = _definition(LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY)
    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["route_revision"] = "r99"

    with pytest.raises(ValueError, match="route identity"):
        restore_route_run_state(definition, payload)

    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["active_unit_ref"] = "unit-brief-1"
    with pytest.raises(ValueError, match="unitized route stage"):
        restore_route_run_state(definition, payload)


def test_state_rejects_retired_quality_mode_and_chapter_cursor() -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY)
    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["quality_mode"] = "balanced"
    payload["active_chapter_number"] = 1

    with pytest.raises(ValidationError, match="quality_mode|active_chapter_number"):
        restore_route_run_state(definition, payload)


def test_state_rejects_empty_artifact_refs_and_duplicate_operation_refs() -> None:
    definition = _definition(LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY)
    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["artifact_refs"]["brief"] = ""

    with pytest.raises(ValueError, match="cannot contain empty references"):
        restore_route_run_state(definition, payload)

    payload = initial_route_run_state(definition).model_dump(mode="json")
    payload["pending_operation_refs"] = ["operation-1", "operation-1"]
    with pytest.raises(ValueError, match="cannot contain duplicates"):
        restore_route_run_state(definition, payload)


def test_read_model_rejects_manifest_and_review_policy_drift() -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY)
    payload = initial_route_run_read_model(
        definition, updated_at=NOW
    ).model_dump(mode="json")
    payload["stage_manifest"][0]["label"] = "被篡改的阶段"

    with pytest.raises(ValueError, match="stage manifest does not match"):
        restore_route_run_read_model(definition, payload)

    payload = initial_route_run_read_model(
        definition, updated_at=NOW
    ).model_dump(mode="json")
    payload["review_policy_summary"]["warning_policy"] = "continue_and_surface"
    with pytest.raises(ValueError, match="ReviewPolicy summary does not match"):
        restore_route_run_read_model(definition, payload)


def test_read_model_rejects_wrong_artifact_kind_and_unknown_decision_stage() -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY)
    payload = initial_route_run_read_model(
        definition, updated_at=NOW
    ).model_dump(mode="json")
    payload["artifact_refs"]["brief"] = {
        "artifact_kind": "character_bible",
        "artifact_ref": "artifact-brief-1",
    }

    with pytest.raises(ValidationError, match="Artifact kind does not match"):
        RouteRunReadModel.model_validate(payload)

    payload = initial_route_run_read_model(
        definition, updated_at=NOW
    ).model_dump(mode="json")
    payload["pending_decisions"] = [
        {
            "decision_id": "decision-outside-route",
            "stage_id": "scene_deck",
            "kind": "accept",
        }
    ]
    with pytest.raises(ValidationError, match="unknown stage"):
        RouteRunReadModel.model_validate(payload)


def test_terminal_read_model_rejects_pending_decision_authority() -> None:
    definition = _definition(LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY)
    payload = initial_route_run_read_model(
        definition, updated_at=NOW
    ).model_dump(mode="json")
    payload["status"] = "failed"
    payload["stage_status"]["brief"] = "failed"
    payload["pending_decisions"] = [
        {
            "decision_id": "decision-brief-failed",
            "stage_id": "brief",
            "artifact_ref": "candidate-brief",
            "kind": "route_stage_decision",
            "domain_revision": 0,
            "allowed_actions": ["accept", "cancel"],
            "redraft_limit": 0,
            "redraft_used": 0,
        }
    ]

    with pytest.raises(ValidationError, match="Terminal read model"):
        RouteRunReadModel.model_validate(payload)


def test_event_rejects_unknown_stage_wrong_artifact_and_route_drift() -> None:
    definition = _definition(LONG_NOVEL_ROUTE, LONG_NOVEL_REVIEW_POLICY)
    event = create_route_run_event(
        definition,
        event_id="event-book-architecture",
        sequence=1,
        occurred_at=NOW,
        type="artifact.committed",
        stage_id="book_architecture",
        artifact_kind="book_architecture",
    )
    payload = event.model_dump(mode="json")
    payload["stage_id"] = "story_map"

    with pytest.raises(ValueError, match="not part of route"):
        restore_route_run_event(definition, payload)

    payload = event.model_dump(mode="json")
    payload["artifact_kind"] = "story_map"
    with pytest.raises(ValueError, match="Artifact kind does not match"):
        restore_route_run_event(definition, payload)

    payload = event.model_dump(mode="json")
    payload["route_manifest_digest"] = "f" * 64
    with pytest.raises(ValueError, match="route identity"):
        restore_route_run_event(definition, payload)


def test_event_rejects_unit_on_aggregate_stage_and_retired_fields() -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE, SCREENPLAY_REVIEW_POLICY)
    event = create_route_run_event(
        definition,
        event_id="event-cast",
        sequence=1,
        occurred_at=NOW,
        type="stage.started",
        stage_id="cast",
    )
    payload = event.model_dump(mode="json")
    payload["unit_ref"] = "cast-unit-1"

    with pytest.raises(ValueError, match="unitized route stage"):
        restore_route_run_event(definition, payload)

    payload = event.model_dump(mode="json")
    payload["quality_mode"] = "fast"
    payload["chapter_id"] = "chapter-1"
    with pytest.raises(ValidationError, match="quality_mode|chapter_id"):
        restore_route_run_event(definition, payload)


def test_export_ready_event_requires_export_stage() -> None:
    definition = _definition(SHORT_NOVEL_ROUTE, SHORT_NOVEL_REVIEW_POLICY)

    with pytest.raises(ValueError, match="must belong to the Export stage"):
        create_route_run_event(
            definition,
            event_id="event-export-wrong-stage",
            sequence=1,
            occurred_at=NOW,
            type="export.ready",
            stage_id="cover",
        )


def test_phase32_projection_contracts_have_no_fixed_stage_dependencies() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "novel_workflow"
    source = "\n".join(
        (source_root / path).read_text(encoding="utf-8")
        for path in (
            "runtime/graph/route_run_state.py",
            "storage/route_run_read_model.py",
            "storage/route_run_event.py",
        )
    )

    for retired_term in (
        "STAGE_ORDER",
        "PHASE27_EDGES",
        "quality_mode",
        "active_chapter_number",
        "chapter_id",
        '"fast"',
        '"balanced"',
        '"deep"',
    ):
        assert retired_term not in source
