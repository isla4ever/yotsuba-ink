from __future__ import annotations

from typing import Any

from novel_workflow.memory.canon_store import CanonFact
from novel_workflow.runtime.graph.evidence_candidates import (
    build_chapter_evidence_candidates,
)
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ProviderOperationError,
    compile_provider_input,
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
    budget = executor.output_budget_planner(state).for_evidence(binding)
    attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
    request = ChapterEvidenceRequest(
        operation_key=operation_key,
        run_id=run_id,
        chapter_id=chapter_id,
        chapter_version_id=version_id,
        attempt=attempt,
        content=chapter.content,
        binding=budget.bind(binding),
    )
    receipt = executor.operations.begin_provider(
        run_id=run_id,
        operation_key=operation_key,
        kind="chapter_evidence",
        provider_profile_id=binding.provider_profile_id,
        model=binding.model,
        provider_input=compile_provider_input(request),
    )
    if receipt.status == "succeeded":
        result = ChapterEvidenceResult.model_validate(receipt.result)
    elif receipt.status == "failed":
        return {"pending_evidence_refs": [], "pending_writeback_ref": ""}
    else:
        response = None
        try:
            response = await executor.provider.extract_chapter_evidence(request)
            result = ChapterEvidenceResult.model_validate(response.payload)
            bound_spans = _bind_evidence_spans(chapter.content, result)
        except Exception as exc:
            executor.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=response.usage if response is not None else getattr(exc, "usage", {}),
                diagnostic=response.diagnostic if response is not None else getattr(exc, "diagnostic", {}),
            )
            return {"pending_evidence_refs": [], "pending_writeback_ref": ""}
        executor.operations.succeed(
            run_id,
            operation_key,
            result.model_dump(mode="json"),
            usage=response.usage,
            diagnostic=response.diagnostic,
        )
    bound_spans = _bind_evidence_spans(chapter.content, result)
    records = [
        executor.evidence.write(
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_version_id=version_id,
            kind=claim.kind,
            claim=claim.claim,
            spans=spans,
        )
        for claim, spans in zip(result.claims, bound_spans, strict=True)
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
    return {"pending_evidence_refs": [], "pending_writeback_ref": ""}


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


def _bind_evidence_spans(
    content: str,
    result: ChapterEvidenceResult,
) -> list[list[EvidenceSpan]]:
    candidates = {
        candidate.span_id: candidate
        for candidate in build_chapter_evidence_candidates(content)
    }
    bound: list[list[EvidenceSpan]] = []
    for claim in result.claims:
        spans: list[EvidenceSpan] = []
        seen: set[str] = set()
        for span_id in claim.span_ids:
            if span_id in seen:
                raise ValueError("Evidence claim repeats one source span")
            candidate = candidates.get(span_id)
            if candidate is None:
                raise ValueError("Evidence claim references an unknown source span")
            seen.add(span_id)
            spans.append(
                EvidenceSpan(
                    start=candidate.start,
                    end=candidate.end,
                    quote=candidate.quote,
                )
            )
        bound.append(spans)
    return bound


__all__ = ["await_commit_receipt", "enqueue_domain_commit", "extract_evidence"]
