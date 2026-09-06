"""Thin operator harness over the production Phase 32 continuity services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.orchestration.phase32_continuity_acceptance import (
    Phase32ContinuityAcceptanceService,
    Phase32ContinuityBudgetLimits,
    PreparedPhase32ContinuityAcceptance,
)
from novel_workflow.orchestration.phase32_creation_service import (
    CreationPreparationRequest,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32DecisionCommand,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_live_candidate_authorization import (
    Phase32LiveCandidateAuthorizationService,
)
from novel_workflow.orchestration.phase32_release_evidence import (
    Phase32ReleaseEvidenceService,
)
from novel_workflow.output_contracts.phase32_release_evidence import (
    Phase32ContinuityEvidenceBundle,
)
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRecord


ReleaseStopReason = Literal[
    "awaiting_operator",
    "image_deferred",
    "needs_action",
    "failed",
    "cancelled",
    "unexpected_completion",
    "transition_limit",
]


class Phase32ReleaseStopPolicy(BaseModel):
    """Explicit decisions and stop bounds; defaults never auto-accept content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: Literal["phase32-continuity-release-stop.v1"] = (
        "phase32-continuity-release-stop.v1"
    )
    max_graph_transitions: int = Field(default=128, ge=1, le=512)
    auto_accept_stages: tuple[str, ...] = ()
    auto_retry_writeback: bool = False
    stop_before_image: Literal[True] = True
    stop_on_failure: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if len(self.auto_accept_stages) != len(set(self.auto_accept_stages)):
            raise ValueError("Release auto-accept stages must be unique")
        return self


@dataclass(frozen=True, slots=True)
class Phase32ReleaseHarnessOutcome:
    run_id: str
    record: Phase32RunRecord
    stop_reason: ReleaseStopReason
    graph_transitions: int


class Phase32ReleaseHarnessError(ValueError):
    code = "phase32_release_harness_failed"


class Phase32ReleaseHarness:
    """Coordinate existing services without owning stores, graph, or gateway."""

    def __init__(
        self,
        *,
        continuity: Phase32ContinuityAcceptanceService,
        execution: Phase32RunExecutionService,
        provider_operations: Phase32ProviderOperationStore,
        evidence: Phase32ReleaseEvidenceService,
        live_candidate_authorization: Phase32LiveCandidateAuthorizationService,
    ) -> None:
        self.continuity = continuity
        self.execution = execution
        self.provider_operations = provider_operations
        self.evidence = evidence
        self.live_candidate_authorization = live_candidate_authorization

    def prepare(
        self,
        request: CreationPreparationRequest,
        *,
        budget: Phase32ContinuityBudgetLimits,
    ) -> PreparedPhase32ContinuityAcceptance:
        prepared = self.continuity.prepare(request, budget=budget)
        self.live_candidate_authorization.authorize_run(
            prepared.definition,
            readiness=prepared.readiness,
            budget=prepared.budget,
        )
        return prepared

    async def advance(
        self,
        run_id: str,
        *,
        stop_policy: Phase32ReleaseStopPolicy,
    ) -> Phase32ReleaseHarnessOutcome:
        record = self.execution.repository.read(run_id)
        self.continuity.require_run(record.definition)
        unknown_stages = set(stop_policy.auto_accept_stages) - set(
            record.definition.stage_ids
        )
        if unknown_stages:
            raise Phase32ReleaseHarnessError(
                "Release stop policy references stages outside the frozen route"
            )

        transitions = 0
        while transitions < stop_policy.max_graph_transitions:
            record = self.execution.repository.read(run_id)
            self._require_text_only_operation_history(run_id)
            stopped = _stop_reason(record)
            if stopped is not None:
                return Phase32ReleaseHarnessOutcome(
                    run_id=run_id,
                    record=record,
                    stop_reason=stopped,
                    graph_transitions=transitions,
                )

            pending = record.read_model.pending_decisions
            if pending:
                if len(pending) != 1:
                    raise Phase32ReleaseHarnessError(
                        "Release harness requires exactly one active decision"
                    )
                decision = pending[0]
                action = _automatic_action(decision, stop_policy)
                if action is None:
                    return Phase32ReleaseHarnessOutcome(
                        run_id=run_id,
                        record=record,
                        stop_reason="awaiting_operator",
                        graph_transitions=transitions,
                    )
                if decision.domain_revision is None:
                    raise Phase32ReleaseHarnessError(
                        "Release decision is missing its frozen domain revision"
                    )
                await self.execution.resume(
                    run_id,
                    Phase32DecisionCommand(
                        decision_id=decision.decision_id,
                        action=action,
                        domain_revision=decision.domain_revision,
                    ),
                )
            else:
                await self.execution.start(run_id)
            transitions += 1

        record = self.execution.repository.read(run_id)
        return Phase32ReleaseHarnessOutcome(
            run_id=run_id,
            record=record,
            stop_reason="transition_limit",
            graph_transitions=transitions,
        )

    def finalize_evidence(self, run_id: str) -> Phase32ContinuityEvidenceBundle:
        bundle = self.evidence.export(run_id)
        return self.evidence.require_valid(run_id, bundle.bundle_ref)

    def _require_text_only_operation_history(self, run_id: str) -> None:
        for receipt in self.provider_operations.list(run_id):
            if ":image:" in receipt.operation_key:
                raise Phase32ReleaseHarnessError(
                    "Release harness observed an image Provider operation"
                )
            if ":collaboration:" in receipt.operation_key:
                raise Phase32ReleaseHarnessError(
                    "Release harness observed a collaboration Provider operation"
                )


def _automatic_action(decision: object, policy: Phase32ReleaseStopPolicy) -> str | None:
    allowed = tuple(getattr(decision, "allowed_actions", ()) or ())
    kind = str(getattr(decision, "kind", "") or "")
    stage_id = str(getattr(decision, "stage_id", "") or "")
    if kind == "writeback_recovery":
        if policy.auto_retry_writeback and "retry_writeback" in allowed:
            return "retry_writeback"
        return None
    if stage_id in policy.auto_accept_stages and "accept" in allowed:
        return "accept"
    return None


def _stop_reason(record: Phase32RunRecord) -> ReleaseStopReason | None:
    status = record.state.status
    if status == "image_deferred":
        return "image_deferred"
    if status == "needs_action":
        return "needs_action"
    if status == "failed":
        return "failed"
    if status == "cancelled":
        return "cancelled"
    if status == "completed":
        return "unexpected_completion"
    return None


__all__ = [
    "Phase32ReleaseHarness",
    "Phase32ReleaseHarnessError",
    "Phase32ReleaseHarnessOutcome",
    "Phase32ReleaseStopPolicy",
    "ReleaseStopReason",
]
