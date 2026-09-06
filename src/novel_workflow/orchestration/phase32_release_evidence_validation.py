"""Fail-closed closure rules for private exact-12 release evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    continuity_acceptance_provider_readiness_policy,
    current_phase32_provider_readiness_verdict,
)
from novel_workflow.output_contracts.phase32_release_evidence import (
    Phase32ContinuityEvidenceSummary,
)
from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceipt,
)
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessStore,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.workflow_ids import OFFICIAL_LONG_NOVEL_WORKFLOW_ID


_TERMINAL_EVENT_TYPES = frozenset({"image.deferred", "export.ready"})

def build_release_summary(
    *,
    definition: GraphRunDefinition,
    record: Any,
    generated_at: str,
    readiness_store: Phase32ProviderReadinessStore,
    authorization: Any,
    admissions: tuple[Any, ...],
    receipts: tuple[Phase32ProviderOperationReceipt, ...],
    provider_inputs: Phase32ProviderInputStore,
    events: tuple[Any, ...],
    artifacts: tuple[Any, ...],
    evidence: tuple[Any, ...],
    writebacks: tuple[Any, ...],
    canon: tuple[Any, ...],
    wiki: tuple[Any, ...],
    quality_reports: tuple[Any, ...],
) -> Phase32ContinuityEvidenceSummary:
    issues: list[str] = []
    profile_kind = str(definition.scale_profile.payload.get("profile_kind") or "")
    if (
        definition.workflow_id != OFFICIAL_LONG_NOVEL_WORKFLOW_ID
        or definition.creation_route_id != "long_novel"
        or profile_kind != "continuity_acceptance"
    ):
        issues.append("continuity_definition_invalid")
    bindings = {
        frozen.stage_id: (
            frozen.binding.payload_digest,
            Phase32StageProviderBindingSnapshot.model_validate(
                frozen.binding.payload
            ),
        )
        for frozen in definition.provider_bindings_by_stage
    }
    try:
        readiness_verdict = current_phase32_provider_readiness_verdict(
            definition,
            store=readiness_store,
            policy=continuity_acceptance_provider_readiness_policy(),
            now=datetime.fromisoformat(generated_at),
        )
    except Exception:
        issues.append("readiness_unreadable")
    else:
        if not readiness_verdict.ready:
            issues.extend(readiness_verdict.issue_codes or ("readiness_not_ready",))

    if authorization is None:
        issues.append("budget_authorization_missing")
    elif authorization.definition_digest != definition.definition_digest:
        issues.append("budget_definition_mismatch")

    progress = record.state.sequential_progress("text")
    committed_refs: tuple[str, ...] = ()
    ordered_refs: tuple[str, ...] = ()
    if progress is None:
        issues.append("text_progress_missing")
    else:
        ordered_refs = tuple(progress.ordered_unit_refs)
        committed_refs = tuple(progress.committed_artifact_refs.values())
        if len(ordered_refs) != 12:
            issues.append("exact12_unit_manifest_mismatch")
        if not progress.complete or len(committed_refs) != 12:
            issues.append("exact12_accepted_prefix_incomplete")
    if record.read_model.pending_decisions:
        issues.append("pending_decision_present")

    artifacts_by_ref = {item.artifact_ref: item for item in artifacts}
    for artifact_ref in committed_refs:
        artifact = artifacts_by_ref.get(artifact_ref)
        if artifact is None:
            issues.append("accepted_artifact_missing")
            continue
        if artifact.status != "committed" or artifact.stage_id != "text":
            issues.append("accepted_artifact_invalid")

    writeback_receipts = tuple(item.receipt for item in writebacks)
    committed_writebacks = tuple(
        item for item in writeback_receipts if item.status == "committed"
    )
    pending_writebacks = tuple(
        item
        for item in writeback_receipts
        if item.status not in {"committed", "cancelled"}
    )
    source_counts = Counter(item.source_artifact_ref for item in committed_writebacks)
    if any(source_counts.get(ref, 0) != 1 for ref in committed_refs):
        issues.append("exact12_writeback_incomplete")
    if any(ref not in committed_refs for ref in source_counts):
        issues.append("writeback_source_outside_accepted_prefix")
    if pending_writebacks:
        issues.append("writeback_pending")
    if any(item.status == "cancelled" for item in writeback_receipts):
        issues.append("writeback_cancelled")

    evidence_by_ref = {item.evidence_ref: item for item in evidence}
    canon_by_ref = {item.transaction_ref: item for item in canon}
    wiki_by_ref = {item.transaction_ref: item for item in wiki}
    receipts_by_ref = {item.receipt_ref: item for item in receipts}
    for receipt in committed_writebacks:
        artifact = artifacts_by_ref.get(receipt.source_artifact_ref)
        if (
            artifact is None
            or receipt.source_payload_digest != artifact.payload_digest
            or receipt.unit_ref not in ordered_refs
        ):
            issues.append("writeback_source_identity_mismatch")
        transaction = canon_by_ref.get(receipt.transaction_ref)
        projection = wiki_by_ref.get(receipt.transaction_ref)
        if transaction is None:
            issues.append("canon_transaction_missing")
        elif (
            transaction.source_artifact_ref != receipt.source_artifact_ref
            or tuple(item.fact_ref for item in transaction.facts) != receipt.fact_refs
        ):
            issues.append("canon_transaction_identity_mismatch")
        if projection is None:
            issues.append("wiki_projection_missing")
        elif (
            projection.source_artifact_ref != receipt.source_artifact_ref
            or transaction is None
            or projection.facts != transaction.facts
        ):
            issues.append("wiki_projection_identity_mismatch")
        receipt_evidence = tuple(
            evidence_by_ref.get(ref) for ref in receipt.evidence_refs
        )
        if any(item is None for item in receipt_evidence):
            issues.append("writeback_evidence_missing")
        elif any(
            item.source_artifact_ref != receipt.source_artifact_ref
            or item.source_payload_digest != receipt.source_payload_digest
            or item.source_text_digest != receipt.source_text_digest
            or item.unit_ref != receipt.unit_ref
            for item in receipt_evidence
        ):
            issues.append("writeback_evidence_identity_mismatch")
        if any(ref not in receipts_by_ref for ref in receipt.provider_operation_refs):
            issues.append("writeback_provider_operation_missing")

    image_count = 0
    collaboration_count = 0
    input_unreadable = False
    provider_identity_mismatch = False
    provider_input_missing = False
    for receipt in receipts:
        if ":image:" in receipt.operation_key:
            image_count += 1
        if ":collaboration:" in receipt.operation_key:
            collaboration_count += 1
        expected_binding = bindings.get(receipt.stage_id)
        if expected_binding is None:
            provider_identity_mismatch = True
        else:
            _, binding = expected_binding
            execution = binding.execution
            if (
                receipt.provider_profile_id != execution.provider_profile_id
                or receipt.provider_template_id != execution.provider_template_id
                or receipt.model_id != execution.model_id
                or receipt.pricing_snapshot_ref != execution.pricing_snapshot.snapshot_ref
            ):
                provider_identity_mismatch = True
        if not receipt.provider_input_ref:
            provider_input_missing = True
            continue
        try:
            request = provider_inputs.read(
                definition.run_id,
                receipt.provider_input_ref,
            ).request
        except Exception:
            input_unreadable = True
            continue
        if expected_binding is not None:
            binding_digest, binding = expected_binding
            execution = binding.execution
            if (
                request.get("creation_route_id") != definition.creation_route_id
                or request.get("route_revision") != definition.route_revision
                or request.get("provider_binding_digest") != binding_digest
                or request.get("provider_profile_id") != execution.provider_profile_id
                or request.get("provider_template_id") != execution.provider_template_id
                or request.get("model_id") != execution.model_id
            ):
                provider_identity_mismatch = True
        if receipt.stage_id == "cover" and "prompt" in request and "rendered_prompt" not in request:
            image_count += int(":image:" not in receipt.operation_key)
        if "thread_id" in request or "turn_id" in request:
            collaboration_count += int(":collaboration:" not in receipt.operation_key)
    if input_unreadable:
        issues.append("provider_input_unreadable")
    if provider_input_missing:
        issues.append("provider_input_missing")
    if provider_identity_mismatch:
        issues.append("provider_execution_identity_mismatch")
    if image_count:
        issues.append("image_provider_operation_present")
    if collaboration_count:
        issues.append("collaboration_provider_operation_present")

    pending_receipts = tuple(item for item in receipts if item.status == "pending")
    if pending_receipts:
        issues.append("provider_operation_pending")
    rejected_receipts = tuple(
        item for item in receipts if item.status == "contract_rejected"
    )
    unrecovered_rejections = _unrecovered_contract_rejection_refs(
        rejected_receipts=rejected_receipts,
        receipts=receipts,
        events=events,
        writebacks=writeback_receipts,
    )
    if (
        any(
            item.status not in {"succeeded", "contract_rejected"}
            for item in receipts
        )
        or unrecovered_rejections
    ):
        issues.append("provider_operation_not_succeeded")

    admission_by_ref = {item.admission_ref: item for item in admissions}
    claimed_admission_refs: list[str] = []
    attempt_evidence_complete = True
    for receipt in receipts:
        claimed_admission_refs.extend(receipt.transport_admission_refs)
        claims = [
            event
            for event in receipt.transport_attempt_events
            if event.event_kind == "claimed"
        ]
        terminals = [
            event
            for event in receipt.transport_attempt_events
            if event.event_kind != "claimed"
        ]
        if (
            len(claims) != receipt.transport_attempts
            or len(terminals) != receipt.transport_attempts
            or tuple(event.transport_attempt for event in claims)
            != tuple(range(1, receipt.transport_attempts + 1))
        ):
            attempt_evidence_complete = False
        if tuple(event.admission_ref for event in claims) != receipt.transport_admission_refs:
            attempt_evidence_complete = False
        if receipt.transport_attempts <= 0:
            attempt_evidence_complete = False
        if authorization is None or (
            receipt.budget_definition_digest != definition.definition_digest
            or receipt.budget_authorization_ref != authorization.authorization_ref
        ):
            issues.append("receipt_budget_identity_mismatch")
        for transport_attempt, admission_ref in enumerate(
            receipt.transport_admission_refs,
            start=1,
        ):
            admission = admission_by_ref.get(admission_ref)
            if admission is None:
                continue
            if (
                admission.run_id != definition.run_id
                or admission.definition_digest != definition.definition_digest
                or authorization is None
                or admission.authorization_ref != authorization.authorization_ref
                or admission.operation_key != receipt.operation_key
                or admission.request_signature != receipt.request_signature
                or admission.transport_attempt != transport_attempt
            ):
                issues.append("budget_admission_identity_mismatch")
    if not attempt_evidence_complete:
        issues.append("transport_attempt_evidence_incomplete")
    if any(ref not in admission_by_ref for ref in claimed_admission_refs):
        issues.append("transport_attempt_without_budget_admission")
    if set(admission_by_ref) != set(claimed_admission_refs):
        issues.append("budget_admission_unclaimed")
    if authorization is not None and any(
        item.transport_attempt > authorization.max_transport_attempts
        for item in admissions
    ):
        issues.append("transport_attempt_limit_exceeded")

    total_tokens, estimated_cost = _consumed_budget(receipts, admission_by_ref, issues)
    if authorization is not None:
        if len(receipts) > authorization.max_operations:
            issues.append("operation_limit_exceeded")
        if total_tokens is not None and total_tokens > authorization.max_total_tokens:
            issues.append("token_limit_exceeded")
        if estimated_cost is not None and estimated_cost > authorization.max_cost_usd:
            issues.append("cost_limit_exceeded")

    terminal_events = tuple(event for event in events if event.type in _TERMINAL_EVENT_TYPES)
    if record.state.status != "image_deferred":
        issues.append("terminal_status_invalid")
    if len(terminal_events) != 1 or terminal_events[0].type != "image.deferred":
        issues.append("terminal_event_not_singleton")

    if not quality_reports:
        issues.append("continuity_quality_report_missing")
    else:
        latest = quality_reports[-1]
        source_refs = tuple(
            item.artifact_ref for item in latest.source_snapshot.committed_sources
        )
        if (
            latest.evidence_scope != "continuity_acceptance"
            or latest.source_snapshot.definition_digest != definition.definition_digest
            or not latest.source_snapshot.accepted_prefix_complete
            or source_refs != committed_refs
            or latest.deterministic_blockers
            or latest.cold_read.outcome != "continue_reading"
        ):
            issues.append("continuity_quality_report_invalid")

    issue_codes = tuple(dict.fromkeys(issues))
    return Phase32ContinuityEvidenceSummary(
        verdict="blocked" if issue_codes else "ready",
        issue_codes=issue_codes,
        terminal_status=record.state.status,
        terminal_event_count=len(terminal_events),
        committed_chapter_count=len(committed_refs),
        committed_writeback_count=len(committed_writebacks),
        pending_writeback_count=len(pending_writebacks),
        provider_operation_count=len(receipts),
        pending_provider_operation_count=len(pending_receipts),
        transport_attempt_count=sum(item.transport_attempts for item in receipts),
        budget_admission_count=len(admissions),
        image_provider_operation_count=image_count,
        collaboration_provider_operation_count=collaboration_count,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        quality_report_count=len(quality_reports),
    )


def _consumed_budget(
    receipts: tuple[Phase32ProviderOperationReceipt, ...],
    admissions: dict[str, Any],
    issues: list[str],
) -> tuple[int | None, float | None]:
    total_tokens = 0
    cost = 0.0
    known = True
    for receipt in receipts:
        claimed = [admissions.get(ref) for ref in receipt.transport_admission_refs]
        if any(item is None for item in claimed):
            known = False
            continue
        for failed in claimed[:-1]:
            total_tokens += failed.reserved_total_tokens
            cost += failed.reserved_cost_usd
        if receipt.status in {"returned", "succeeded", "contract_rejected"} and claimed:
            prompt_tokens = receipt.usage.get("prompt_tokens")
            completion_tokens = receipt.usage.get("completion_tokens")
            receipt_total = receipt.usage.get("total_tokens")
            if (
                prompt_tokens is None
                or completion_tokens is None
                or receipt_total is None
                or receipt_total < prompt_tokens + completion_tokens
            ):
                issues.append("receipt_token_usage_incomplete")
                known = False
            else:
                total_tokens += receipt_total
            if receipt.cost_status != "known" or receipt.estimated_cost_usd is None:
                issues.append("receipt_cost_unknown")
                known = False
            else:
                cost += receipt.estimated_cost_usd
        elif claimed:
            total_tokens += claimed[-1].reserved_total_tokens
            cost += claimed[-1].reserved_cost_usd
        elif receipt.transport_attempts:
            known = False
    return (
        total_tokens if known else None,
        round(cost, 12) if known else None,
    )


def _unrecovered_contract_rejection_refs(
    *,
    rejected_receipts: tuple[Phase32ProviderOperationReceipt, ...],
    receipts: tuple[Phase32ProviderOperationReceipt, ...],
    events: tuple[Any, ...],
    writebacks: tuple[Any, ...],
) -> tuple[str, ...]:
    """Return contract rejections without a durable successful continuation.

    A rejected Provider return remains first-class evidence. It is release-safe
    only when the canonical history proves replacement: writeback recovery must
    bind the rejected and successful operations into one committed outbox
    receipt; a stage failure must be projected, followed by a new candidate and
    a committed Artifact for that same stage.
    """

    succeeded_refs = {
        receipt.receipt_ref
        for receipt in receipts
        if receipt.status == "succeeded"
    }
    unresolved: list[str] = []
    for receipt in rejected_receipts:
        if ":writeback:" in receipt.operation_key:
            recovered = any(
                writeback.status == "committed"
                and receipt.receipt_ref in writeback.provider_operation_refs
                and any(
                    provider_ref in succeeded_refs
                    for provider_ref in writeback.provider_operation_refs
                )
                for writeback in writebacks
            )
        else:
            try:
                rejected_at = datetime.fromisoformat(receipt.updated_at)
            except (TypeError, ValueError):
                recovered = False
            else:
                matching_failures = tuple(
                    event
                    for event in events
                    if event.stage_id == receipt.stage_id
                    and event.type in {"stage.failed", "unit.failed"}
                    and (event.payload or {}).get("code")
                    == "provider_contract_failed"
                    and datetime.fromisoformat(event.occurred_at) >= rejected_at
                )
                recovered = any(
                    any(
                        candidate.type == "candidate.created"
                        and candidate.stage_id == receipt.stage_id
                        and candidate.sequence > failure.sequence
                        and any(
                            committed.type == "artifact.committed"
                            and committed.stage_id == receipt.stage_id
                            and committed.sequence > candidate.sequence
                            for committed in events
                        )
                        for candidate in events
                    )
                    for failure in matching_failures
                )
        if not recovered:
            unresolved.append(receipt.receipt_ref)
    return tuple(unresolved)




__all__ = ["build_release_summary"]
