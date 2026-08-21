from __future__ import annotations

from typing import Any

from novel_workflow.memory.canon_store import CanonFact
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState


def enqueue_domain_commit(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    evidence_refs = list(state.get("pending_evidence_refs") or [])
    if not evidence_refs:
        raise ValueError("Domain commit requires non-empty validated Evidence refs")
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    attempt_ref = str(state.get("pending_evidence_attempt_ref") or "")
    if not attempt_ref:
        raise ValueError("Domain commit requires a succeeded Evidence attempt")
    evidence_attempt = executor.evidence.read_attempt(run_id, attempt_ref)
    if (
        evidence_attempt.status != "succeeded"
        or evidence_attempt.chapter_id != chapter_id
        or evidence_attempt.chapter_version_id != version_id
        or evidence_attempt.evidence_refs != evidence_refs
    ):
        raise ValueError("Domain commit Evidence does not match the accepted chapter")
    facts = [
        CanonFact(
            fact_id=f"fact-{evidence.evidence_id.removeprefix('evidence-')}",
            claim=evidence.claim,
            evidence_refs=[evidence.evidence_id],
            chapter_version_id=version_id,
            subject_id=evidence.subject_id,
            property_key=evidence.property_key,
            value=evidence.value,
            epistemic_status=evidence.epistemic_status,
            lifecycle=evidence.lifecycle,
            effective_from_chapter=evidence.effective_from_chapter,
            effective_to_chapter=evidence.effective_to_chapter,
            supersedes_fact_ids=evidence.supersedes_fact_ids,
            resolves_fact_ids=evidence.resolves_fact_ids,
        )
        for evidence in (
            executor.evidence.read(run_id, evidence_id)
            for evidence_id in evidence_refs
        )
    ]
    operation_id = f"outbox-{chapter_id}-{version_id}"
    transaction_id = f"canon-{chapter_id}-{version_id}"
    executor.outbox.enqueue(run_id, operation_id, transaction_id, facts)
    executor.events.append(
        run_id,
        event_id=f"{operation_id}:queued",
        type="writeback.queued",
        stage_id="text",
        node_id="text.enqueue_domain_commit",
        chapter_id=chapter_id,
        status="queued",
        payload={
            "evidence_count": len(evidence_refs),
            "transaction_id": transaction_id,
        },
        payload_ref=operation_id,
    )
    return {"pending_writeback_ref": operation_id}


def await_commit_receipt(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    operation_id = str(state.get("pending_writeback_ref") or "")
    if not operation_id:
        raise ValueError("Domain commit receipt requires a queued Outbox operation")
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    operation = executor.outbox.flush(run_id, operation_id)
    executor.events.append(
        run_id,
        event_id=f"{operation_id}:committed",
        type="writeback.committed",
        stage_id="text",
        node_id="text.await_commit_receipt",
        chapter_id=chapter_id,
        status="committed",
        payload={"transaction_id": operation.transaction_id},
        payload_ref=operation_id,
    )
    return {
        "pending_evidence_refs": [],
        "pending_writeback_ref": "",
        "pending_evidence_attempt_ref": "",
        "evidence_gate_action": "",
    }


__all__ = ["await_commit_receipt", "enqueue_domain_commit"]
