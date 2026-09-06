"""Dormant no-Provider Phase 32 Run creation fixture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from novel_workflow.runtime.graph.route_run_state import RouteRunStateSnapshot
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_event import RouteRunEventEnvelope, create_route_run_event
from novel_workflow.storage.route_run_read_model import RouteRunReadModel
from novel_workflow.workflows.frozen_route_contract import canonical_digest, freeze_route_contract
from novel_workflow.workflows.graph_run_definition import (
    FrozenStageProviderBinding,
    GraphRunDefinition,
    freeze_contract_payload,
    freeze_graph_run_definition,
    freeze_phase32_scale_profile,
)
from novel_workflow.workflows.frozen_route_contract import FrozenRouteContract
from novel_workflow.workflows.definition_schemas import (
    ProviderModelPricing,
    ProviderProfile,
)
from novel_workflow.workflows.phase32_provider_binding import (
    build_phase32_provider_bindings,
)
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_INPUTS_CONTRACT_REVISION,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.phase32_scale import freeze_scale_profile
from novel_workflow.workflows.review_policy import (
    LONG_NOVEL_REVIEW_POLICY,
    SCREENPLAY_REVIEW_POLICY,
    SHORT_NOVEL_REVIEW_POLICY,
    ReviewPolicy,
)
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import (
    CreationRouteSpec,
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


_OFFICIAL_POLICIES: dict[str, ReviewPolicy] = {
    SCREENPLAY_SAMPLE_ROUTE.route_id: SCREENPLAY_REVIEW_POLICY,
    SHORT_NOVEL_ROUTE.route_id: SHORT_NOVEL_REVIEW_POLICY,
    LONG_NOVEL_ROUTE.route_id: LONG_NOVEL_REVIEW_POLICY,
}


@dataclass(frozen=True, slots=True)
class Phase32RunFixture:
    repository: Phase32RunRepository
    definition: GraphRunDefinition
    state: RouteRunStateSnapshot
    read_model: RouteRunReadModel
    first_event: RouteRunEventEnvelope


def create_phase32_run_fixture(
    root: Path,
    *,
    route: CreationRouteSpec,
    run_id: str,
    project_id: str,
    creative_intent: str,
    target: int | None = None,
    created_at: str = "2026-08-23T12:00:00+08:00",
    provider_profile: str = "phase32-fixture-provider",
    workflow_id: str | None = None,
    review_policy: ReviewPolicy | None = None,
) -> Phase32RunFixture:
    """Create one durable, route-aware Run without invoking a Provider."""

    try:
        selected_review_policy = review_policy or _OFFICIAL_POLICIES[route.route_id]
    except KeyError as exc:
        raise ValueError(f"No official Phase 32 ReviewPolicy for {route.route_id}") from exc
    if selected_review_policy.route_id != route.route_id:
        raise ValueError("Fixture ReviewPolicy route does not match the selected route")
    route_contract = freeze_route_contract(
        RouteGraphCompiler().compile(route), selected_review_policy
    )
    workflow_id = workflow_id or f"workflow-{route.route_id}"
    provider_bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id=workflow_id,
        provider_profile=provider_profile,
    )
    definition = freeze_graph_run_definition(
        run_id=run_id,
        project_id=project_id,
        workflow_id=workflow_id,
        workflow_revision=route.revision,
        workflow_digest=canonical_digest(
            {"workflow_id": workflow_id, "workflow_revision": route.revision}
        ),
        route_contract=route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_scale_profile(route.route_id, target=target)
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id(route.route_id),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": creative_intent,
            },
        ),
        provider_bindings_by_stage=provider_bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at=created_at,
    )
    repository = Phase32RunRepository(root)
    record = repository.create(definition, updated_at=created_at)
    running_stage_status = dict(record.state.stage_status)
    running_stage_status["brief"] = "running"
    record = repository.commit_projection(
        definition.run_id,
        state=record.state.model_copy(
            update={"status": "running", "stage_status": running_stage_status}
        ),
        read_model=record.read_model.model_copy(
            update={"status": "running", "stage_status": running_stage_status}
        ),
    )
    first_event = repository.append_event(
        create_route_run_event(
            definition,
            event_id=f"{run_id}-stage-brief-started",
            sequence=1,
            occurred_at=created_at,
            type="stage.started",
            stage_id="brief",
            status="running",
        )
    )
    return Phase32RunFixture(
        repository=repository,
        definition=record.definition,
        state=record.state,
        read_model=record.read_model,
        first_event=first_event,
    )


def phase32_fixture_provider_bindings(
    route_contract: FrozenRouteContract,
    *,
    workflow_id: str,
    provider_profile: str = "phase32-fixture-provider",
) -> tuple[FrozenStageProviderBinding, ...]:
    """Build executable, secret-free bindings for deterministic test gateways."""

    provider = ProviderProfile(
        id=provider_profile,
        name="Phase 32 fixture text Provider",
        kind="openai-compatible",
        template_id="deepseek-text",
        base_url="https://phase32-fixture.invalid/v1",
        default_model="phase32-fixture-model",
        model_pricing={
            "phase32-fixture-model": ProviderModelPricing(
                input_usd_per_million_tokens=0,
                output_usd_per_million_tokens=0,
                source_url="https://phase32-fixture.invalid/pricing",
                verified_at="2026-08-23T12:00:00+08:00",
                estimate_basis="published_rates",
                estimate_basis_note="Deterministic test fixture rates; no external billing.",
            )
        },
    )
    image_provider = ProviderProfile(
        id="phase32-fixture-image-provider",
        name="Phase 32 fixture image Provider",
        kind="openai-compatible-image",
        template_id="openai-compatible-image",
        base_url="https://phase32-fixture-image.invalid/v1",
        default_model="phase32-fixture-image-model",
        model_pricing={
            "phase32-fixture-image-model": ProviderModelPricing(
                fixed_output_usd=0,
                source_url="https://phase32-fixture.invalid/image-pricing",
                verified_at="2026-08-23T12:00:00+08:00",
                estimate_basis="fixed_output_estimate",
                estimate_basis_note="Deterministic fixture image rate; no external billing.",
            )
        },
    )
    return build_phase32_provider_bindings(
        route_contract.creation_route_id,
        route_contract.route_manifest,
        None,
        {provider.id: provider, image_provider.id: image_provider},
        workflow_id=workflow_id,
    )


__all__ = [
    "Phase32RunFixture",
    "create_phase32_run_fixture",
    "phase32_fixture_provider_bindings",
]
