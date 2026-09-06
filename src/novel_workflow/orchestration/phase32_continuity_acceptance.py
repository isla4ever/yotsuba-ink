"""Private exact-12 preparation and Provider-admission authority."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
    Phase32CreationService,
    PreparedPhase32Run,
)
from novel_workflow.orchestration.phase32_live_candidate_authorization import (
    Phase32LiveCandidateAuthorizationService,
)
from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    admit_phase32_provider_readiness,
    continuity_acceptance_provider_readiness_policy,
    require_current_phase32_provider_readiness,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32StageProviderBindingSnapshot,
    Phase32WritebackProviderRequest,
)
from novel_workflow.providers.usage import ensure_phase32_text_pricing_ready
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessAdmission,
    Phase32ProviderReadinessStore,
)
from novel_workflow.storage.phase32_run_budget_store import Phase32RunBudgetStore
from novel_workflow.usage.phase32_run_budget import Phase32RunBudgetAdmissionService
from novel_workflow.usage.phase32_run_budget_contract import (
    Phase32ProviderBudgetAdmission,
    Phase32RunBudgetAuthorization,
    freeze_phase32_run_budget_authorization,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.workflow_ids import OFFICIAL_LONG_NOVEL_WORKFLOW_ID


Clock = Callable[[], datetime]
SecretResolver = Callable[[str], str | None]
_CONTINUITY_MAX_TRANSPORT_ATTEMPTS = 3


class Phase32ContinuityBudgetLimits(BaseModel):
    """Explicit operator limits; this private launcher has no spending default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_cost_usd: float = Field(gt=0, allow_inf_nan=False)
    max_operations: int = Field(gt=0)
    max_total_tokens: int = Field(gt=0)

    @field_validator(
        "max_cost_usd",
        "max_operations",
        "max_total_tokens",
        mode="before",
    )
    @classmethod
    def reject_boolean_limits(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Continuity acceptance budget limits cannot be boolean")
        return value


@dataclass(frozen=True, slots=True)
class PreparedPhase32ContinuityAcceptance:
    prepared: PreparedPhase32Run
    readiness: Phase32ProviderReadinessAdmission
    budget: Phase32RunBudgetAuthorization

    @property
    def definition(self) -> GraphRunDefinition:
        return self.prepared.definition


class Phase32ContinuityAdmissionError(ValueError):
    code = "phase32_continuity_admission_failed"


class Phase32ContinuityAcceptanceService:
    """Prepare, admit, and guard the controlled long-form Provider sample."""

    def __init__(
        self,
        *,
        creation: Phase32CreationService,
        readiness: Phase32ProviderReadinessStore,
        budgets: Phase32RunBudgetStore,
        budget_admission: Phase32RunBudgetAdmissionService,
        live_candidate_authorization: Phase32LiveCandidateAuthorizationService,
        secret_resolver: SecretResolver,
        clock: Clock | None = None,
    ) -> None:
        self.creation = creation
        self.readiness = readiness
        self.budgets = budgets
        self.budget_admission = budget_admission
        self.live_candidate_authorization = live_candidate_authorization
        self.secret_resolver = secret_resolver
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.readiness_policy = continuity_acceptance_provider_readiness_policy()

    def prepare(
        self,
        request: CreationPreparationRequest,
        *,
        budget: Phase32ContinuityBudgetLimits,
    ) -> PreparedPhase32ContinuityAcceptance:
        """Freeze all local authority without contacting a Provider."""

        prepared = self.creation.prepare_continuity_acceptance(request)
        definition = prepared.definition
        _require_private_definition(definition)
        observed_at = _utc(self.clock())
        authorization = self._authorize_budget(
            definition,
            budget=budget,
            authorized_at=observed_at,
        )
        admit_phase32_provider_readiness(
            definition,
            store=self.readiness,
            policy=self.readiness_policy,
            secret_resolver=self.secret_resolver,
            now=observed_at,
        )
        ready = require_current_phase32_provider_readiness(
            definition,
            store=self.readiness,
            policy=self.readiness_policy,
            now=observed_at,
        )
        return PreparedPhase32ContinuityAcceptance(
            prepared=prepared,
            readiness=ready,
            budget=authorization,
        )

    def require_run(self, definition: GraphRunDefinition) -> Phase32RunBudgetAuthorization:
        """Require current readiness plus budget authority for this definition."""

        _require_private_definition(definition)
        readiness = require_current_phase32_provider_readiness(
            definition,
            store=self.readiness,
            policy=self.readiness_policy,
            now=_utc(self.clock()),
        )
        try:
            authorization = self.budgets.read_authorization(definition.run_id)
        except FileNotFoundError as exc:
            raise Phase32ContinuityAdmissionError(
                "Continuity acceptance budget authorization is missing"
            ) from exc
        if authorization.definition_digest != definition.definition_digest:
            raise Phase32ContinuityAdmissionError(
                "Continuity acceptance budget authority targets another definition"
            )
        self.live_candidate_authorization.require_run_authorization(
            definition,
            readiness=readiness,
            budget=authorization,
        )
        return authorization

    def admit_text_operation(
        self,
        *,
        definition: GraphRunDefinition,
        request: Phase32ProviderRequest | Phase32WritebackProviderRequest,
        binding: Phase32StageProviderBindingSnapshot,
        request_signature: str,
        max_transport_attempts: int,
    ) -> Phase32ProviderBudgetAdmission:
        """Reserve a conservative bound for one exact text transport attempt."""

        self.require_run(definition)
        _require_frozen_request(definition, request, binding)
        reserved_tokens, reserved_cost = _text_reservation(request, binding)
        return self.budget_admission.admit(
            run_id=definition.run_id,
            definition_digest=definition.definition_digest,
            operation_key=request.operation_key,
            request_signature=request_signature,
            reserved_total_tokens=reserved_tokens,
            reserved_cost_usd=reserved_cost,
            max_transport_attempts=max_transport_attempts,
        ).admission

    def _authorize_budget(
        self,
        definition: GraphRunDefinition,
        *,
        budget: Phase32ContinuityBudgetLimits,
        authorized_at: datetime,
    ) -> Phase32RunBudgetAuthorization:
        try:
            existing = self.budgets.read_authorization(definition.run_id)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if (
                existing.definition_digest != definition.definition_digest
                or existing.max_cost_usd != budget.max_cost_usd
                or existing.max_operations != budget.max_operations
                or existing.max_total_tokens != budget.max_total_tokens
                or existing.max_transport_attempts
                != _CONTINUITY_MAX_TRANSPORT_ATTEMPTS
            ):
                raise Phase32ContinuityAdmissionError(
                    "Continuity acceptance budget authorization is immutable"
                )
            return existing
        return self.budgets.save_authorization(
            freeze_phase32_run_budget_authorization(
                run_id=definition.run_id,
                definition_digest=definition.definition_digest,
                max_cost_usd=budget.max_cost_usd,
                max_operations=budget.max_operations,
                max_total_tokens=budget.max_total_tokens,
                max_transport_attempts=_CONTINUITY_MAX_TRANSPORT_ATTEMPTS,
                authorized_at=authorized_at.isoformat(),
            )
        )


def _require_private_definition(definition: GraphRunDefinition) -> None:
    profile_kind = str(definition.scale_profile.payload.get("profile_kind") or "")
    if (
        definition.workflow_id != OFFICIAL_LONG_NOVEL_WORKFLOW_ID
        or definition.creation_route_id != "long_novel"
        or profile_kind != "continuity_acceptance"
    ):
        raise Phase32ContinuityAdmissionError(
            "Provider admission is private to official.long_novel exact-12 Runs"
        )


def _require_frozen_request(
    definition: GraphRunDefinition,
    request: Phase32ProviderRequest | Phase32WritebackProviderRequest,
    binding: Phase32StageProviderBindingSnapshot,
) -> None:
    frozen = next(
        (
            item
            for item in definition.provider_bindings_by_stage
            if item.stage_id == request.stage_id
        ),
        None,
    )
    binding_payload = binding.model_dump(mode="json")
    binding_digest = canonical_digest(binding_payload)
    execution = binding.execution
    if (
        request.run_id != definition.run_id
        or request.creation_route_id != definition.creation_route_id
        or request.route_revision != definition.route_revision
        or binding.creation_route_id != definition.creation_route_id
        or binding.workflow_id != definition.workflow_id
        or binding.stage_id != request.stage_id
        or frozen is None
        or frozen.binding.payload_digest != binding_digest
        or frozen.binding.payload != binding_payload
        or request.provider_binding_digest != binding_digest
        or request.provider_profile_id != execution.provider_profile_id
        or request.provider_template_id != execution.provider_template_id
        or request.model_id != execution.model_id
    ):
        raise Phase32ContinuityAdmissionError(
            "Provider budget reservation does not match the frozen Run request"
        )
    if isinstance(request, Phase32ProviderRequest) and (
        request.provider_task_kind != binding.task.provider_task_kind
        or request.artifact_kind != binding.task.artifact_kind
        or request.transport_task_name != binding.task.transport_task_name
        or request.output_schema_digest != binding.task.output_schema_digest
    ):
        raise Phase32ContinuityAdmissionError(
            "Provider budget reservation does not match the frozen stage task"
        )


def _text_reservation(
    request: Phase32ProviderRequest | Phase32WritebackProviderRequest,
    binding: Phase32StageProviderBindingSnapshot,
) -> tuple[int, float]:
    pricing = binding.execution.pricing_snapshot
    ensure_phase32_text_pricing_ready(pricing)
    schema = json.dumps(
        request.output_schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    # UTF-8 bytes are a conservative tokenizer-independent ceiling for BPE
    # input pieces. The fixed allowance covers roles and request framing.
    input_tokens = (
        len(request.rendered_prompt.encode("utf-8"))
        + len(schema.encode("utf-8"))
        + 512
    )
    output_tokens = binding.execution.model_settings.max_tokens
    input_rate = pricing.input_usd_per_million_tokens
    output_rate = pricing.output_usd_per_million_tokens
    if input_rate is None or output_rate is None:
        raise Phase32ContinuityAdmissionError(
            "Provider budget reservation requires known text token rates"
        )
    estimated_cost = round(
        (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000,
        12,
    )
    if estimated_cost <= 0:
        raise Phase32ContinuityAdmissionError(
            "Provider budget reservation must have a positive cost bound"
        )
    return input_tokens + output_tokens, estimated_cost


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Continuity acceptance clock must include a timezone")
    return value.astimezone(timezone.utc)


__all__ = [
    "Phase32ContinuityAcceptanceService",
    "Phase32ContinuityAdmissionError",
    "Phase32ContinuityBudgetLimits",
    "PreparedPhase32ContinuityAcceptance",
]
