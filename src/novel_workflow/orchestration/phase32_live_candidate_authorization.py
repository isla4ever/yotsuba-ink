"""Bind zero-call facts to one private Phase 32 live candidate Run."""

from __future__ import annotations

from novel_workflow.orchestration.phase32_live_candidate_preflight import (
    Phase32LiveCandidatePreflightService,
)
from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.storage.phase32_live_candidate_preflight_store import (
    Phase32LiveCandidatePreflightStore,
)
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessAdmission,
)
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32LiveCandidateAuthorization,
    Phase32LiveCandidateEnvironmentReport,
    build_live_candidate_authorization,
)
from novel_workflow.usage.phase32_run_budget_contract import (
    Phase32RunBudgetAuthorization,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.templates import (
    DEEPSEEK_PRO_MODEL,
    DEEPSEEK_PROVIDER_ID,
)


_DEEPSEEK_TEMPLATE_ID = "deepseek-text"


class Phase32LiveCandidateAuthorizationError(ValueError):
    code = "phase32_live_candidate_authorization_failed"


class Phase32LiveCandidateAuthorizationService:
    """Issue and revalidate the final zero-call authority bundle."""

    def __init__(
        self,
        *,
        preflight: Phase32LiveCandidatePreflightService,
        store: Phase32LiveCandidatePreflightStore,
    ) -> None:
        self.preflight = preflight
        self.store = store

    def authorize_run(
        self,
        definition: GraphRunDefinition,
        *,
        readiness: Phase32ProviderReadinessAdmission,
        budget: Phase32RunBudgetAuthorization,
    ) -> Phase32LiveCandidateAuthorization:
        """Bind the current environment, definition, readiness, and budget."""

        report = self.preflight.assess_environment()
        if report.verdict != "ready_for_budget_authorization":
            raise Phase32LiveCandidateAuthorizationError(
                "Live candidate environment is not ready for authorization"
            )
        self._require_run_authority_identity(
            definition,
            readiness=readiness,
            budget=budget,
            report=report,
        )
        payload: dict[str, object] = {
            "authorization_version": "phase32-live-candidate-authorization.v1",
            "issued_at": report.observed_at,
            "run_id": definition.run_id,
            "definition_digest": definition.definition_digest,
            "environment_report_ref": report.report_ref,
            "pricing_attestation_ref": report.pricing_attestation_ref,
            "profile_digest": report.profile_digest,
            "pricing_snapshot_ref": report.pricing_snapshot_ref,
            "readiness_admission_ref": readiness.admission_ref,
            "readiness_report_digest": readiness.report_digest,
            "budget_authorization_ref": budget.authorization_ref,
            "max_cost_usd": budget.max_cost_usd,
            "max_operations": budget.max_operations,
            "max_total_tokens": budget.max_total_tokens,
            "max_transport_attempts": budget.max_transport_attempts,
            "authorization_basis": "user_confirmed_limits",
            "text_only": True,
            "billable_call_count_at_issue": 0,
        }
        return self.store.write_authorization(
            build_live_candidate_authorization(payload)
        )

    def require_run_authorization(
        self,
        definition: GraphRunDefinition,
        *,
        readiness: Phase32ProviderReadinessAdmission,
        budget: Phase32RunBudgetAuthorization,
    ) -> Phase32LiveCandidateAuthorization:
        """Revalidate the full authority binding before Provider execution."""

        authorization = self.store.latest_authorization(definition.run_id)
        if authorization is None:
            raise Phase32LiveCandidateAuthorizationError(
                "Live candidate authorization is missing"
            )
        report = self.preflight.require_current_report(
            authorization.environment_report_ref
        )
        self._require_run_authority_identity(
            definition,
            readiness=readiness,
            budget=budget,
            report=report,
        )
        expected = {
            "definition_digest": definition.definition_digest,
            "environment_report_ref": report.report_ref,
            "pricing_attestation_ref": report.pricing_attestation_ref,
            "profile_digest": report.profile_digest,
            "pricing_snapshot_ref": report.pricing_snapshot_ref,
            "readiness_admission_ref": readiness.admission_ref,
            "readiness_report_digest": readiness.report_digest,
            "budget_authorization_ref": budget.authorization_ref,
            "max_cost_usd": budget.max_cost_usd,
            "max_operations": budget.max_operations,
            "max_total_tokens": budget.max_total_tokens,
            "max_transport_attempts": budget.max_transport_attempts,
        }
        if any(getattr(authorization, key) != value for key, value in expected.items()):
            raise Phase32LiveCandidateAuthorizationError(
                "Live candidate authorization differs from current Run authority"
            )
        return authorization

    @staticmethod
    def _require_run_authority_identity(
        definition: GraphRunDefinition,
        *,
        readiness: Phase32ProviderReadinessAdmission,
        budget: Phase32RunBudgetAuthorization,
        report: Phase32LiveCandidateEnvironmentReport,
    ) -> None:
        profile_kind = str(definition.scale_profile.payload.get("profile_kind") or "")
        if (
            definition.workflow_id != "official.long_novel"
            or definition.creation_route_id != "long_novel"
            or profile_kind != "continuity_acceptance"
            or readiness.run_id != definition.run_id
            or readiness.definition_digest != definition.definition_digest
            or readiness.verdict != "ready"
            or budget.run_id != definition.run_id
            or budget.definition_digest != definition.definition_digest
            or budget.max_transport_attempts != 3
        ):
            raise Phase32LiveCandidateAuthorizationError(
                "Live candidate Run authorities do not share one frozen identity"
            )
        if not report.pricing_snapshot_ref:
            raise Phase32LiveCandidateAuthorizationError(
                "Live candidate report is missing its pricing snapshot"
            )
        for frozen in definition.provider_bindings_by_stage:
            binding = Phase32StageProviderBindingSnapshot.model_validate(
                frozen.binding.payload
            )
            execution = binding.execution
            if (
                binding.image_execution is not None
                or execution.provider_profile_id != DEEPSEEK_PROVIDER_ID
                or execution.provider_template_id != _DEEPSEEK_TEMPLATE_ID
                or execution.model_id != DEEPSEEK_PRO_MODEL
                or execution.pricing_snapshot.snapshot_ref
                != report.pricing_snapshot_ref
            ):
                raise Phase32LiveCandidateAuthorizationError(
                    "Live candidate binding differs from the zero-call authority"
                )


__all__ = [
    "Phase32LiveCandidateAuthorizationError",
    "Phase32LiveCandidateAuthorizationService",
]
