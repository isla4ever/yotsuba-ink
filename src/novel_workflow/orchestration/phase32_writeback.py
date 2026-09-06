"""Accepted Artifact -> Evidence -> Outbox -> Canon/Wiki orchestration."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.output_contracts.phase32_writeback import (
    Phase32EvidenceProposalBundle,
    Phase32WritebackReceipt,
)
from novel_workflow.providers.frozen_contract import prompt_digest, schema_digest
from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
    Phase32TextOperationAdmission,
)
from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
    Phase32WritebackGateway,
    Phase32WritebackProviderRequest,
)
from novel_workflow.references.phase32_writeback_context import (
    accepted_source_text,
    accepted_unit_ref,
    bind_writeback_proposals,
    build_evidence_candidates,
    compile_writeback_context,
    frozen_subject_refs,
    render_writeback_prompt,
)
from novel_workflow.runtime.graph.route_run_state import RouteRunStateSnapshot
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_evidence_store import Phase32EvidenceStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceipt,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.storage.phase32_writeback_outbox import Phase32WritebackOutbox
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_compiler import CompiledRouteStage


@dataclass(frozen=True, slots=True)
class _ProposalResult:
    bundle: Phase32EvidenceProposalBundle
    receipt_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PendingWritebackOperation:
    """A transport-pending writeback call and its exact frozen request."""

    receipt: Phase32ProviderOperationReceipt
    request: Phase32WritebackProviderRequest
    contract_attempt: int


class Phase32WritebackContractError(ValueError):
    """A Provider response could not satisfy the frozen Evidence contract."""

    code = "writeback_contract_invalid"


class Phase32WritebackBindingError(ValueError):
    """A contract-valid proposal could not bind to frozen source state."""

    # Keep the existing public recovery code for semantic binding failures;
    # the message still identifies the lower-level source/state boundary.
    code = "evidence_proposal_failed"


class Phase32WritebackAdmissionError(ValueError):
    code = "phase32_text_operation_admission_required"


class Phase32WritebackService:
    """Own one resumable writeback operation for each accepted writing unit."""

    def __init__(
        self,
        *,
        artifacts: Phase32ArtifactStore,
        evidence: Phase32EvidenceStore,
        canon: Phase32CanonStore,
        outbox: Phase32WritebackOutbox,
        provider_inputs: Phase32ProviderInputStore,
        provider_operations: Phase32ProviderOperationStore,
        gateway: Phase32WritebackGateway,
        text_operation_admission: Phase32TextOperationAdmission | None = None,
        provider_lease_seconds: int = 120,
        provider_max_transport_attempts: int = 3,
    ) -> None:
        self.artifacts = artifacts
        self.evidence = evidence
        self.canon = canon
        self.outbox = outbox
        self.provider_inputs = provider_inputs
        self.provider_operations = provider_operations
        self.gateway = gateway
        self.text_operation_admission = text_operation_admission
        self.provider_lease_seconds = provider_lease_seconds
        self.provider_max_transport_attempts = provider_max_transport_attempts

    async def commit(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        artifact_ref: str,
        unit_ref: str,
        retry: bool = False,
    ) -> Phase32WritebackReceipt:
        if stage.stage_id not in {"script", "text"}:
            raise ValueError("Only Script/Text stages have formal writeback")
        record = self.artifacts.read(definition.run_id, artifact_ref)
        if (
            record.status != "committed"
            or record.creation_route_id != definition.creation_route_id
            or record.stage_id != stage.stage_id
            or accepted_unit_ref(record) != unit_ref
        ):
            raise ValueError("Writeback source must be the accepted current unit")
        content = accepted_source_text(record)
        source_text_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        intent = self.outbox.begin(
            run_id=definition.run_id,
            creation_route_id=definition.creation_route_id,
            stage_id=stage.stage_id,
            unit_ref=unit_ref,
            source_artifact_ref=record.artifact_ref,
            source_payload_digest=record.payload_digest,
            source_text_digest=source_text_digest,
        )
        if intent.receipt.status == "committed":
            return intent.receipt
        if intent.receipt.status == "cancelled":
            return intent.receipt
        recovery_correction = ""
        if intent.receipt.status == "needs_action":
            if not retry:
                return intent.receipt
            recovery_correction = intent.receipt.error_message
            intent = self.outbox.begin_recovery(
                definition.run_id,
                intent.receipt.receipt_ref,
            )
        if intent.receipt.transaction_ref:
            return self.outbox.flush(
                definition.run_id,
                intent.receipt.receipt_ref,
            ).receipt

        effective_ordinal = _effective_ordinal(state, stage.stage_id, unit_ref)
        candidates = build_evidence_candidates(content)
        context = compile_writeback_context(
            definition=definition,
            artifact_store=self.artifacts,
            canon=self.canon,
            record=record,
            content=content,
            candidates=candidates,
            effective_ordinal=effective_ordinal,
        )
        try:
            proposal = await self._proposal(
                definition=definition,
                stage=stage,
                source_artifact_ref=record.artifact_ref,
                unit_ref=unit_ref,
                context=context,
                recovery_count=intent.receipt.recovery_count,
                recovery_correction=recovery_correction,
            )
            try:
                bound = bind_writeback_proposals(
                    definition=definition,
                    record=record,
                    content=content,
                    candidates=candidates,
                    bundle=proposal.bundle,
                    existing_facts=self.canon.facts(definition.run_id),
                    frozen_subject_refs=frozen_subject_refs(definition, self.artifacts),
                    effective_ordinal=effective_ordinal,
                )
            except ValueError as exc:
                raise Phase32WritebackBindingError(str(exc)) from exc
            for evidence in bound.evidence:
                self.evidence.write(evidence)
            intent = self.outbox.attach_evidence(
                run_id=definition.run_id,
                receipt_ref=intent.receipt.receipt_ref,
                evidence_refs=tuple(item.evidence_ref for item in bound.evidence),
                facts=bound.facts,
                provider_operation_refs=proposal.receipt_refs,
            )
        except Exception as exc:
            failed = self.outbox.mark_needs_action(
                run_id=definition.run_id,
                receipt_ref=intent.receipt.receipt_ref,
                error_code=getattr(exc, "code", "evidence_proposal_failed"),
                error_message=str(exc) or type(exc).__name__,
                provider_operation_refs=tuple(
                    receipt.receipt_ref
                    for receipt in self._writeback_provider_receipts(
                        definition.run_id,
                        record.artifact_ref,
                        intent.receipt.recovery_count,
                    )
                ),
            )
            return failed.receipt
        return self.outbox.flush(
            definition.run_id,
            intent.receipt.receipt_ref,
        ).receipt

    def cancel(self, run_id: str, receipt_ref: str) -> Phase32WritebackReceipt:
        return self.outbox.cancel(run_id, receipt_ref).receipt

    def reconcile(self, run_id: str) -> tuple[Phase32WritebackReceipt, ...]:
        """Complete deterministic Outbox work only; never repeat Provider extraction."""

        reconciled: list[Phase32WritebackReceipt] = []
        for intent in self.outbox.pending(run_id):
            if not intent.receipt.transaction_ref:
                continue
            if intent.receipt.status == "needs_action":
                self.outbox.begin_recovery(run_id, intent.receipt.receipt_ref)
            reconciled.append(
                self.outbox.flush(run_id, intent.receipt.receipt_ref).receipt
            )
        return tuple(reconciled)

    def receipts(self, run_id: str) -> tuple[Phase32WritebackReceipt, ...]:
        return tuple(item.receipt for item in self.outbox.list(run_id))

    async def _proposal(
        self,
        *,
        definition: GraphRunDefinition,
        stage: CompiledRouteStage,
        source_artifact_ref: str,
        unit_ref: str,
        context: dict[str, Any],
        recovery_count: int,
        recovery_correction: str = "",
    ) -> _ProposalResult:
        binding_digest, binding = _provider_binding(definition, stage.stage_id)
        output_schema = Phase32EvidenceProposalBundle.model_json_schema()
        receipt_refs: list[str] = []
        previous_error = ""
        contract_errors: list[tuple[dict[str, str], ...]] = []
        pending = self._pending_writeback_operation(
            definition.run_id,
            stage.stage_id,
            unit_ref,
            source_artifact_ref,
        )
        # A transport failure leaves the exact operation pending.  Recovery
        # must replay that operation (and its frozen prompt) before minting a
        # new contract attempt; otherwise the old receipt remains pending and
        # terminal usage/cost accounting becomes indeterminate.
        first_contract_attempt = pending.contract_attempt if pending else 1
        for contract_attempt in range(first_contract_attempt, 3):
            if pending is not None and contract_attempt == pending.contract_attempt:
                request = pending.request
            else:
                operation_key = _writeback_operation_key(
                    definition.run_id,
                    source_artifact_ref,
                    recovery_count,
                    contract_attempt,
                )
                prompt = render_writeback_prompt(
                    context,
                    correction=(
                        recovery_correction
                        if contract_attempt == 1
                        else previous_error
                    ),
                )
                request = Phase32WritebackProviderRequest(
                    operation_key=operation_key,
                    run_id=definition.run_id,
                    creation_route_id=definition.creation_route_id,
                    route_revision=definition.route_revision,
                    stage_id=stage.stage_id,
                    unit_ref=unit_ref,
                    source_artifact_ref=source_artifact_ref,
                    provider_profile_id=binding.execution.provider_profile_id,
                    provider_template_id=binding.execution.provider_template_id,
                    model_id=binding.execution.model_id,
                    provider_binding_digest=binding_digest,
                    rendered_prompt=prompt,
                    rendered_prompt_digest=prompt_digest(prompt),
                    output_schema=output_schema,
                    output_schema_digest=schema_digest(output_schema),
                    context=context,
                )
            receipt = await self._execute_provider_request(
                definition,
                request,
                binding,
            )
            receipt_refs.append(receipt.receipt_ref)
            if receipt.status == "contract_rejected":
                previous_error = str(receipt.diagnostic.get("message") or "合同不匹配")
                continue
            if receipt.status not in {"returned", "succeeded"} or receipt.raw_provider_payload is None:
                raise ValueError("Writeback Provider operation did not succeed")
            try:
                bundle = Phase32EvidenceProposalBundle.model_validate(
                    receipt.raw_provider_payload
                )
            except ValidationError as exc:
                summary = _validation_error_summary(exc)
                contract_errors.append(summary)
                previous_error = _contract_correction(summary)
                if receipt.status == "returned":
                    self.provider_operations.reject_contract(
                        run_id=definition.run_id,
                        operation_key=request.operation_key,
                        request_signature=receipt.request_signature,
                        diagnostic={
                            **receipt.diagnostic,
                            "code": "writeback_contract_invalid",
                            "message": "Evidence proposal does not satisfy phase32-writeback-v1",
                            "validation_errors": [dict(item) for item in summary],
                        },
                    )
                continue
            if receipt.status == "returned":
                self.provider_operations.succeed(
                    run_id=definition.run_id,
                    operation_key=request.operation_key,
                    request_signature=receipt.request_signature,
                    result={"kind": "phase32_writeback_proposal"},
                )
            return _ProposalResult(bundle, tuple(receipt_refs))
        details = _summarize_contract_failures(contract_errors)
        raise Phase32WritebackContractError(
            "Evidence proposal failed the frozen contract after one correction"
            " (phase32-writeback-v1)"
            + (f": {details}" if details else "")
        )

    def _pending_writeback_operation(
        self,
        run_id: str,
        stage_id: str,
        unit_ref: str,
        source_artifact_ref: str,
    ) -> _PendingWritebackOperation | None:
        """Find a pending operation for this source and recover its snapshot.

        Provider input snapshots are mandatory for production Phase32 calls;
        low-level fixtures may omit them, in which case the operation is not
        safe to replay because its exact prompt cannot be reconstructed.
        """

        source_prefix = _writeback_operation_source_prefix(run_id, source_artifact_ref)
        matches: list[_PendingWritebackOperation] = []
        for receipt in self.provider_operations.list(run_id):
            if (
                receipt.status != "pending"
                or receipt.stage_id != stage_id
                or not receipt.operation_key.startswith(source_prefix)
                or not receipt.provider_input_ref
            ):
                continue
            try:
                snapshot = self.provider_inputs.read(run_id, receipt.provider_input_ref)
                request = Phase32WritebackProviderRequest.model_validate(snapshot.request)
            except Exception:
                # A malformed or legacy receipt must not be silently reused
                # with a different prompt.  It remains visible to recovery
                # diagnostics and can be reconciled by the operator.
                continue
            if request.unit_ref != unit_ref or request.source_artifact_ref != source_artifact_ref:
                continue
            attempt_match = re.search(r":contract-(\d+)$", request.operation_key)
            if attempt_match is None:
                continue
            matches.append(
                _PendingWritebackOperation(
                    receipt=receipt,
                    request=request,
                    contract_attempt=int(attempt_match.group(1)),
                )
            )
        if not matches:
            return None
        return max(matches, key=lambda item: (item.receipt.updated_at, item.receipt.operation_key))

    async def _execute_provider_request(
        self,
        definition: GraphRunDefinition,
        request: Phase32WritebackProviderRequest,
        binding: Phase32StageProviderBindingSnapshot,
    ) -> Phase32ProviderOperationReceipt:
        self._require_text_operation_run(definition)
        payload = request.model_dump(mode="json")
        signature = provider_request_signature(payload)
        snapshot = self.provider_inputs.write(
            run_id=request.run_id,
            operation_key=request.operation_key,
            stage_id=request.stage_id,
            request=payload,
        )
        pricing = binding.execution.pricing_snapshot
        receipt = self.provider_operations.begin(
            run_id=request.run_id,
            operation_key=request.operation_key,
            stage_id=request.stage_id,
            request_signature=signature,
            provider_input_ref=snapshot.provider_input_ref,
            provider_profile_id=binding.execution.provider_profile_id,
            provider_template_id=binding.execution.provider_template_id,
            model_id=binding.execution.model_id,
            pricing_snapshot_ref=pricing.snapshot_ref,
        )
        if receipt.status in {"succeeded", "contract_rejected"}:
            return receipt
        if receipt.status == "returned":
            return receipt
        admission_fence = self._admit_text_operation(
            definition=definition,
            request=request,
            binding=binding,
            request_signature=signature,
        )
        lease_owner = f"phase32-writeback:{os.getpid()}:{uuid4().hex}"
        receipt = self.provider_operations.claim_pending(
            run_id=request.run_id,
            operation_key=request.operation_key,
            request_signature=signature,
            lease_owner=lease_owner,
            admission_fence=admission_fence,
            lease_seconds=self.provider_lease_seconds,
            max_transport_attempts=self.provider_max_transport_attempts,
        )
        try:
            response = await self.gateway.generate_writeback(request, binding=binding)
        except Exception as exc:
            self.provider_operations.release_pending(
                run_id=request.run_id,
                operation_key=request.operation_key,
                request_signature=signature,
                lease_owner=lease_owner,
                claimed_transport_attempt=receipt.transport_attempts,
                diagnostic={"code": getattr(exc, "code", "provider_failed")},
            )
            raise
        receipt = self.provider_operations.record_return(
            run_id=request.run_id,
            operation_key=request.operation_key,
            request_signature=signature,
            raw_provider_payload=response.payload,
            usage=response.usage,
            diagnostic=response.diagnostic,
            pricing_snapshot=pricing,
            lease_owner=lease_owner,
            claimed_transport_attempt=receipt.transport_attempts,
        )
        return receipt

    def _require_text_operation_run(self, definition: GraphRunDefinition) -> None:
        if not _requires_text_operation_admission(definition):
            return
        if self.text_operation_admission is None:
            raise Phase32WritebackAdmissionError(
                "Continuity acceptance requires a persisted text-operation admission"
            )
        self.text_operation_admission.require_run(definition)

    def _admit_text_operation(
        self,
        *,
        definition: GraphRunDefinition,
        request: Phase32WritebackProviderRequest,
        binding: Phase32StageProviderBindingSnapshot,
        request_signature: str,
    ) -> Phase32ProviderOperationAdmissionFence | None:
        if not _requires_text_operation_admission(definition):
            return None
        if self.text_operation_admission is None:  # guarded before receipt creation
            raise Phase32WritebackAdmissionError(
                "Continuity acceptance requires a persisted text-operation admission"
            )
        grant = self.text_operation_admission.admit_text_operation(
            definition=definition,
            request=request,
            binding=binding,
            request_signature=request_signature,
            max_transport_attempts=self.provider_max_transport_attempts,
        )
        return Phase32ProviderOperationAdmissionFence.model_validate(
            grant,
            from_attributes=True,
        )

    def _writeback_provider_receipts(
        self,
        run_id: str,
        source_artifact_ref: str,
        recovery_count: int,
    ) -> tuple[Phase32ProviderOperationReceipt, ...]:
        # Include receipts from prior recovery attempts.  A transport failure
        # is intentionally left pending until the same operation is replayed,
        # so filtering by the current recovery counter would hide the receipt
        # that actually needs operator-visible recovery.
        prefix = _writeback_operation_source_prefix(run_id, source_artifact_ref)
        return tuple(
            receipt for receipt in self.provider_operations.list(run_id)
            if receipt.operation_key.startswith(prefix)
        )


def _provider_binding(
    definition: GraphRunDefinition,
    stage_id: str,
) -> tuple[str, Phase32StageProviderBindingSnapshot]:
    for entry in definition.provider_bindings_by_stage:
        if entry.stage_id == stage_id:
            return (
                entry.binding.payload_digest,
                Phase32StageProviderBindingSnapshot.model_validate(entry.binding.payload),
            )
    raise ValueError(f"No frozen Provider binding for writeback stage {stage_id}")


def _requires_text_operation_admission(definition: GraphRunDefinition) -> bool:
    return definition.scale_profile.payload.get("profile_kind") == "continuity_acceptance"


def _effective_ordinal(
    state: RouteRunStateSnapshot,
    stage_id: str,
    unit_ref: str,
) -> int:
    progress = state.sequential_progress(stage_id)
    if progress is None or unit_ref not in progress.ordered_unit_refs:
        raise ValueError("Writeback unit is outside the frozen sequential stage")
    if unit_ref != progress.next_unit_ref:
        raise ValueError("Writeback may only commit the next accepted unit")
    return progress.ordered_unit_refs.index(unit_ref) + 1


def _writeback_operation_prefix(
    run_id: str,
    source_artifact_ref: str,
    recovery_count: int,
) -> str:
    source_digest = hashlib.sha256(source_artifact_ref.encode("utf-8")).hexdigest()[:24]
    return f"{run_id}:writeback:{source_digest}:recovery-{recovery_count}:"


def _writeback_operation_source_prefix(run_id: str, source_artifact_ref: str) -> str:
    source_digest = hashlib.sha256(source_artifact_ref.encode("utf-8")).hexdigest()[:24]
    return f"{run_id}:writeback:{source_digest}:"


def _writeback_operation_key(
    run_id: str,
    source_artifact_ref: str,
    recovery_count: int,
    contract_attempt: int,
) -> str:
    return _writeback_operation_prefix(
        run_id,
        source_artifact_ref,
        recovery_count,
    ) + f"contract-{contract_attempt}"


def _validation_error_summary(exc: ValidationError) -> tuple[dict[str, str], ...]:
    """Persist only locations and error kinds, never Provider values or prose."""

    summary: list[dict[str, str]] = []
    for error in exc.errors()[:12]:
        location = ".".join(str(part) for part in error.get("loc", ()))
        error_type = str(error.get("type") or "validation_error")[:80]
        message = str(error.get("msg") or "合同校验失败")[:180]
        summary.append(
            {
                "location": location[:180],
                "type": error_type,
                "message": message,
            }
        )
    return tuple(summary)


def _contract_correction(summary: tuple[dict[str, str], ...]) -> str:
    """Give the model a bounded repair instruction without echoing raw input."""

    locations = {item["location"] for item in summary}
    rules = [
        "完整返回一个对象 {\"claims\": [...]}，claims 最多 8 条；",
        "每条 claim 的 span_ids 只能有 1-3 个给定 ID；",
        "state 必须是对象，只能使用 type=story、assertion 或 transition；",
        "不要使用 state=confirmed，也不要添加合同外字段。",
    ]
    if any("span_ids" in location for location in locations):
        rules.insert(
            1,
            "只修改超限 claim 的 span_ids：删除多余 span，只保留最小的 1-3 个连续证据片段；"
            "保留其他合同正确的 claim，不要因为一条 claim 超限而清空整个 claims；",
        )
    if any("state" in location for location in locations):
        rules.insert(
            2,
            "没有明确人物属性时使用 {\"type\":\"story\",\"epistemic_status\":\"fact\"}；"
            "transition 只能使用 {\"type\":\"transition\",\"source_fact_ref\":\"真实 existing_facts.fact_ref\","
            "\"action\":\"supersedes 或 resolves\",\"value\":\"新的状态\",\"epistemic_status\":\"fact\"}，"
            "不得添加 subject_ref、property_key、fact_ref 或 transition 字段；",
        )
    return "上一次输出只在合同层失败。" + "".join(rules)


def _summarize_contract_failures(
    failures: list[tuple[dict[str, str], ...]],
) -> str:
    locations = sorted(
        {
            item["location"]
            for failure in failures
            for item in failure
            if item.get("location")
        }
    )
    return "、".join(locations[:8])


__all__ = [
    "Phase32WritebackBindingError",
    "Phase32WritebackContractError",
    "Phase32WritebackService",
]
