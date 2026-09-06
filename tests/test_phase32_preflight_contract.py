from __future__ import annotations

import pytest

from novel_workflow.orchestration.phase32_run_fixture import (
    phase32_fixture_provider_bindings,
)
from novel_workflow.orchestration.phase32_run_preflight import (
    Phase32PreflightError,
    Phase32RunPreflight,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.route_run_read_model import initial_route_run_read_model
from novel_workflow.workflows.frozen_route_contract import freeze_route_contract
from novel_workflow.workflows.graph_run_definition import (
    freeze_contract_payload,
    freeze_graph_run_definition,
)
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_INPUTS_CONTRACT_REVISION,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.review_policy import SHORT_NOVEL_REVIEW_POLICY
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE


NOW = "2026-08-23T13:00:00+08:00"


def _definition():
    route_contract = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id="workflow-short-novel",
    )
    return freeze_graph_run_definition(
        run_id="run-preflight-short",
        project_id="project-preflight",
        workflow_id="workflow-short-novel",
        workflow_revision="route-r1",
        workflow_digest="c" * 64,
        route_contract=route_contract,
        scale_profile=freeze_contract_payload(
            contract_id="scale.short_novel",
            contract_revision="r1",
            payload={"target": 12_000},
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id("short_novel"),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "route-aware preflight",
            },
        ),
        provider_bindings_by_stage=bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at=NOW,
    )


def _projection_pair():
    definition = _definition()
    state = initial_route_run_state(definition)
    read_model = initial_route_run_read_model(definition, updated_at=NOW)
    return definition, state, read_model


def test_phase32_preflight_returns_route_manifest_and_projection_identity() -> None:
    definition, state, read_model = _projection_pair()
    report = Phase32RunPreflight().validate(
        definition,
        state=state,
        read_model=read_model,
    )
    assert report.creation_route_id == "short_novel"
    assert report.stage_ids == definition.stage_ids
    assert report.provider_stage_ids == definition.route_contract.provider_stage_ids
    assert report.active_stage_id == "brief"
    assert report.status == "created"


def test_phase32_preflight_rejects_projection_drift() -> None:
    definition, state, read_model = _projection_pair()
    bad_state = state.model_copy(update={"active_stage_id": "text"})
    with pytest.raises(Phase32PreflightError) as exc:
        Phase32RunPreflight().validate(
            definition,
            state=bad_state,
            read_model=read_model,
        )
    assert exc.value.code == "projection_stage_drift"

    bad_read_model = read_model.model_copy(update={"status": "running"})
    with pytest.raises(Phase32PreflightError) as exc:
        Phase32RunPreflight().validate(
            definition,
            state=state,
            read_model=bad_read_model,
        )
    assert exc.value.code == "projection_status_drift"


def test_phase32_preflight_rejects_current_prompts_without_language_authority() -> None:
    definition, state, read_model = _projection_pair()
    invalid_definition = definition.model_copy(
        update={
            "inputs": freeze_contract_payload(
                contract_id="inputs.short_novel.v1",
                contract_revision="r1",
                payload={"creative_intent": "缺少冻结创作语言。"},
            )
        }
    )

    with pytest.raises(Phase32PreflightError) as exc:
        Phase32RunPreflight().validate(
            invalid_definition,
            state=state,
            read_model=read_model,
        )

    assert exc.value.code == "creation_language_contract_invalid"
