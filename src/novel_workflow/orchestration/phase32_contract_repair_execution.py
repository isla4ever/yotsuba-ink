"""Checkpoint-safe graph reinjection for a validated contract repair."""

from __future__ import annotations

from typing import Any

from novel_workflow.orchestration.phase32_execution_service import (
    Phase32ExecutionConflict,
    Phase32ExecutionLockConflict,
    Phase32ExecutionOutcome,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32StepResult,
    project_phase32_read_model,
)
from novel_workflow.runtime.graph.route_graph import (
    RouteGraphDriver,
    RouteStageCandidate,
)
from novel_workflow.storage.phase32_execution_lock import Phase32ExecutionLockTimeout
from novel_workflow.storage.phase32_run_repository import Phase32RunRecord
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


async def resume_phase32_contract_repair(
    execution: Phase32RunExecutionService,
    run_id: str,
    *,
    expected_definition_digest: str,
    expected_domain_revision: int,
    stage_id: str,
    candidate_ref: str,
    repair_receipt_ref: str,
    provider_receipt_ref: str,
) -> Phase32ExecutionOutcome:
    """Inject one local candidate and stop at a fresh explicit decision."""

    try:
        async with execution._run_guard(run_id):
            current = execution._validated_record(run_id)
            _validate_authority(
                current,
                expected_definition_digest=expected_definition_digest,
                expected_domain_revision=expected_domain_revision,
                stage_id=stage_id,
                candidate_ref=candidate_ref,
                repair_receipt_ref=repair_receipt_ref,
                provider_receipt_ref=provider_receipt_ref,
            )
            existing = next(
                (
                    decision
                    for decision in current.read_model.pending_decisions
                    if decision.stage_id == stage_id
                    and decision.artifact_ref == candidate_ref
                ),
                None,
            )
            if existing is not None and current.state.status == "awaiting_decision":
                return Phase32ExecutionOutcome(
                    result=_existing_result(current),
                    reused=True,
                )
            if current.state.status != "failed" or current.read_model.failure is None:
                raise Phase32ExecutionConflict(
                    "Contract repair requires a terminal failed Run"
                )
            failure = current.read_model.failure
            if (
                failure.code != "provider_contract_failed"
                or failure.stage_id != stage_id
                or current.state.active_stage_id != stage_id
            ):
                raise Phase32ExecutionConflict(
                    "Contract repair does not match the active Provider contract failure"
                )
            stage = current.definition.stage(stage_id)
            if stage_id not in (
                current.definition.route_contract.review_policy.mandatory_decision_stages
            ):
                raise Phase32ExecutionConflict(
                    "Contract repair requires an explicit stage decision gate"
                )
            unit_ref = (
                current.state.active_unit_ref
                if stage.unitization == "sequential_units"
                else ""
            )
            candidate = RouteStageCandidate(
                artifact_ref=candidate_ref,
                unit_ref=unit_ref,
            )
            driver = execution.driver_factory(current.definition)
            await driver.validate_stage(
                definition=current.definition,
                state=current.state,
                stage=stage,
                candidate=candidate,
            )

            repair_driver = _ContractRepairDriver(
                driver,
                stage_id=stage_id,
                candidate=candidate,
            )
            if current.state.pending_decision_action == "regenerate":
                source_command = _failed_regeneration_command(
                    execution,
                    current,
                    stage_id,
                )
                result = await execution._step_with_driver(
                    current,
                    driver=repair_driver,
                    # LangGraph retains the already consumed interrupt value
                    # after a post-resume node failure. Replaying the exact
                    # command lets the local driver replace only its result.
                    resume=source_command,
                )
                return Phase32ExecutionOutcome(result=result)

            if current.state.pending_decision_action not in {"", "accept"}:
                raise Phase32ExecutionConflict(
                    "Contract repair checkpoint action is not recoverable"
                )
            recovery_record = _project_local_retry(execution, current, stage_id)
            result = await execution._step_with_driver(
                recovery_record,
                driver=repair_driver,
                resume=None,
            )
            return Phase32ExecutionOutcome(result=result)
    except Phase32ExecutionLockTimeout as exc:
        raise Phase32ExecutionLockConflict(str(exc)) from exc


def _validate_authority(
    current: Phase32RunRecord,
    *,
    expected_definition_digest: str,
    expected_domain_revision: int,
    stage_id: str,
    candidate_ref: str,
    repair_receipt_ref: str,
    provider_receipt_ref: str,
) -> None:
    if not repair_receipt_ref or not provider_receipt_ref or not candidate_ref:
        raise Phase32ExecutionConflict("Contract repair provenance is incomplete")
    if current.definition.definition_digest != expected_definition_digest:
        raise Phase32ExecutionConflict("Contract repair definition digest is stale")
    if current.state.domain_revision != expected_domain_revision:
        raise Phase32ExecutionConflict("Contract repair domain revision is stale")
    current.definition.stage(stage_id)


def _failed_regeneration_command(
    execution: Phase32RunExecutionService,
    current: Phase32RunRecord,
    stage_id: str,
) -> dict[str, Any]:
    source_candidate_ref = current.state.candidate_artifact_refs.get(stage_id, "")
    if not source_candidate_ref:
        raise Phase32ExecutionConflict(
            "Failed regeneration checkpoint has no source candidate"
        )
    source_decision_id = f"{current.definition.run_id}:{stage_id}:{source_candidate_ref}"
    source_receipt = execution.decisions.find(
        current.definition.run_id,
        f"decision:{source_decision_id}",
    )
    if (
        source_receipt is None
        or source_receipt.status != "succeeded"
        or source_receipt.command.get("action") != "regenerate"
    ):
        raise Phase32ExecutionConflict(
            "Failed regeneration decision provenance is incomplete"
        )
    return dict(source_receipt.command)


def _project_local_retry(
    execution: Phase32RunExecutionService,
    current: Phase32RunRecord,
    stage_id: str,
) -> Phase32RunRecord:
    statuses = dict(current.state.stage_status)
    statuses[stage_id] = "running"
    candidates = dict(current.state.candidate_artifact_refs)
    candidates.pop(stage_id, None)
    recovery_state = current.state.model_copy(
        update={
            "status": "running",
            "stage_status": statuses,
            "candidate_artifact_refs": candidates,
            "pending_decision_action": "",
            "failure": None,
        }
    ).validate_for_definition(current.definition)
    recovery_read_model = project_phase32_read_model(
        current.read_model,
        current.definition,
        recovery_state,
        decision=None,
        checkpoint_id=current.read_model.checkpoint_id,
        provider_usage=current.read_model.provider_usage,
    )
    return execution.repository.commit_projection(
        current.definition.run_id,
        state=recovery_state,
        read_model=recovery_read_model,
    )


class _ContractRepairDriver:
    """Allow exactly one local candidate injection and forbid Provider fallback."""

    def __init__(
        self,
        delegate: RouteGraphDriver,
        *,
        stage_id: str,
        candidate: RouteStageCandidate,
    ) -> None:
        self.delegate = delegate
        self.stage_id = stage_id
        self.candidate = candidate
        self.injected = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    async def generate_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: Any,
        stage: Any,
        direction: str = "",
    ) -> RouteStageCandidate:
        if self.injected or stage.stage_id != self.stage_id:
            raise Phase32ExecutionConflict(
                "Contract repair cannot fall through to another Provider generation"
            )
        self.injected = True
        return self.candidate


def _existing_result(record: Phase32RunRecord) -> Phase32StepResult:
    return Phase32StepResult(
        record=record,
        interrupted=record.state.status == "awaiting_decision",
        decision=None,
    )


__all__ = ["resume_phase32_contract_repair"]
