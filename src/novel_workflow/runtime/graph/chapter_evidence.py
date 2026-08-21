from __future__ import annotations

import hashlib
from typing import Any

from langgraph.types import interrupt

from novel_workflow.quality.decision_contract import (
    QualityDecision,
    build_quality_decision,
)
from novel_workflow.runtime.graph.chapter_evidence_contract import (
    evidence_request_context,
    EvidenceStateBinding,
    provider_receipt_key,
    visible_evidence_error,
)
from novel_workflow.runtime.graph.chapter_evidence_operation import (
    execute_evidence_request,
)
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ProviderOperationError,
)
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.evidence_store import (
    EvidenceAttempt,
    EvidenceRecord,
    EvidenceSpan,
)


MAX_AUTOMATIC_EVIDENCE_ATTEMPTS = 2


async def extract_evidence(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    chapter = executor.chapters.read(run_id, chapter_id, version_id).artifact
    if chapter.author_status != "accepted":
        raise ValueError("Evidence extraction requires an accepted chapter version")
    operation_key = f"{run_id}:{chapter_id}:evidence:{version_id}"
    content_hash = hashlib.sha256(chapter.content.encode("utf-8")).hexdigest()
    evidence_attempt = executor.evidence.begin_attempt(
        operation_key=operation_key,
        run_id=run_id,
        chapter_id=chapter_id,
        chapter_version_id=version_id,
        chapter_content_hash=content_hash,
    )
    if evidence_attempt.status == "succeeded":
        return _succeeded_attempt_update(executor, evidence_attempt)
    if evidence_attempt.status == "needs_action":
        quality_decision = _evidence_quality_decision(
            executor,
            evidence_attempt,
            evidence_status="needs_action",
        )
        _emit_quality_decision(executor, evidence_attempt, quality_decision)
        return _needs_action_update(evidence_attempt)

    binding = executor.runs.definition(run_id).provider_bindings.get("text")
    if binding is None:
        raise ProviderOperationError("No frozen Provider binding for evidence extraction")
    budget = executor.output_budget_planner(state).for_evidence(binding)
    frozen_context = executor.context_compiler().evidence(state)

    while evidence_attempt.attempt <= MAX_AUTOMATIC_EVIDENCE_ATTEMPTS:
        attempt_number = (
            2 if evidence_attempt.status == "retryable" else evidence_attempt.attempt
        )
        previous_error = evidence_attempt.contract_error
        receipt_key = provider_receipt_key(
            operation_key,
            recovery_count=evidence_attempt.recovery_count,
            attempt=attempt_number,
        )
        if attempt_number == 2:
            evidence_attempt = executor.evidence.update_attempt(
                run_id,
                operation_key,
                status="pending",
                attempt=2,
                contract_error=previous_error,
                provider_receipt_ref=receipt_key,
            )
        request = ChapterEvidenceRequest(
            operation_key=receipt_key,
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_version_id=version_id,
            attempt=attempt_number,
            content=chapter.content,
            binding=budget.bind(binding),
            context=evidence_request_context(
                frozen_context,
                operation_key=operation_key,
                content_hash=content_hash,
                recovery_count=evidence_attempt.recovery_count,
                attempt=attempt_number,
                contract_error=previous_error,
            ),
        )
        result, bound_spans, state_bindings, failure = await execute_evidence_request(
            executor,
            request,
        )
        if failure is None:
            assert (
                result is not None
                and bound_spans is not None
                and state_bindings is not None
            )
            records = _write_evidence_records(
                executor,
                state,
                result=result,
                bound_spans=bound_spans,
                state_bindings=state_bindings,
                version_id=version_id,
            )
            evidence_refs = [record.evidence_id for record in records]
            evidence_attempt = executor.evidence.update_attempt(
                run_id,
                operation_key,
                status="succeeded",
                attempt=attempt_number,
                evidence_refs=evidence_refs,
                provider_receipt_ref=receipt_key,
            )
            for record in records:
                _emit_evidence_proposed(executor, record)
            return _succeeded_attempt_update(executor, evidence_attempt)

        visible_error = visible_evidence_error(failure)
        if attempt_number == 1 and failure.contract_error:
            evidence_attempt = executor.evidence.update_attempt(
                run_id,
                operation_key,
                status="retryable",
                attempt=1,
                contract_error=visible_error,
                provider_receipt_ref=receipt_key,
            )
            continue

        evidence_attempt = executor.evidence.update_attempt(
            run_id,
            operation_key,
            status="needs_action",
            attempt=attempt_number,
            contract_error=visible_error,
            provider_receipt_ref=receipt_key,
        )
        quality_decision = _evidence_quality_decision(
            executor,
            evidence_attempt,
            evidence_status="needs_action",
        )
        _emit_quality_decision(executor, evidence_attempt, quality_decision)
        _emit_evidence_recovery_required(
            executor,
            evidence_attempt,
            quality_decision,
        )
        return _needs_action_update(evidence_attempt)

    raise RuntimeError("Evidence attempt exceeded its bounded correction policy")


def request_evidence_recovery(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    run_id = state["run_id"]
    operation_key = str(state.get("pending_evidence_attempt_ref") or "")
    if not operation_key:
        raise ValueError("Evidence recovery requires a persisted attempt reference")
    attempt = executor.evidence.read_attempt(run_id, operation_key)
    if attempt.status != "needs_action":
        raise ValueError("Evidence recovery requires a needs_action attempt")
    decision_id = f"{operation_key}:recovery-{attempt.recovery_count + 1}"
    payload = _evidence_recovery_payload(
        state,
        attempt=attempt,
        decision_id=decision_id,
        quality_decision=_evidence_quality_decision(
            executor,
            attempt,
            evidence_status="needs_action",
        ),
    )
    executor.events.append(
        run_id,
        event_id=f"{decision_id}:required",
        type="decision.required",
        stage_id="text",
        node_id="text.evidence_recovery",
        chapter_id=attempt.chapter_id,
        status="awaiting_decision",
        payload=payload,
        payload_ref=operation_key,
    )
    value = interrupt(payload)
    action = _validate_evidence_recovery_decision(
        value,
        decision_id=decision_id,
        domain_revision=int(state.get("domain_revision") or 0),
    )
    executor.events.append(
        run_id,
        event_id=f"{decision_id}:{action}:resolved",
        type="decision.resolved",
        stage_id="text",
        node_id="text.evidence_recovery",
        chapter_id=attempt.chapter_id,
        status=action,
        payload={"decision_id": decision_id, "action": action},
        payload_ref=operation_key,
    )
    if action == "cancel":
        return {"evidence_gate_action": "cancel", "status": "cancelled"}
    executor.evidence.begin_recovery(
        run_id,
        operation_key,
        decision_id=decision_id,
    )
    return {"evidence_gate_action": "retry", "status": "running"}


def _evidence_recovery_payload(
    state: NarrativeRunState,
    *,
    attempt: EvidenceAttempt,
    decision_id: str,
    quality_decision: QualityDecision,
) -> dict[str, Any]:
    return {
        "type": "evidence_recovery_decision",
        "decision_id": decision_id,
        "thread_id": attempt.run_id,
        "node_id": "text.evidence_recovery",
        "chapter_id": attempt.chapter_id,
        "chapter_version_id": attempt.chapter_version_id,
        "evidence_operation_key": attempt.operation_key,
        "domain_revision": int(state.get("domain_revision") or 0),
        "allowed_actions": quality_decision.allowed_actions(),
        "regeneration_limit": quality_decision.regeneration_limit,
        "regeneration_used": quality_decision.regeneration_used,
        "quality_decision": quality_decision.model_dump(mode="json"),
        "evidence_detail": {
            "status": attempt.status,
            "attempt": attempt.attempt,
            "contract_error": attempt.contract_error,
            "chapter_content_hash": attempt.chapter_content_hash,
        },
    }



def _write_evidence_records(
    executor: StageExecutor,
    state: NarrativeRunState,
    *,
    result: ChapterEvidenceResult,
    bound_spans: list[list[EvidenceSpan]],
    state_bindings: list[EvidenceStateBinding],
    version_id: str,
) -> list[EvidenceRecord]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    return [
        executor.evidence.write(
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_version_id=version_id,
            kind=claim.kind,
            claim=claim.claim,
            spans=spans,
            subject_id=binding.subject_id,
            property_key=binding.property_key,
            value=binding.value,
            epistemic_status=binding.epistemic_status,
            lifecycle=binding.lifecycle,
            effective_from_chapter=int(state["active_chapter_number"]),
            supersedes_fact_ids=list(binding.supersedes_fact_ids),
            resolves_fact_ids=list(binding.resolves_fact_ids),
        )
        for claim, spans, binding in zip(
            result.claims,
            bound_spans,
            state_bindings,
            strict=True,
        )
    ]


def _succeeded_attempt_update(
    executor: StageExecutor,
    attempt: EvidenceAttempt,
) -> dict[str, Any]:
    if not attempt.evidence_refs:
        raise ValueError("Succeeded Evidence attempt cannot contain empty refs")
    for evidence_ref in attempt.evidence_refs:
        record = executor.evidence.read(attempt.run_id, evidence_ref)
        if (
            record.chapter_id != attempt.chapter_id
            or record.chapter_version_id != attempt.chapter_version_id
        ):
            raise ValueError("Evidence ref does not match its accepted chapter")
    quality_decision = _evidence_quality_decision(
        executor,
        attempt,
        evidence_status="succeeded",
    )
    _emit_quality_decision(executor, attempt, quality_decision)
    return {
        "pending_evidence_attempt_ref": attempt.operation_key,
        "pending_evidence_refs": list(attempt.evidence_refs),
        "pending_writeback_ref": "",
        "evidence_gate_action": "succeeded",
    }


def _needs_action_update(attempt: EvidenceAttempt) -> dict[str, Any]:
    return {
        "pending_evidence_attempt_ref": attempt.operation_key,
        "pending_evidence_refs": [],
        "pending_writeback_ref": "",
        "evidence_gate_action": "needs_action",
    }


def _emit_evidence_recovery_required(
    executor: StageExecutor,
    attempt: EvidenceAttempt,
    quality_decision: QualityDecision,
) -> None:
    executor.events.append(
        attempt.run_id,
        event_id=(
            f"{attempt.operation_key}:recovery-required-{attempt.recovery_count}"
        ),
        type="evidence.recovery_required",
        stage_id="text",
        node_id="text.extract_evidence",
        chapter_id=attempt.chapter_id,
        status="needs_action",
        payload={
            "chapter_version_id": attempt.chapter_version_id,
            "attempt": attempt.attempt,
            "contract_error": attempt.contract_error,
            "recovery_count": attempt.recovery_count,
            "quality_decision": quality_decision.model_dump(mode="json"),
        },
        payload_ref=attempt.operation_key,
    )


def _evidence_quality_decision(
    executor: StageExecutor,
    attempt: EvidenceAttempt,
    *,
    evidence_status: str,
) -> QualityDecision:
    latest: QualityDecision | None = None
    for event in reversed(executor.events.read(attempt.run_id)):
        if event.chapter_id != attempt.chapter_id or not isinstance(event.payload, dict):
            continue
        candidate = event.payload.get("quality_decision")
        if not isinstance(candidate, dict):
            continue
        latest = QualityDecision.model_validate(candidate)
        break
    if latest is None:
        latest = build_quality_decision(
            regeneration_used=0,
            accepted=True,
        )
    return QualityDecision.model_validate(
        {
            **latest.model_dump(mode="json"),
            "accepted": True,
            "evidence_status": evidence_status,
            "evidence_degraded": evidence_status == "needs_action",
        }
    )


def _emit_quality_decision(
    executor: StageExecutor,
    attempt: EvidenceAttempt,
    decision: QualityDecision,
) -> None:
    executor.events.append(
        attempt.run_id,
        event_id=(
            f"{attempt.operation_key}:quality:{decision.evidence_status}:"
            f"{attempt.recovery_count}"
        ),
        type="quality.decision_projected",
        stage_id="text",
        node_id="text.extract_evidence",
        chapter_id=attempt.chapter_id,
        status=decision.evidence_status,
        payload={"quality_decision": decision.model_dump(mode="json")},
        payload_ref=attempt.operation_key,
    )


def _emit_evidence_proposed(
    executor: StageExecutor,
    record: EvidenceRecord,
) -> None:
    executor.events.append(
        record.run_id,
        event_id=f"{record.evidence_id}:proposed",
        type="evidence.proposed",
        stage_id="text",
        node_id="text.extract_evidence",
        chapter_id=record.chapter_id,
        status="proposed",
        payload={
            "kind": record.kind,
            "claim": record.claim,
            "span_count": len(record.spans),
        },
        payload_ref=record.evidence_id,
    )


def _validate_evidence_recovery_decision(
    value: Any,
    *,
    decision_id: str,
    domain_revision: int,
) -> str:
    if not isinstance(value, dict):
        raise ValueError("Evidence recovery decision must be an object")
    if value.get("decision_id") != decision_id:
        raise ValueError("Evidence recovery decision id does not match")
    if int(value.get("domain_revision", -1)) != domain_revision:
        raise ValueError("Evidence recovery decision domain revision is stale")
    action = str(value.get("action") or "")
    if action not in {"retry_evidence", "cancel"}:
        raise ValueError("Evidence recovery action is not allowed")
    return action


__all__ = [
    "extract_evidence",
    "request_evidence_recovery",
]
