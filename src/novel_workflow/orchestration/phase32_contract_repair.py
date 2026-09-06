"""Auditable zero-Provider repair of schema-valid contract-rejected Artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingError,
    validate_phase32_artifact_payload,
    validate_phase32_author_edit_identity,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32ExecutionOutcome,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_contract_repair_execution import (
    resume_phase32_contract_repair,
)
from novel_workflow.orchestration.phase32_stage_reference_validation import (
    Phase32StageReferenceError,
    validate_phase32_stage_references,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_contract_repair_store import (
    Phase32ContractRepairRecord,
    Phase32ContractRepairStore,
)
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceipt,
    Phase32ProviderOperationStore,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32ContractRepairCommand(BaseModel):
    """Exact source and revision authority for one human-supplied repair."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    repair_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    provider_receipt_ref: str = Field(
        pattern=r"^p32-provider-operation-[a-f0-9]{64}$"
    )
    provider_request_signature: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    domain_revision: int = Field(ge=0)
    source_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, Any]


class Phase32ContractFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=1_000)


class Phase32ContractQuarantine(BaseModel):
    """Author-facing, source-bound projection of a rejected Provider return."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    run_id: str
    creation_route_id: str
    stage_id: str
    definition_digest: str
    domain_revision: int
    provider_receipt_ref: str
    provider_request_signature: str
    source_payload_digest: str
    source_payload: dict[str, Any]
    eligible: bool
    findings: tuple[Phase32ContractFinding, ...]


class Phase32ContractRepairError(ValueError):
    code = "phase32_contract_repair_invalid"


class Phase32ContractRepairConflict(Phase32ContractRepairError):
    code = "phase32_contract_repair_conflict"


class Phase32ContractRepairNotEligible(Phase32ContractRepairError):
    code = "phase32_contract_repair_not_eligible"


@dataclass(frozen=True, slots=True)
class Phase32ContractRepairOutcome:
    repair: Phase32ContractRepairRecord
    run: Phase32RunRecord
    decision: dict[str, Any] | None
    reused: bool


class Phase32ContractRepairService:
    """Quarantine, validate, persist, and graph-resume one rejected payload."""

    def __init__(
        self,
        repository: Phase32RunRepository,
        artifacts: Phase32ArtifactStore,
        provider_operations: Phase32ProviderOperationStore,
        repairs: Phase32ContractRepairStore,
        execution: Phase32RunExecutionService,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.provider_operations = provider_operations
        self.repairs = repairs
        self.execution = execution

    def inspect(self, run_id: str, provider_receipt_ref: str) -> Phase32ContractQuarantine:
        current, receipt = self._current_source(run_id, provider_receipt_ref)
        source_payload = dict(receipt.raw_provider_payload or {})
        source_payload_digest = canonical_digest(source_payload)
        stage = current.definition.stage(receipt.stage_id)
        base = {
            "run_id": run_id,
            "creation_route_id": current.definition.creation_route_id,
            "stage_id": stage.stage_id,
            "definition_digest": current.definition.definition_digest,
            "domain_revision": current.state.domain_revision,
            "provider_receipt_ref": receipt.receipt_ref,
            "provider_request_signature": receipt.request_signature,
            "source_payload_digest": source_payload_digest,
            "source_payload": source_payload,
        }
        if stage.stage_id not in (
            current.definition.route_contract.review_policy.mandatory_decision_stages
        ):
            return Phase32ContractQuarantine(
                **base,
                eligible=False,
                findings=(
                    Phase32ContractFinding(
                        code="explicit_decision_gate_required",
                        message="合同修复只开放给冻结为显式人工决策的阶段。",
                    ),
                ),
            )
        try:
            artifact = validate_phase32_artifact_payload(
                current.definition,
                stage,
                source_payload,
            )
        except Phase32ArtifactEditingError:
            return Phase32ContractQuarantine(
                **base,
                eligible=False,
                findings=(
                    Phase32ContractFinding(
                        code="artifact_schema_invalid",
                        message="Provider 返回未通过 Artifact Schema，不能进入人工语义修复。",
                    ),
                ),
            )
        try:
            validate_phase32_stage_references(
                self.artifacts,
                current.definition,
                current.state.artifact_refs,
                stage.stage_id,
                artifact,
                active_unit_ref=current.state.active_unit_ref,
            )
        except Phase32StageReferenceError as exc:
            return Phase32ContractQuarantine(
                **base,
                eligible=True,
                findings=(
                    Phase32ContractFinding(
                        code="stage_reference_contract_invalid",
                        message=str(exc)[:1_000],
                    ),
                ),
            )
        return Phase32ContractQuarantine(
            **base,
            eligible=False,
            findings=(
                Phase32ContractFinding(
                    code="contract_rejection_not_repairable",
                    message="拒绝原因不能由受限的 Artifact 语义修复安全恢复。",
                ),
            ),
        )

    def inspect_current(self, run_id: str) -> Phase32ContractQuarantine:
        """Discover the current failed Stage's authoritative rejected return."""

        current = self.repository.read(run_id)
        failure = self._require_contract_failure(current)
        latest = max(
            (
                receipt
                for receipt in self.provider_operations.list(run_id)
                if receipt.stage_id == failure.stage_id
            ),
            key=lambda item: (item.updated_at, item.created_at, item.receipt_ref),
            default=None,
        )
        if latest is None:
            raise FileNotFoundError(
                f"Run {run_id!r} has no Provider receipt for failed Stage "
                f"{failure.stage_id!r}"
            )
        return self.inspect(run_id, latest.receipt_ref)

    async def repair(
        self,
        run_id: str,
        command: Phase32ContractRepairCommand | dict[str, Any],
    ) -> Phase32ContractRepairOutcome:
        parsed = (
            command
            if isinstance(command, Phase32ContractRepairCommand)
            else Phase32ContractRepairCommand.model_validate(command)
        )
        submitted_digest = canonical_digest(parsed.payload)
        existing = self.repairs.find(run_id, parsed.repair_id)
        if existing is not None:
            self._validate_existing(existing, parsed, submitted_digest)
            if existing.status == "succeeded":
                current = self.repository.read(run_id)
                return Phase32ContractRepairOutcome(
                    repair=existing,
                    run=current,
                    decision=self._pending_decision(current, existing),
                    reused=True,
                )
            outcome = await resume_phase32_contract_repair(
                self.execution,
                run_id,
                expected_definition_digest=existing.definition_digest,
                expected_domain_revision=existing.domain_revision,
                stage_id=existing.stage_id,
                candidate_ref=existing.candidate_ref,
                repair_receipt_ref=existing.repair_ref,
                provider_receipt_ref=existing.provider_receipt_ref,
            )
            return self._complete(existing, outcome)

        quarantine = self.inspect(run_id, parsed.provider_receipt_ref)
        self._validate_command_authority(quarantine, parsed)
        if not quarantine.eligible:
            raise Phase32ContractRepairNotEligible(
                quarantine.findings[0].message
            )
        current = self.repository.read(run_id)
        stage = current.definition.stage(quarantine.stage_id)
        source_artifact = validate_phase32_artifact_payload(
            current.definition,
            stage,
            quarantine.source_payload,
        )
        repaired_artifact = validate_phase32_artifact_payload(
            current.definition,
            stage,
            parsed.payload,
        )
        validate_phase32_author_edit_identity(
            stage.stage_id,
            source_artifact.model_dump(mode="json"),
            repaired_artifact,
            allow_rolling_detail_cast_scope_changes=True,
        )
        try:
            validate_phase32_stage_references(
                self.artifacts,
                current.definition,
                current.state.artifact_refs,
                stage.stage_id,
                repaired_artifact,
                active_unit_ref=current.state.active_unit_ref,
            )
        except Phase32StageReferenceError as exc:
            raise Phase32ContractRepairError(str(exc)) from exc
        source_operation_key = (
            f"contract-repair:{parsed.repair_id}:"
            f"{parsed.provider_receipt_ref}:{submitted_digest[:16]}"
        )
        candidate = self.artifacts.save_candidate(
            run_id=run_id,
            creation_route_id=current.definition.creation_route_id,
            stage_id=stage.stage_id,
            artifact=repaired_artifact,
            source_operation_key=source_operation_key,
        )
        repair = self.repairs.begin(
            repair_id=parsed.repair_id,
            run_id=run_id,
            definition_digest=parsed.definition_digest,
            domain_revision=parsed.domain_revision,
            stage_id=stage.stage_id,
            provider_receipt_ref=parsed.provider_receipt_ref,
            provider_request_signature=parsed.provider_request_signature,
            source_payload_digest=parsed.source_payload_digest,
            repaired_payload_digest=submitted_digest,
            candidate_ref=candidate.artifact_ref,
        )
        outcome = await resume_phase32_contract_repair(
            self.execution,
            run_id,
            expected_definition_digest=repair.definition_digest,
            expected_domain_revision=repair.domain_revision,
            stage_id=repair.stage_id,
            candidate_ref=repair.candidate_ref,
            repair_receipt_ref=repair.repair_ref,
            provider_receipt_ref=repair.provider_receipt_ref,
        )
        return self._complete(repair, outcome)

    def _current_source(
        self,
        run_id: str,
        provider_receipt_ref: str,
    ) -> tuple[Phase32RunRecord, Phase32ProviderOperationReceipt]:
        current = self.repository.read(run_id)
        failure = self._require_contract_failure(current)
        receipt = self.provider_operations.read_receipt_ref(
            run_id,
            provider_receipt_ref,
        )
        if (
            receipt.status != "contract_rejected"
            or receipt.stage_id != failure.stage_id
            or receipt.stage_id != current.state.active_stage_id
            or receipt.raw_provider_payload is None
        ):
            raise Phase32ContractRepairConflict(
                "Provider receipt does not match the active contract failure"
            )
        stage_receipts = [
            item
            for item in self.provider_operations.list(run_id)
            if item.stage_id == receipt.stage_id
        ]
        latest = max(
            stage_receipts,
            key=lambda item: (item.updated_at, item.created_at, item.receipt_ref),
            default=None,
        )
        if latest is None or latest.receipt_ref != receipt.receipt_ref:
            raise Phase32ContractRepairConflict(
                "Only the latest failed Provider return can enter quarantine"
            )
        return current, receipt

    @staticmethod
    def _require_contract_failure(current: Phase32RunRecord):
        if current.state.status != "failed" or current.read_model.failure is None:
            raise Phase32ContractRepairConflict(
                "Contract quarantine requires a terminal failed Run"
            )
        failure = current.read_model.failure
        if failure.code != "provider_contract_failed":
            raise Phase32ContractRepairConflict(
                "Only a Provider contract failure can enter quarantine"
            )
        return failure

    @staticmethod
    def _validate_command_authority(
        quarantine: Phase32ContractQuarantine,
        command: Phase32ContractRepairCommand,
    ) -> None:
        if (
            command.definition_digest != quarantine.definition_digest
            or command.domain_revision != quarantine.domain_revision
            or command.provider_request_signature
            != quarantine.provider_request_signature
            or command.source_payload_digest != quarantine.source_payload_digest
        ):
            raise Phase32ContractRepairConflict(
                "Contract repair source or Run authority is stale"
            )

    @staticmethod
    def _validate_existing(
        existing: Phase32ContractRepairRecord,
        command: Phase32ContractRepairCommand,
        submitted_digest: str,
    ) -> None:
        if (
            existing.provider_receipt_ref != command.provider_receipt_ref
            or existing.provider_request_signature
            != command.provider_request_signature
            or existing.definition_digest != command.definition_digest
            or existing.domain_revision != command.domain_revision
            or existing.source_payload_digest != command.source_payload_digest
            or existing.repaired_payload_digest != submitted_digest
        ):
            raise Phase32ContractRepairConflict(
                "Contract repair id cannot be reused with different command data"
            )

    def _complete(
        self,
        repair: Phase32ContractRepairRecord,
        outcome: Phase32ExecutionOutcome,
    ) -> Phase32ContractRepairOutcome:
        decision = self._pending_decision(outcome.record, repair)
        if decision is None:
            decision = outcome.result.decision
        if decision is None:
            raise Phase32ContractRepairConflict(
                "Contract repair did not restore an explicit candidate decision"
            )
        decision_id = str(decision.get("decision_id") or "")
        completed = self.repairs.succeed(
            run_id=repair.run_id,
            repair_id=repair.repair_id,
            decision_id=decision_id,
            result={
                "status": outcome.record.state.status,
                "active_stage_id": outcome.record.state.active_stage_id,
                "decision_id": decision_id,
            },
        )
        return Phase32ContractRepairOutcome(
            repair=completed,
            run=outcome.record,
            decision=decision,
            reused=outcome.reused,
        )

    @staticmethod
    def _pending_decision(
        record: Phase32RunRecord,
        repair: Phase32ContractRepairRecord,
    ) -> dict[str, Any] | None:
        pending = next(
            (
                item
                for item in record.read_model.pending_decisions
                if item.artifact_ref == repair.candidate_ref
                and item.stage_id == repair.stage_id
            ),
            None,
        )
        return pending.model_dump(mode="json") if pending is not None else None


__all__ = [
    "Phase32ContractFinding",
    "Phase32ContractQuarantine",
    "Phase32ContractRepairCommand",
    "Phase32ContractRepairConflict",
    "Phase32ContractRepairError",
    "Phase32ContractRepairNotEligible",
    "Phase32ContractRepairOutcome",
    "Phase32ContractRepairService",
]
