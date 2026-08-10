from __future__ import annotations

import hashlib
import json
from typing import Any

from novel_workflow.memory.canon_store import CanonFact
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ProviderOperationError,
)
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.evidence_store import EvidenceRecord, EvidenceSpan


async def extract_evidence(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    chapter = executor.chapters.read(run_id, chapter_id, version_id).artifact
    operation_key = f"{run_id}:{chapter_id}:evidence:{version_id}"
    binding = executor.runs.definition(run_id).provider_bindings.get("text")
    if binding is None:
        raise ProviderOperationError("No frozen Provider binding for evidence extraction")
    request = ChapterEvidenceRequest(
        operation_key=operation_key,
        run_id=run_id,
        chapter_id=chapter_id,
        chapter_version_id=version_id,
        content=chapter.content,
        binding=binding,
    )
    receipt = executor.operations.begin(
        run_id=run_id,
        operation_key=operation_key,
        kind="chapter_evidence",
        request_signature=_signature(request.model_dump(mode="json")),
        provider_profile_id=binding.provider_profile_id,
        model=binding.model,
    )
    if receipt.status == "succeeded":
        result = ChapterEvidenceResult.model_validate(receipt.result)
    elif receipt.status == "failed":
        return {"pending_evidence_refs": [], "pending_writeback_ref": ""}
    else:
        try:
            result = await executor.provider.extract_chapter_evidence(request)
            _validate_evidence_spans(chapter.content, result)
        except Exception as exc:
            executor.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
            )
            return {"pending_evidence_refs": [], "pending_writeback_ref": ""}
        executor.operations.succeed(
            run_id,
            operation_key,
            result.model_dump(mode="json"),
        )
    _validate_evidence_spans(chapter.content, result)
    records = [
        executor.evidence.write(
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_version_id=version_id,
            kind=claim.kind,
            claim=claim.claim,
            spans=[
                EvidenceSpan.model_validate(span.model_dump(mode="json"))
                for span in claim.spans
            ],
        )
        for claim in result.claims
    ]
    for record in records:
        _emit_evidence_proposed(executor, record)
    return {
        "pending_evidence_refs": [record.evidence_id for record in records],
        "pending_writeback_ref": "",
    }


def enqueue_domain_commit(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    evidence_refs = list(state.get("pending_evidence_refs") or [])
    if not evidence_refs:
        return {"pending_writeback_ref": ""}
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    facts = [
        CanonFact(
            fact_id=f"fact-{evidence.evidence_id.removeprefix('evidence-')}",
            claim=evidence.claim,
            evidence_refs=[evidence.evidence_id],
            chapter_version_id=version_id,
        )
        for evidence in (
            executor.evidence.read(run_id, evidence_id) for evidence_id in evidence_refs
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
        payload={"evidence_count": len(evidence_refs), "transaction_id": transaction_id},
        payload_ref=operation_id,
    )
    return {"pending_writeback_ref": operation_id}


def await_commit_receipt(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    operation_id = str(state.get("pending_writeback_ref") or "")
    if not operation_id:
        return {}
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
    return {}


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


def _validate_evidence_spans(content: str, result: ChapterEvidenceResult) -> None:
    for claim in result.claims:
        for span in claim.spans:
            if span.end > len(content) or span.start >= span.end:
                raise ValueError("Evidence span is outside the accepted chapter")
            if content[span.start:span.end] != span.quote:
                raise ValueError("Evidence quote does not match the accepted chapter")


def _signature(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = ["await_commit_receipt", "enqueue_domain_commit", "extract_evidence"]
