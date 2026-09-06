"""Durable start/resume orchestration for the dormant Phase 32 runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.orchestration.phase32_failure_projection import (
    project_phase32_execution_failure,
)
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_graph_execution import (
    Phase32GraphExecutionService,
    Phase32StepResult,
    project_phase32_read_model,
)
from novel_workflow.orchestration.phase32_run_preflight import (
    Phase32RunPreflight,
)
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.runtime.graph.route_graph import RouteGraphDriver
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptStore,
)
from novel_workflow.storage.phase32_execution_lock import (
    Phase32ExecutionLockTimeout,
    Phase32RunExecutionLock,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


class Phase32DecisionCommand(BaseModel):
    """The exact user command that may resume a pending graph interrupt."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    decision_id: str = Field(min_length=1, max_length=240)
    action: Literal["accept", "regenerate", "retry_writeback", "cancel"]
    domain_revision: int = Field(ge=0)
    direction: str = Field(default="", max_length=4_000)
    draft_ref: str = Field(default="", max_length=240)

    @model_validator(mode="after")
    def validate_direction(self) -> "Phase32DecisionCommand":
        if self.action == "regenerate" and not self.direction.strip():
            raise ValueError("Directed regeneration requires a non-empty direction")
        if self.draft_ref and self.action != "accept":
            raise ValueError("Only an accept decision may reference an author draft")
        return self


class Phase32FailureRecoveryCommand(BaseModel):
    """One explicit, idempotent regeneration of a failed Provider stage."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    recovery_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    domain_revision: int = Field(ge=0)
    direction: str = Field(min_length=1, max_length=4_000)


class Phase32ExecutionConflict(ValueError):
    code = "phase32_execution_conflict"


class Phase32ExecutionLockConflict(Phase32ExecutionConflict):
    code = "phase32_execution_lock_timeout"


class Phase32RunAdmissionRequired(Phase32ExecutionConflict):
    code = "phase32_run_admission_required"


@dataclass(frozen=True, slots=True)
class Phase32ExecutionOutcome:
    result: Phase32StepResult
    reused: bool = False

    @property
    def record(self) -> Phase32RunRecord:
        return self.result.record


DriverFactory = Callable[[GraphRunDefinition], RouteGraphDriver]
RunAdmission = Callable[[GraphRunDefinition], object]


class Phase32RunExecutionService:
    """Own durable checkpoint lifetime and idempotent decision submission."""

    def __init__(
        self,
        repository: Phase32RunRepository,
        *,
        checkpoint_root: Path,
        driver_factory: DriverFactory,
        decisions: Phase32DecisionReceiptStore,
        run_admission: RunAdmission | None = None,
        preflight: Phase32RunPreflight | None = None,
        artifact_editing: Phase32ArtifactEditingService | None = None,
        execution_lock_root: Path | None = None,
        execution_lock_timeout_seconds: float = 30.0,
    ) -> None:
        self.repository = repository
        self.checkpoint_root = checkpoint_root
        self.driver_factory = driver_factory
        self.decisions = decisions
        self.run_admission = run_admission
        self.artifact_editing = artifact_editing
        self.preflight = preflight or Phase32RunPreflight()
        self.graph_execution = Phase32GraphExecutionService(
            repository,
            preflight=self.preflight,
        )
        self._run_locks: dict[str, asyncio.Lock] = {}
        self.execution_locks = Phase32RunExecutionLock(
            execution_lock_root or repository.root / "execution_locks"
        )
        self.execution_lock_timeout_seconds = execution_lock_timeout_seconds

    async def start(self, run_id: str) -> Phase32ExecutionOutcome:
        """Start a created/running Run, or return its durable frontier."""

        try:
            async with self._run_guard(run_id):
                current = self._validated_record(run_id)
                if current.state.status in {
                    "awaiting_decision",
                    "image_deferred",
                    "completed",
                    "cancelled",
                }:
                    return Phase32ExecutionOutcome(
                        result=_existing_result(current),
                        reused=True,
                    )
                if current.state.status == "failed":
                    raise Phase32ExecutionConflict(
                        "A failed Run requires an explicit recovery path before start"
                    )
                self._require_run_admission(current.definition)
                result = await self._step(current, resume=None)
                return Phase32ExecutionOutcome(result=result)
        except Phase32ExecutionLockTimeout as exc:
            raise Phase32ExecutionLockConflict(str(exc)) from exc

    async def resume(
        self,
        run_id: str,
        command: Phase32DecisionCommand | dict[str, Any],
    ) -> Phase32ExecutionOutcome:
        """Submit one exact decision command and resume the durable graph."""

        parsed = (
            command
            if isinstance(command, Phase32DecisionCommand)
            else Phase32DecisionCommand.model_validate(command)
        )
        try:
            async with self._run_guard(run_id):
                current = self._validated_record(run_id)
                operation_key = f"decision:{parsed.decision_id}"
                existing = self.decisions.find(run_id, operation_key)
                if existing is not None:
                    _validate_repeated_command(existing.command, parsed)
                if existing is not None and existing.status == "succeeded":
                    return Phase32ExecutionOutcome(
                        result=_existing_result(current),
                        reused=True,
                    )
                if (
                    existing is not None
                    and existing.status == "pending"
                    and parsed.action == "regenerate"
                    and current.state.status == "failed"
                ):
                    reconciled = self._reconcile_terminal_regeneration(
                        current,
                        operation_key=operation_key,
                        command=parsed,
                    )
                    if reconciled is not None:
                        return Phase32ExecutionOutcome(
                            result=_existing_result(reconciled),
                            reused=True,
                        )

                active = next(
                    (
                        decision
                        for decision in current.read_model.pending_decisions
                        if decision.decision_id == parsed.decision_id
                    ),
                    None,
                )
                if active is None:
                    if existing is not None and existing.status == "pending":
                        self.decisions.succeed(
                            run_id=run_id,
                            operation_key=operation_key,
                            result=_reconciled_result(current),
                        )
                        return Phase32ExecutionOutcome(
                            result=_existing_result(current),
                            reused=True,
                        )
                    raise Phase32ExecutionConflict(
                        "Decision is not pending on the current Phase 32 Run"
                    )

                if active.domain_revision is None or not active.allowed_actions:
                    raise Phase32ExecutionConflict(
                        "Historical decision projection is read-only because its authority is incomplete"
                    )
                if parsed.domain_revision != active.domain_revision:
                    raise Phase32ExecutionConflict("Decision domain revision is stale")
                if parsed.action not in active.allowed_actions:
                    raise Phase32ExecutionConflict(
                        "Decision action is not allowed by the frozen ReviewPolicy"
                    )
                resolved_command = parsed.model_dump(mode="json")
                resolved_command["source_artifact_ref"] = active.artifact_ref
                candidate_ref = active.artifact_ref
                if parsed.draft_ref:
                    if self.artifact_editing is None:
                        raise Phase32ExecutionConflict(
                            "Phase 32 Artifact editing is not registered in this process"
                        )
                    candidate_ref = self.artifact_editing.materialize_accept_candidate(
                        run_id,
                        parsed.decision_id,
                        parsed.draft_ref,
                    ).artifact_ref
                resolved_command["candidate_ref"] = candidate_ref

                receipt = self.decisions.begin(
                    run_id=run_id,
                    operation_key=operation_key,
                    decision_id=parsed.decision_id,
                    command=resolved_command,
                )
                if receipt.status == "succeeded":
                    return Phase32ExecutionOutcome(
                        result=_existing_result(current),
                        reused=True,
                    )
                self._require_run_admission(current.definition)
                try:
                    result = await self._step(
                        current,
                        resume=resolved_command,
                    )
                except Exception:
                    self._reconcile_consumed_decision(
                        current.definition.run_id,
                        operation_key=operation_key,
                        command=parsed,
                    )
                    raise
                self.decisions.succeed(
                    run_id=run_id,
                    operation_key=operation_key,
                    result=_result_summary(result),
                )
                return Phase32ExecutionOutcome(result=result)
        except Phase32ExecutionLockTimeout as exc:
            raise Phase32ExecutionLockConflict(str(exc)) from exc

    async def recover(
        self,
        run_id: str,
        command: Phase32FailureRecoveryCommand | dict[str, Any],
    ) -> Phase32ExecutionOutcome:
        """Regenerate one terminal Provider-contract failure under frozen limits."""

        parsed = (
            command
            if isinstance(command, Phase32FailureRecoveryCommand)
            else Phase32FailureRecoveryCommand.model_validate(command)
        )
        operation_key = f"failure-recovery:{parsed.recovery_id}"
        try:
            async with self._run_guard(run_id):
                current = self._validated_record(run_id)
                existing = self.decisions.find(run_id, operation_key)
                if existing is not None:
                    _validate_repeated_recovery(existing.command, parsed)
                    if existing.status == "succeeded":
                        return Phase32ExecutionOutcome(
                            result=_existing_result(current),
                            reused=True,
                        )

                if current.state.status != "failed" or current.read_model.failure is None:
                    raise Phase32ExecutionConflict(
                        "Failure recovery requires a terminal failed Run"
                    )
                failure = current.read_model.failure
                if failure.code != "provider_contract_failed":
                    raise Phase32ExecutionConflict(
                        "Only a Provider contract failure supports directed regeneration"
                    )
                if parsed.domain_revision != current.state.domain_revision:
                    raise Phase32ExecutionConflict(
                        "Failure recovery domain revision is stale"
                    )
                stage_id = failure.stage_id
                stage = current.definition.stage(stage_id)
                if stage.provider_task_kind is None:
                    raise Phase32ExecutionConflict(
                        "Deterministic stages cannot use Provider failure recovery"
                    )
                redraft_limit = current.definition.route_contract.review_policy.directed_redraft_limit_by_stage.get(
                    stage_id,
                    0,
                )
                used = max(
                    current.state.stage_attempts.get(stage_id, 0),
                    current.state.pending_decision_redraft_count,
                )
                if used >= redraft_limit:
                    raise Phase32ExecutionConflict(
                        "Failure recovery exceeds the frozen ReviewPolicy redraft limit"
                    )

                command_payload = parsed.model_dump(mode="json")
                command_payload.update(
                    {
                        "stage_id": stage_id,
                        "failure_code": failure.code,
                        "checkpoint_id": current.read_model.checkpoint_id,
                    }
                )
                receipt = self.decisions.begin(
                    run_id=run_id,
                    operation_key=operation_key,
                    decision_id=parsed.recovery_id,
                    command=command_payload,
                )
                if receipt.status == "succeeded":
                    return Phase32ExecutionOutcome(
                        result=_existing_result(current),
                        reused=True,
                    )

                self._require_run_admission(current.definition)
                attempts = dict(current.state.stage_attempts)
                attempts[stage_id] = used + 1
                directions = dict(current.state.stage_revision_directions)
                directions[stage_id] = parsed.direction
                candidates = dict(current.state.candidate_artifact_refs)
                candidates.pop(stage_id, None)
                statuses = dict(current.state.stage_status)
                statuses[stage_id] = "running"
                recovery_state = current.state.model_copy(
                    update={
                        "status": "running",
                        "stage_status": statuses,
                        "candidate_artifact_refs": candidates,
                        "stage_attempts": attempts,
                        "stage_revision_directions": directions,
                        "pending_decision_action": "",
                        "pending_decision_redraft_count": 0,
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
                recovery_record = self.repository.commit_projection(
                    run_id,
                    state=recovery_state,
                    read_model=recovery_read_model,
                )
                try:
                    result = await self._step(recovery_record, resume=None)
                except Exception:
                    latest = self.repository.read(run_id)
                    self.decisions.succeed(
                        run_id=run_id,
                        operation_key=operation_key,
                        result={
                            "status": latest.state.status,
                            "active_stage_id": latest.state.active_stage_id,
                            "downstream_failure": latest.read_model.failure is not None,
                        },
                    )
                    raise
                self.decisions.succeed(
                    run_id=run_id,
                    operation_key=operation_key,
                    result=_result_summary(result),
                )
                return Phase32ExecutionOutcome(result=result)
        except Phase32ExecutionLockTimeout as exc:
            raise Phase32ExecutionLockConflict(str(exc)) from exc

    def _validated_record(self, run_id: str) -> Phase32RunRecord:
        current = self.repository.read(run_id)
        self.preflight.validate(
            current.definition,
            state=current.state,
            read_model=current.read_model,
        )
        return current

    def _require_run_admission(self, definition: GraphRunDefinition) -> None:
        if definition.scale_profile.payload.get("profile_kind") != (
            "continuity_acceptance"
        ):
            return
        if self.run_admission is None:
            raise Phase32RunAdmissionRequired(
                "Continuity acceptance execution requires a current Provider admission"
            )
        self.run_admission(definition)

    async def _step(
        self,
        current: Phase32RunRecord,
        *,
        resume: dict[str, Any] | None,
    ) -> Phase32StepResult:
        driver = self.driver_factory(current.definition)
        return await self._step_with_driver(current, driver=driver, resume=resume)

    async def _step_with_driver(
        self,
        current: Phase32RunRecord,
        *,
        driver: RouteGraphDriver,
        resume: dict[str, Any] | None,
    ) -> Phase32StepResult:
        async with open_phase32_checkpointer(self.checkpoint_root) as checkpointer:
            try:
                return await self.graph_execution.step(
                    current.definition.run_id,
                    driver=driver,
                    checkpointer=checkpointer,
                    resume=resume,
                )
            except Exception as exc:
                project_phase32_execution_failure(
                    self.repository,
                    current,
                    driver,
                    exc,
                    consumed_decision=resume,
                )
                raise

    @asynccontextmanager
    async def _run_guard(self, run_id: str):
        process_lock = self._lock_for(run_id)
        await process_lock.acquire()
        try:
            async with self.execution_locks.acquire(
                run_id,
                timeout_seconds=self.execution_lock_timeout_seconds,
            ):
                yield
        finally:
            process_lock.release()

    def _lock_for(self, run_id: str) -> asyncio.Lock:
        return self._run_locks.setdefault(run_id, asyncio.Lock())

    def _reconcile_consumed_decision(
        self,
        run_id: str,
        *,
        operation_key: str,
        command: Phase32DecisionCommand,
    ) -> None:
        """Complete a decision receipt when its command advanced the checkpoint."""

        try:
            latest = self.repository.read(run_id)
            remains_pending = any(
                item.decision_id == command.decision_id
                for item in latest.read_model.pending_decisions
            )
            terminal_regeneration = bool(
                command.action == "regenerate"
                and latest.state.status == "failed"
                and not remains_pending
            )
            if (
                latest.state.domain_revision <= command.domain_revision
                and not terminal_regeneration
            ):
                return
            if remains_pending:
                return
            self.decisions.succeed(
                run_id=run_id,
                operation_key=operation_key,
                result={
                    "status": latest.state.status,
                    "active_stage_id": latest.state.active_stage_id,
                    "downstream_failure": latest.read_model.failure is not None,
                },
            )
        except Exception:
            # Preserve the graph failure. A later idempotent submission can
            # reconcile the durable receipt from the already advanced state.
            return

    def _reconcile_terminal_regeneration(
        self,
        current: Phase32RunRecord,
        *,
        operation_key: str,
        command: Phase32DecisionCommand,
    ) -> Phase32RunRecord | None:
        """Repair the pre-fix projection of a consumed failed regeneration."""

        failure = current.read_model.failure
        active = next(
            (
                item
                for item in current.read_model.pending_decisions
                if item.decision_id == command.decision_id
            ),
            None,
        )
        if (
            failure is None
            or failure.retryable
            or failure.stage_id != current.state.active_stage_id
            or active is None
            or active.stage_id != failure.stage_id
        ):
            return None
        redraft_count = max(
            current.state.pending_decision_redraft_count,
            int(active.redraft_used or 0) + 1,
        )
        state = current.state.model_copy(
            update={
                "pending_decision_action": "regenerate",
                "pending_decision_redraft_count": redraft_count,
            }
        ).validate_for_definition(current.definition)
        read_model = current.read_model.model_copy(
            update={"pending_decisions": ()}
        ).validate_for_definition(current.definition)
        reconciled = self.repository.commit_projection(
            current.definition.run_id,
            state=state,
            read_model=read_model,
        )
        self.decisions.succeed(
            run_id=current.definition.run_id,
            operation_key=operation_key,
            result=_reconciled_result(reconciled),
        )
        return reconciled


def _existing_result(record: Phase32RunRecord) -> Phase32StepResult:
    return Phase32StepResult(
        record=record,
        interrupted=record.state.status == "awaiting_decision",
        decision=None,
    )


def _result_summary(result: Phase32StepResult) -> dict[str, Any]:
    return {
        "status": result.record.state.status,
        "active_stage_id": result.record.state.active_stage_id,
        "next_decision_id": (
            str(result.decision.get("decision_id")) if result.decision else ""
        ),
    }


def _reconciled_result(record: Phase32RunRecord) -> dict[str, Any]:
    return {
        "status": record.state.status,
        "active_stage_id": record.state.active_stage_id,
        "reconciled": True,
    }


def _validate_repeated_command(
    recorded: dict[str, Any],
    submitted: Phase32DecisionCommand,
) -> None:
    payload = submitted.model_dump(mode="json")
    if any(recorded.get(key) != value for key, value in payload.items()):
        raise Phase32ExecutionConflict(
            "Succeeded decision cannot be reused with different command data"
        )


def _validate_repeated_recovery(
    recorded: dict[str, Any],
    submitted: Phase32FailureRecoveryCommand,
) -> None:
    payload = submitted.model_dump(mode="json")
    if any(recorded.get(key) != value for key, value in payload.items()):
        raise Phase32ExecutionConflict(
            "Failure recovery id cannot be reused with different command data"
        )


__all__ = [
    "Phase32DecisionCommand",
    "Phase32FailureRecoveryCommand",
    "Phase32ExecutionConflict",
    "Phase32ExecutionLockConflict",
    "Phase32ExecutionOutcome",
    "Phase32RunAdmissionRequired",
    "Phase32RunExecutionService",
]
