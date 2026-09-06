"""Route-aware preflight contract for a future Phase 32 execution entry."""

from __future__ import annotations

from dataclasses import dataclass

from novel_workflow.providers.phase32_contract import Phase32StageProviderBindingSnapshot
from novel_workflow.runtime.graph.route_run_state import RouteRunStateSnapshot
from novel_workflow.storage.route_run_read_model import RouteRunReadModel
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_INPUTS_CONTRACT_REVISION,
    PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.route_compiler import PHASE32_ARCHITECTURE_VERSION


class Phase32PreflightError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Phase32PreflightReport:
    run_id: str
    project_id: str
    creation_route_id: str
    route_revision: str
    route_manifest_digest: str
    definition_digest: str
    stage_ids: tuple[str, ...]
    provider_stage_ids: tuple[str, ...]
    active_stage_id: str
    status: str


class Phase32RunPreflight:
    """Validate frozen route, current input authority, and projections.

    Provider readiness and graph execution remain separate. This contract has
    no stores, network calls, or model selection logic.
    """

    def validate(
        self,
        definition: GraphRunDefinition,
        *,
        state: RouteRunStateSnapshot | None = None,
        read_model: RouteRunReadModel | None = None,
    ) -> Phase32PreflightReport:
        if definition.architecture_version != PHASE32_ARCHITECTURE_VERSION:
            raise Phase32PreflightError(
                "run_architecture_unsupported",
                "Only phase32-routes-v1 definitions may enter route preflight",
            )
        if state is not None:
            try:
                state.validate_for_definition(definition)
            except Exception as exc:
                raise Phase32PreflightError(
                    "state_projection_invalid",
                    "Route state does not match the frozen Run definition",
                ) from exc
        if read_model is not None:
            try:
                read_model.validate_for_definition(definition)
            except Exception as exc:
                raise Phase32PreflightError(
                    "read_model_projection_invalid",
                    "Route read model does not match the frozen Run definition",
                ) from exc
        if state is not None and read_model is not None:
            if state.status != read_model.status:
                raise Phase32PreflightError(
                    "projection_status_drift",
                    "Route state and read model statuses differ",
                )
            if state.active_stage_id != read_model.active_stage_id:
                raise Phase32PreflightError(
                    "projection_stage_drift",
                    "Route state and read model active stages differ",
                )
            if (
                state.active_amendment_id != read_model.active_amendment_id
                or state.stale_stage_ids != read_model.stale_stage_ids
                or state.historical_frozen_stage_ids
                != read_model.historical_frozen_stage_ids
            ):
                raise Phase32PreflightError(
                    "projection_amendment_drift",
                    "Route state and read model amendment projections differ",
                )
        stale_stage_ids = (
            state.stale_stage_ids
            if state is not None
            else read_model.stale_stage_ids
            if read_model is not None
            else ()
        )
        projected_status = (
            state.status
            if state is not None
            else read_model.status
            if read_model is not None
            else "created"
        )
        if projected_status == "needs_action" or stale_stage_ids:
            raise Phase32PreflightError(
                "stale_artifact_execution_blocked",
                "Run has stale Artifact dependencies and requires an explicit repair plan",
            )

        stage_ids = definition.stage_ids
        provider_stage_ids = definition.route_contract.provider_stage_ids
        bound_stage_ids = tuple(
            binding.stage_id for binding in definition.provider_bindings_by_stage
        )
        if bound_stage_ids != provider_stage_ids:
            raise Phase32PreflightError(
                "provider_binding_stage_mismatch",
                "Provider bindings must exactly follow the route Provider stages",
            )
        if "export" in provider_stage_ids:
            raise Phase32PreflightError(
                "export_provider_binding_invalid",
                "Deterministic Export cannot own a Provider binding",
            )
        if self._requires_frozen_creation_language(definition):
            expected_contract_id = phase32_inputs_contract_id(
                definition.creation_route_id
            )
            if (
                definition.inputs.contract_id != expected_contract_id
                or definition.inputs.contract_revision
                != PHASE32_INPUTS_CONTRACT_REVISION
                or definition.inputs.payload.get("creation_language")
                != PHASE32_CREATION_LANGUAGE
            ):
                raise Phase32PreflightError(
                    "creation_language_contract_invalid",
                    "Current Phase 32 Prompts require frozen zh-CN creation language inputs",
                )

        active_stage_id = (
            state.active_stage_id
            if state is not None
            else read_model.active_stage_id
            if read_model is not None
            else definition.route_contract.route_manifest.start_stage_id
        )
        status = (
            state.status
            if state is not None
            else read_model.status
            if read_model is not None
            else "created"
        )
        return Phase32PreflightReport(
            run_id=definition.run_id,
            project_id=definition.project_id,
            creation_route_id=definition.creation_route_id,
            route_revision=definition.route_revision,
            route_manifest_digest=definition.route_contract.route_manifest_digest,
            definition_digest=definition.definition_digest,
            stage_ids=stage_ids,
            provider_stage_ids=provider_stage_ids,
            active_stage_id=active_stage_id,
            status=status,
        )

    @staticmethod
    def _requires_frozen_creation_language(
        definition: GraphRunDefinition,
    ) -> bool:
        return any(
            PHASE32_LANGUAGE_PROMPT_CONTRACT_MARKER
            in Phase32StageProviderBindingSnapshot.model_validate(
                frozen.binding.payload
            ).task.prompt_template
            for frozen in definition.provider_bindings_by_stage
        )


__all__ = [
    "Phase32PreflightError",
    "Phase32PreflightReport",
    "Phase32RunPreflight",
]
