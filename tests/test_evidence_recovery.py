from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.runtime.graph.provider_gateway import StructuredProviderResult
from novel_workflow.runtime.graph.runtime import NarrativeRuntime, filesystem_stores
from tests.fakes import FakeNarrativeProvider
from tests.test_langgraph_narrative_runtime import (
    _advance_to_first_chapter,
    _create_run,
)


class EvidenceSequenceProvider(FakeNarrativeProvider):
    def __init__(self, outcomes: list[str]) -> None:
        super().__init__()
        self.outcomes = outcomes

    async def extract_chapter_evidence(self, request):
        self.evidence_requests.append(request)
        if not self.outcomes:
            raise AssertionError("No fake Evidence outcome remains")
        outcome = self.outcomes.pop(0)
        if outcome == "timeout":
            raise TimeoutError("simulated Evidence timeout")
        if outcome == "malformed_payload":
            return StructuredProviderResult(
                payload={"claims": []},
                usage={"total_tokens": 1},
            )
        span_ids = {
            "duplicate_span": ["span-0001", "span-0001"],
            "unknown_span": ["span-9999"],
            "valid": ["span-0001"],
        }[outcome]
        claim = "本章完成施工图目标"
        return StructuredProviderResult(
            payload={
                "claims": [
                    {
                        "kind": "fact",
                        "claim": claim,
                        "span_ids": span_ids,
                        "state": {
                            "type": "assertion",
                            "subject_id": "story",
                            "property_key": f"{request.chapter_id}.completion",
                            "value": claim,
                            "epistemic_status": "fact",
                        },
                    }
                ]
            },
            usage={"total_tokens": 1},
        )


async def _accept_first_chapter(runtime: NarrativeRuntime, run_id: str):
    paused = await _advance_to_first_chapter(runtime, run_id)
    decision = dict(paused.pending_decisions[0])
    accepted = await runtime.resume(
        run_id,
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "accept",
        },
    )
    return paused, accepted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_outcome",
    ["duplicate_span", "unknown_span", "malformed_payload"],
)
async def test_first_evidence_contract_failure_gets_one_bounded_correction(
    tmp_path,
    first_outcome: str,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = EvidenceSequenceProvider([first_outcome, "valid"])
    run_id = f"run-evidence-correction-{first_outcome}"
    _create_run(stores, run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    first_pause, next_pause = await _accept_first_chapter(runtime, run_id)

    assert next_pause.status == "awaiting_decision"
    assert next_pause.active_chapter_number == 2
    assert next_pause.pending_decisions[0]["type"] == "chapter_author_decision"
    assert len(provider.evidence_requests) == 2
    first_request, correction_request = provider.evidence_requests
    assert first_request.chapter_version_id == correction_request.chapter_version_id
    assert first_request.content == correction_request.content
    first_identity = first_request.context["evidence_operation"]
    correction_identity = correction_request.context["evidence_operation"]
    assert first_identity == correction_identity
    assert "contract_correction" not in first_request.context
    assert correction_request.context["contract_correction"]["previous_error"].startswith(
        "contract_invalid:"
    )
    first_receipt = stores.operations.read(run_id, first_request.operation_key)
    correction_receipt = stores.operations.read(
        run_id,
        correction_request.operation_key,
    )
    assert first_receipt.status == "contract_rejected"
    assert first_receipt.provider_result is not None
    assert first_receipt.usage["total_tokens"] == 1
    assert correction_receipt.status == "succeeded"
    assert stores.operations.usage_summary(run_id).returned_operations >= 2
    assert stores.operations.usage_summary(run_id).contract_rejected_operations == 1

    attempt = stores.evidence.list_attempts(run_id)[0]
    assert attempt.status == "succeeded"
    assert attempt.attempt == 2
    assert attempt.recovery_count == 0
    assert attempt.chapter_version_id == "chapter-1-v1-accepted"
    assert attempt.chapter_content_hash == first_identity["chapter_content_hash"]
    assert attempt.evidence_refs
    assert stores.outbox.read(
        run_id,
        "outbox-chapter-1-chapter-1-v1-accepted",
    ).status == "committed"
    assert len(stores.canon.facts(run_id)) == 1
    assert len(stores.wiki.list(run_id)) == 1
    assert not any(
        event.type == "evidence.recovery_required"
        for event in stores.events.read(run_id)
    )
    state = await runtime.state(run_id)
    assert state["chapter_attempts"]["chapter-1"] == 1
    assert state["chapter_version_refs"]["chapter-1"] == "chapter-1-v1-accepted"
    assert stores.chapters.read(
        run_id,
        "chapter-1",
        "chapter-1-v1-accepted",
    ).artifact.content == stores.chapters.read(
        run_id,
        "chapter-1",
        first_pause.pending_decisions[0]["artifact_ref"],
    ).artifact.content


@pytest.mark.asyncio
async def test_second_contract_failure_pauses_without_empty_writeback_and_recovers_once(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = EvidenceSequenceProvider(["unknown_span", "duplicate_span"])
    run_id = "run-evidence-needs-action"
    _create_run(stores, run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    _, recovery_pause = await _accept_first_chapter(runtime, run_id)

    assert recovery_pause.status == "awaiting_decision"
    assert recovery_pause.active_chapter_number == 1
    recovery_decision = dict(recovery_pause.pending_decisions[0])
    assert recovery_decision["type"] == "evidence_recovery_decision"
    assert recovery_decision["allowed_actions"] == ["retry_evidence", "cancel"]
    assert recovery_decision["chapter_version_id"] == "chapter-1-v1-accepted"
    assert recovery_decision["quality_decision"]["accepted"] is True
    assert recovery_decision["quality_decision"]["evidence_degraded"] is True
    assert recovery_decision["quality_decision"]["evidence_status"] == "needs_action"
    assert recovery_decision["quality_decision"]["regeneration_used"] == 0
    attempt = stores.evidence.list_attempts(run_id)[0]
    assert attempt.status == "needs_action"
    assert attempt.attempt == 2
    assert attempt.evidence_refs == []
    assert stores.evidence.list(run_id) == []
    assert stores.canon.facts(run_id) == []
    assert stores.wiki.list(run_id) == []
    with pytest.raises(FileNotFoundError):
        stores.outbox.read(
            run_id,
            "outbox-chapter-1-chapter-1-v1-accepted",
        )
    assert len(provider.evidence_requests) == 2

    unchanged = await runtime.recover(run_id)

    assert unchanged.pending_decisions == recovery_pause.pending_decisions
    assert len(provider.evidence_requests) == 2

    provider.outcomes.append("valid")
    command = {
        "decision_id": recovery_decision["decision_id"],
        "domain_revision": recovery_decision["domain_revision"],
        "action": "retry_evidence",
    }
    next_pause = await runtime.resume(run_id, command)

    assert next_pause.status == "awaiting_decision"
    assert next_pause.active_chapter_number == 2
    assert len(provider.evidence_requests) == 3
    recovered_attempt = stores.evidence.list_attempts(run_id)[0]
    assert recovered_attempt.status == "succeeded"
    assert recovered_attempt.attempt == 1
    assert recovered_attempt.recovery_count == 1
    assert recovered_attempt.chapter_version_id == attempt.chapter_version_id
    assert recovered_attempt.chapter_content_hash == attempt.chapter_content_hash
    assert len(stores.evidence.list(run_id)) == 1
    assert len(stores.canon.facts(run_id)) == 1
    assert len(stores.wiki.list(run_id)) == 1
    assert stores.outbox.read(
        run_id,
        "outbox-chapter-1-chapter-1-v1-accepted",
    ).status == "committed"
    state = await runtime.state(run_id)
    assert state["chapter_attempts"]["chapter-1"] == 1

    replay = await runtime.resume(run_id, command)

    assert replay.pending_decisions == next_pause.pending_decisions
    assert len(provider.evidence_requests) == 3
    assert len(stores.evidence.list(run_id)) == 1
    assert len(stores.canon.facts(run_id)) == 1
    assert len(stores.wiki.list(run_id)) == 1


@pytest.mark.asyncio
async def test_provider_timeout_needs_action_without_spending_contract_correction(
    tmp_path,
) -> None:
    stores = filesystem_stores(tmp_path / "runtime")
    provider = EvidenceSequenceProvider(["timeout"])
    run_id = "run-evidence-timeout"
    _create_run(stores, run_id, quality_mode="balanced")
    runtime = NarrativeRuntime.create(stores, provider, checkpointer=InMemorySaver())

    _, recovery_pause = await _accept_first_chapter(runtime, run_id)

    assert recovery_pause.status == "awaiting_decision"
    assert recovery_pause.active_chapter_number == 1
    assert len(provider.evidence_requests) == 1
    attempt = stores.evidence.list_attempts(run_id)[0]
    assert attempt.status == "needs_action"
    assert attempt.attempt == 1
    assert attempt.contract_error.startswith("provider_failed:")
    assert stores.evidence.list(run_id) == []
    assert stores.canon.facts(run_id) == []

    provider.outcomes.append("valid")
    decision = recovery_pause.pending_decisions[0]
    next_pause = await runtime.resume(
        run_id,
        {
            "decision_id": decision["decision_id"],
            "domain_revision": decision["domain_revision"],
            "action": "retry_evidence",
        },
    )

    assert next_pause.active_chapter_number == 2
    assert len(provider.evidence_requests) == 2
    recovered_attempt = stores.evidence.list_attempts(run_id)[0]
    assert recovered_attempt.status == "succeeded"
    assert recovered_attempt.recovery_count == 1
    assert recovered_attempt.attempt == 1


def test_evidence_operation_rejects_accepted_prose_identity_drift(tmp_path) -> None:
    store = filesystem_stores(tmp_path / "runtime").evidence
    values = {
        "operation_key": "run-identity:chapter-1:evidence:accepted-v1",
        "run_id": "run-identity",
        "chapter_id": "chapter-1",
        "chapter_version_id": "chapter-1-v1-accepted",
    }
    store.begin_attempt(**values, chapter_content_hash="a" * 64)

    with pytest.raises(ValueError, match="different accepted prose"):
        store.begin_attempt(**values, chapter_content_hash="b" * 64)
