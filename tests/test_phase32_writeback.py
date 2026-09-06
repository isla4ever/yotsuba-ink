from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.memory.phase32_wiki_projection import Phase32WikiProjectionStore
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingConflict,
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_writeback import Phase32WritebackService
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    ScreenplayDraftArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    CharacterBibleArtifact,
    SectionPlanArtifact,
)
from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderResponse,
    Phase32WritebackProviderRequest,
)
from novel_workflow.references.phase32_writeback_context import render_writeback_prompt
from novel_workflow.runtime.graph.route_run_state import (
    RouteRunStateSnapshot,
    SequentialStageProgress,
    initial_route_run_state,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_artifact_draft_store import Phase32ArtifactDraftStore
from novel_workflow.storage.phase32_evidence_store import Phase32EvidenceStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.phase32_writeback_outbox import Phase32WritebackOutbox
from novel_workflow.storage.route_run_read_model import (
    ArtifactRefProjection,
    PendingDecisionProjection,
    initial_route_run_read_model,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)
from tests.test_phase32_driver import _continuity_acceptance_definition, _payload_for
from tests.test_phase32_route_graph import _definition


ROUTES = (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE)


def test_writeback_prompt_makes_discriminated_state_and_span_limits_explicit() -> None:
    prompt = render_writeback_prompt(
        {
            "frozen_subject_refs": ["archivist"],
            "source_spans": [{"span_id": "span-0001", "quote": "发现证据"}],
        }
    )

    assert "state 必须是对象，不能是字符串" in prompt
    assert '"type":"story"' in prompt
    assert '"type":"assertion"' in prompt
    assert '"type":"transition"' in prompt
    assert "每条 claim 必须只引用 1-3 个给定 span_id（绝不能超过 3 个）" in prompt
    assert "每个 span_ids 必须是长度为 1、2 或 3 的 JSON 数组" in prompt
    assert "绝不超过 8 条 claim" in prompt
    assert "最小的连续证据窗口" in prompt
    assert "不要使用 confirmed" in prompt
    assert "首段只能是 character、relationship、world、location、object、clue、knowledge 或 promise" in prompt
    assert "不得使用 evidence、accusation、response 等未注册命名空间" in prompt
    assert "assertion.subject_ref 必须逐字等于 frozen_subject_refs 中的一个值" in prompt
    assert '"subject_ref":"archivist"' in prompt
    assert "property_key 必须至少包含一个点" in prompt
    assert "禁止使用 transition" in prompt
    assert "绝不能输出 p32-fact-... 等占位符" in prompt
    assert "输出前硬检查" in prompt
    assert "state.type 只能是 story、assertion、transition" in prompt

    prompt_with_existing = render_writeback_prompt(
        {
            "frozen_subject_refs": ["archivist"],
            "existing_facts": [
                {
                    "fact_ref": "p32-fact-abc",
                    "subject_ref": "archivist",
                    "property_key": "clue.status",
                }
            ],
            "source_spans": [{"span_id": "span-0001", "quote": "发现证据"}],
        }
    )
    assert '"subject_ref":"archivist"' in prompt_with_existing
    assert '"property_key":"clue.status"' in prompt_with_existing
    assert "必须引用对应的精确 fact_ref 并使用 state.type=transition" in prompt_with_existing
    assert "禁止再次使用 state.type=assertion" in prompt_with_existing

    correction_prompt = render_writeback_prompt(
        {
            "frozen_subject_refs": ["archivist"],
            "source_spans": [{"span_id": "span-0001", "quote": "发现证据"}],
        },
        correction="上一次输出的 claims.0.span_ids 超过最多 3 项",
    )
    assert "合同纠正（最高优先级）" in correction_prompt
    assert "保留未违规 claim，只修复指出的字段" in correction_prompt
    assert "不要因为单条 span_ids 超限而清空全部 claims" in correction_prompt


class _ProcessExit(BaseException):
    pass


class _WritebackGateway:
    def __init__(self, payloads: list[dict[str, Any]] | None = None) -> None:
        self.payloads = list(payloads or [_story_claims()])
        self.requests: list[Phase32WritebackProviderRequest] = []

    async def generate_writeback(
        self,
        request: Phase32WritebackProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        payload = self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
        return Phase32ProviderResponse(payload=payload, usage={"total_tokens": 11})


class _TransportFlakyWritebackGateway(_WritebackGateway):
    """Fail once at transport level, then return the deterministic payload."""

    def __init__(self) -> None:
        super().__init__()
        self.failures_remaining = 1

    async def generate_writeback(
        self,
        request: Phase32WritebackProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("simulated network timeout")
        return Phase32ProviderResponse(payload=self.payloads[0], usage={"total_tokens": 11})


class _WritebackAdmissionDenied(ValueError):
    code = "phase32_run_budget_admission_denied"


class _RecordingWritebackAdmission:
    def __init__(
        self,
        *,
        deny_operation: bool = False,
        mismatch_identity_field: str = "",
    ) -> None:
        self.deny_operation = deny_operation
        self.mismatch_identity_field = mismatch_identity_field
        self.required_definitions: list[GraphRunDefinition] = []
        self.admitted_requests: list[Phase32WritebackProviderRequest] = []
        self.admitted_fences: list[Phase32ProviderOperationAdmissionFence] = []

    def require_run(self, definition: GraphRunDefinition) -> None:
        self.required_definitions.append(definition)

    def admit_text_operation(
        self,
        *,
        definition,
        request,
        binding,
        request_signature: str,
        max_transport_attempts: int,
    ) -> Phase32ProviderOperationAdmissionFence:
        self.admitted_requests.append(request)
        if self.deny_operation:
            raise _WritebackAdmissionDenied("writeback budget denied")
        transport_attempt = 1 + sum(
            previous.operation_key == request.operation_key
            for previous in self.admitted_requests[:-1]
        )
        digest = hashlib.sha256(
            f"{request.operation_key}\0{transport_attempt}".encode("utf-8")
        ).hexdigest()
        fence = Phase32ProviderOperationAdmissionFence(
            authorization_ref=(
                "p32-run-budget-"
                + hashlib.sha256(definition.definition_digest.encode("utf-8")).hexdigest()
            ),
            run_id=definition.run_id,
            definition_digest=definition.definition_digest,
            operation_key=request.operation_key,
            request_signature=request_signature,
            admission_ref=f"p32-budget-admission-{digest}",
            transport_attempt=transport_attempt,
        )
        self.admitted_fences.append(fence)
        if self.mismatch_identity_field:
            mismatches = {
                "operation_key": "another-operation",
                "run_id": "another-run",
                "request_signature": "f" * 64,
            }
            return fence.model_copy(
                update={
                    self.mismatch_identity_field: mismatches[
                        self.mismatch_identity_field
                    ]
                }
            )
        return fence


@dataclass
class _WritebackFixture:
    root: Path
    definition: GraphRunDefinition
    state: RouteRunStateSnapshot
    stage_id: str
    unit_ref: str
    source: Phase32ArtifactRecord
    artifacts: Phase32ArtifactStore
    evidence: Phase32EvidenceStore
    canon: Phase32CanonStore
    wiki: Phase32WikiProjectionStore
    outbox: Phase32WritebackOutbox
    provider_inputs: Phase32ProviderInputStore
    provider_operations: Phase32ProviderOperationStore
    gateway: _WritebackGateway
    text_operation_admission: Any | None
    service: Phase32WritebackService


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.route_id)
async def test_accepted_unit_writes_source_bound_evidence_canon_and_wiki(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    fixture = _fixture(tmp_path / route.route_id, route)

    receipt = await _commit(fixture)

    assert receipt.status == "committed"
    assert len(fixture.gateway.requests) == 1
    assert len(receipt.evidence_refs) == 1
    assert len(receipt.fact_refs) == 1
    evidence = fixture.evidence.list(fixture.definition.run_id)
    facts = fixture.canon.facts(fixture.definition.run_id)
    wiki = fixture.wiki.list(fixture.definition.run_id)
    assert tuple(item.evidence_ref for item in evidence) == receipt.evidence_refs
    assert tuple(item.fact_ref for item in facts) == receipt.fact_refs
    assert evidence[0].source_artifact_ref == fixture.source.artifact_ref
    assert evidence[0].source_payload_digest == fixture.source.payload_digest
    assert evidence[0].unit_ref == fixture.unit_ref
    assert wiki[0].transaction_ref == receipt.transaction_ref
    assert wiki[0].facts == facts


@pytest.mark.asyncio
async def test_candidate_unknown_source_and_unit_cursor_drift_never_write_canon(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE)
    artifact = ShortProseUnitArtifact.model_validate(_payload_for("short_novel", "text"))
    candidate = fixture.artifacts.save_candidate(
        run_id=fixture.definition.run_id,
        creation_route_id="short_novel",
        stage_id="text",
        artifact=artifact,
        source_operation_key="candidate-is-not-accepted",
    )

    with pytest.raises(ValueError, match="accepted current unit"):
        await _commit(fixture, artifact_ref=candidate.artifact_ref)
    with pytest.raises(FileNotFoundError):
        await _commit(fixture, artifact_ref="p32-text-committed-" + "0" * 64)

    drifted = fixture.state.model_copy(
        update={
            "active_unit_ref": "prior-unit",
            "sequential_stage_progress": {
                "text": SequentialStageProgress(
                    ordered_unit_refs=("prior-unit", fixture.unit_ref)
                ).model_dump(mode="json")
            },
        }
    )
    with pytest.raises(ValueError, match="next accepted unit"):
        await fixture.service.commit(
            definition=fixture.definition,
            state=drifted,
            stage=fixture.definition.stage("text"),
            artifact_ref=fixture.source.artifact_ref,
            unit_ref=fixture.unit_ref,
        )

    assert fixture.canon.facts(fixture.definition.run_id) == ()
    assert fixture.wiki.list(fixture.definition.run_id) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (
            {
                "claims": [
                    {
                        "kind": "fact",
                        "claim": "这条事实没有对应的冻结片段。",
                        "span_ids": ["span-9999"],
                        "state": {"type": "story", "epistemic_status": "fact"},
                    }
                ]
            },
            "unknown source span",
        ),
        (
            {
                "claims": [
                    {
                        "kind": "character",
                        "claim": "未知人物拿走了证物。",
                        "span_ids": ["span-0001"],
                        "state": {
                            "type": "assertion",
                            "subject_ref": "subject-ghost",
                            "property_key": "character.evidence_status",
                            "value": "持有证物",
                            "epistemic_status": "fact",
                        },
                    }
                ]
            },
            "unfrozen subject",
        ),
    ),
)
async def test_span_and_subject_drift_require_visible_recovery(
    tmp_path: Path,
    payload: dict[str, Any],
    message: str,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE, payloads=[payload])

    receipt = await _commit(fixture)

    assert receipt.status == "needs_action"
    assert receipt.error_code == "evidence_proposal_failed"
    assert message in receipt.error_message
    assert fixture.evidence.list(fixture.definition.run_id) == ()
    assert fixture.canon.facts(fixture.definition.run_id) == ()
    assert fixture.wiki.list(fixture.definition.run_id) == ()


@pytest.mark.asyncio
async def test_binding_recovery_prompt_carries_forward_the_visible_error(
    tmp_path: Path,
) -> None:
    invalid = {
        "claims": [
            {
                "kind": "fact",
                "claim": "未知人物拿走了证物。",
                "span_ids": ["span-0001"],
                "state": {
                    "type": "assertion",
                    "subject_ref": "subject-ghost",
                    "property_key": "character.evidence_status",
                    "value": "持有证物",
                    "epistemic_status": "fact",
                },
            }
        ]
    }
    fixture = _fixture(
        tmp_path,
        SHORT_NOVEL_ROUTE,
        payloads=[invalid, _story_claims()],
    )

    blocked = await _commit(fixture)
    recovered = await _commit(fixture, retry=True)

    assert blocked.status == "needs_action"
    assert recovered.status == "committed"
    assert len(fixture.gateway.requests) == 2
    retry_prompt = fixture.gateway.requests[1].rendered_prompt
    assert "上一次返回违反合同" in retry_prompt
    assert "Evidence references an unfrozen subject: subject-ghost" in retry_prompt
    assert fixture.gateway.requests[1].operation_key != fixture.gateway.requests[0].operation_key


@pytest.mark.asyncio
async def test_transport_recovery_reuses_pending_writeback_operation(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE)
    gateway = _TransportFlakyWritebackGateway()
    fixture.gateway = gateway
    fixture.service.gateway = gateway

    blocked = await _commit(fixture)
    assert blocked.status == "needs_action"
    first_operation = fixture.provider_operations.list(fixture.definition.run_id)
    assert len(first_operation) == 1
    assert first_operation[0].status == "pending"

    recovered = await _commit(fixture, retry=True)

    assert recovered.status == "committed"
    assert len(gateway.requests) == 2
    assert gateway.requests[1].operation_key == gateway.requests[0].operation_key
    assert gateway.requests[1].rendered_prompt == gateway.requests[0].rendered_prompt
    operations = fixture.provider_operations.list(fixture.definition.run_id)
    assert len(operations) == 1
    assert operations[0].status == "succeeded"
    assert all(item.status != "pending" for item in operations)
    assert recovered.provider_operation_refs == (operations[0].receipt_ref,)


@pytest.mark.asyncio
async def test_continuity_writeback_requires_run_admission_before_input_or_receipt(
    tmp_path: Path,
) -> None:
    fixture = _fixture(
        tmp_path,
        LONG_NOVEL_ROUTE,
        definition=_continuity_acceptance_definition(),
    )

    receipt = await _commit(fixture)

    assert receipt.status == "needs_action"
    assert receipt.error_code == "phase32_text_operation_admission_required"
    assert fixture.provider_inputs.list(fixture.definition.run_id) == []
    assert fixture.provider_operations.list(fixture.definition.run_id) == []
    assert fixture.gateway.requests == []


@pytest.mark.asyncio
async def test_continuity_writeback_denies_operation_before_claim_and_gateway(
    tmp_path: Path,
) -> None:
    admission = _RecordingWritebackAdmission(deny_operation=True)
    fixture = _fixture(
        tmp_path,
        LONG_NOVEL_ROUTE,
        definition=_continuity_acceptance_definition(),
        text_operation_admission=admission,
    )

    receipt = await _commit(fixture)

    assert receipt.status == "needs_action"
    assert receipt.error_code == "phase32_run_budget_admission_denied"
    operations = fixture.provider_operations.list(fixture.definition.run_id)
    assert len(admission.required_definitions) == 1
    assert len(admission.admitted_requests) == 1
    assert len(operations) == 1
    assert operations[0].status == "pending"
    assert operations[0].transport_attempts == 0
    assert operations[0].transport_admission_refs == ()
    assert fixture.gateway.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identity_field",
    ("operation_key", "run_id", "request_signature"),
)
async def test_continuity_writeback_rejects_mismatched_admission_identity_before_gateway(
    tmp_path: Path,
    identity_field: str,
) -> None:
    admission = _RecordingWritebackAdmission(
        mismatch_identity_field=identity_field,
    )
    fixture = _fixture(
        tmp_path,
        LONG_NOVEL_ROUTE,
        definition=_continuity_acceptance_definition(),
        text_operation_admission=admission,
    )

    receipt = await _commit(fixture)

    assert receipt.status == "needs_action"
    assert receipt.error_code == "phase32_provider_operation_attempt_fence_conflict"
    operations = fixture.provider_operations.list(fixture.definition.run_id)
    assert len(operations) == 1
    assert operations[0].transport_attempts == 0
    assert operations[0].transport_admission_refs == ()
    assert operations[0].lease_owner == ""
    assert fixture.gateway.requests == []


@pytest.mark.asyncio
async def test_continuity_writeback_replay_does_not_readmit_returned_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission = _RecordingWritebackAdmission()
    fixture = _fixture(
        tmp_path,
        LONG_NOVEL_ROUTE,
        definition=_continuity_acceptance_definition(),
        text_operation_admission=admission,
    )
    original_record_return = fixture.provider_operations.record_return

    def stop_after_return(**kwargs):
        original_record_return(**kwargs)
        raise _ProcessExit("process stopped after Provider return")

    monkeypatch.setattr(fixture.provider_operations, "record_return", stop_after_return)
    with pytest.raises(_ProcessExit):
        await _commit(fixture)

    reopened = _reopen(fixture)
    receipt = await _commit(reopened)

    assert receipt.status == "committed"
    assert len(admission.required_definitions) == 2
    assert len(admission.admitted_requests) == 1
    assert len(fixture.gateway.requests) == 1
    operation = reopened.provider_operations.list(fixture.definition.run_id)[0]
    assert operation.status == "succeeded"
    assert operation.transport_admission_refs == (
        admission.admitted_fences[0].admission_ref,
    )


@pytest.mark.asyncio
async def test_continuity_writeback_transport_retry_requests_a_new_admission(
    tmp_path: Path,
) -> None:
    admission = _RecordingWritebackAdmission()
    fixture = _fixture(
        tmp_path,
        LONG_NOVEL_ROUTE,
        definition=_continuity_acceptance_definition(),
        text_operation_admission=admission,
    )
    gateway = _TransportFlakyWritebackGateway()
    fixture.gateway = gateway
    fixture.service.gateway = gateway

    blocked = await _commit(fixture)
    recovered = await _commit(fixture, retry=True)

    assert blocked.status == "needs_action"
    assert recovered.status == "committed"
    assert len(admission.admitted_requests) == 2
    assert len(gateway.requests) == 2
    operations = fixture.provider_operations.list(fixture.definition.run_id)
    assert len(operations) == 1
    assert operations[0].transport_attempts == 2
    assert operations[0].transport_admission_refs == tuple(
        fence.admission_ref for fence in admission.admitted_fences
    )
    assert operations[0].status == "succeeded"


@pytest.mark.asyncio
async def test_provider_contract_failure_is_classified_without_persisting_provider_values(
    tmp_path: Path,
) -> None:
    malformed = {
        "claims": [
            {
                "kind": "fact",
                "claim": "模型把旧版状态写成字符串。",
                "span_ids": [
                    "span-0001",
                    "span-0002",
                    "span-0003",
                    "span-0004",
                ],
                "state": "confirmed",
            }
        ]
    }
    fixture = _fixture(
        tmp_path,
        SHORT_NOVEL_ROUTE,
        payloads=[malformed, malformed],
    )

    receipt = await _commit(fixture)

    assert receipt.status == "needs_action"
    assert receipt.error_code == "writeback_contract_invalid"
    assert "phase32-writeback-v1" in receipt.error_message
    operations = fixture.provider_operations.list(fixture.definition.run_id)
    assert len(operations) == 2
    assert all(item.status == "contract_rejected" for item in operations)
    diagnostics = [item.diagnostic for item in operations]
    assert all(item["code"] == "writeback_contract_invalid" for item in diagnostics)
    assert all(item["validation_errors"] for item in diagnostics)
    assert all("input" not in item for item in diagnostics[0]["validation_errors"])
    assert fixture.evidence.list(fixture.definition.run_id) == ()
    assert fixture.canon.facts(fixture.definition.run_id) == ()
    assert fixture.wiki.list(fixture.definition.run_id) == ()


@pytest.mark.asyncio
async def test_span_limit_contract_correction_keeps_valid_recovery_claims(
    tmp_path: Path,
) -> None:
    malformed = {
        "claims": [
            {
                "kind": "fact",
                "claim": "一条事实被四个证据片段支持。",
                "span_ids": [
                    "span-0001",
                    "span-0002",
                    "span-0003",
                    "span-0004",
                ],
                "state": {"type": "story", "epistemic_status": "fact"},
            }
        ]
    }
    fixture = _fixture(
        tmp_path,
        SHORT_NOVEL_ROUTE,
        payloads=[malformed, _story_claims()],
    )

    receipt = await _commit(fixture)

    assert receipt.status == "committed"
    assert len(fixture.gateway.requests) == 2
    retry_prompt = fixture.gateway.requests[1].rendered_prompt
    assert "合同纠正（最高优先级）" in retry_prompt
    assert "只修改超限 claim 的 span_ids" in retry_prompt
    assert "保留其他合同正确的 claim" in retry_prompt
    operations = fixture.provider_operations.list(fixture.definition.run_id)
    assert sorted(item.status for item in operations) == [
        "contract_rejected",
        "succeeded",
    ]


@pytest.mark.asyncio
async def test_repeated_commit_does_not_repeat_any_writeback_side_effect(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE)

    first = await _commit(fixture)
    second = await _commit(fixture)

    assert second == first
    assert len(fixture.gateway.requests) == 1
    assert len(fixture.provider_operations.list(fixture.definition.run_id)) == 1
    assert len(fixture.evidence.list(fixture.definition.run_id)) == 1
    assert len(fixture.canon.transactions(fixture.definition.run_id)) == 1
    assert len(fixture.wiki.list(fixture.definition.run_id)) == 1


@pytest.mark.asyncio
async def test_provider_returned_recovery_reuses_receipt_without_provider_recall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE)
    original_record_return = fixture.provider_operations.record_return

    def stop_after_return(**kwargs):
        original_record_return(**kwargs)
        raise _ProcessExit("process stopped after Provider return")

    monkeypatch.setattr(fixture.provider_operations, "record_return", stop_after_return)
    with pytest.raises(_ProcessExit):
        await _commit(fixture)
    assert len(fixture.gateway.requests) == 1
    assert fixture.provider_operations.list(fixture.definition.run_id)[0].status == "returned"

    reopened = _reopen(fixture)
    receipt = await _commit(reopened)

    assert receipt.status == "committed"
    assert len(fixture.gateway.requests) == 1
    assert reopened.provider_operations.list(fixture.definition.run_id)[0].status == "succeeded"


@pytest.mark.asyncio
async def test_queued_outbox_recovery_never_repeats_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE)

    def stop_before_flush(*args, **kwargs):
        raise _ProcessExit("process stopped with queued Outbox")

    monkeypatch.setattr(fixture.outbox, "flush", stop_before_flush)
    with pytest.raises(_ProcessExit):
        await _commit(fixture)
    queued = fixture.outbox.list(fixture.definition.run_id)[0]
    assert queued.receipt.status == "queued"
    assert queued.receipt.transaction_ref

    reopened = _reopen(fixture)
    receipt = await _commit(reopened)

    assert receipt.status == "committed"
    assert len(fixture.gateway.requests) == 1
    assert len(reopened.canon.transactions(fixture.definition.run_id)) == 1
    assert len(reopened.wiki.list(fixture.definition.run_id)) == 1


@pytest.mark.asyncio
async def test_new_process_reconciles_canon_commit_without_wiki_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, LONG_NOVEL_ROUTE)

    def stop_before_wiki(**kwargs):
        raise _ProcessExit("process stopped after Canon commit")

    monkeypatch.setattr(fixture.wiki, "project", stop_before_wiki)
    with pytest.raises(_ProcessExit):
        await _commit(fixture)
    pending = fixture.outbox.list(fixture.definition.run_id)[0]
    assert pending.receipt.status == "canon_committed"
    assert len(fixture.canon.transactions(fixture.definition.run_id)) == 1
    assert fixture.wiki.list(fixture.definition.run_id) == ()

    reopened = _reopen(fixture)
    receipts = reopened.service.reconcile(fixture.definition.run_id)

    assert len(receipts) == 1
    assert receipts[0].status == "committed"
    assert len(fixture.gateway.requests) == 1
    assert len(reopened.canon.transactions(fixture.definition.run_id)) == 1
    assert len(reopened.wiki.list(fixture.definition.run_id)) == 1


@pytest.mark.asyncio
async def test_empty_claim_bundle_commits_a_zero_fact_receipt(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SCREENPLAY_SAMPLE_ROUTE, payloads=[{"claims": []}])

    receipt = await _commit(fixture)

    assert receipt.status == "committed"
    assert receipt.evidence_refs == ()
    assert receipt.fact_refs == ()
    assert receipt.transaction_ref
    assert fixture.evidence.list(fixture.definition.run_id) == ()
    assert fixture.canon.transactions(fixture.definition.run_id)[0].facts == ()
    assert fixture.wiki.list(fixture.definition.run_id)[0].facts == ()


def test_writeback_recovery_reads_committed_source_without_opening_author_edits(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, SHORT_NOVEL_ROUTE)
    section_plan = fixture.artifacts.save_deterministic(
        run_id=fixture.definition.run_id,
        creation_route_id="short_novel",
        stage_id="section_plan",
        artifact=SectionPlanArtifact.model_validate(
            _payload_for("short_novel", "section_plan")
        ),
    )
    fixture.state = fixture.state.model_copy(
        update={
            "artifact_refs": {
                **fixture.state.artifact_refs,
                "section_plan": section_plan.artifact_ref,
            }
        }
    )
    repository = Phase32RunRepository(tmp_path / "runtime")
    decision = PendingDecisionProjection(
        decision_id="writeback-recovery-unit-1",
        stage_id="text",
        unit_ref=fixture.unit_ref,
        artifact_ref=fixture.source.artifact_ref,
        kind="writeback_recovery",
        domain_revision=0,
        allowed_actions=("retry_writeback", "cancel"),
    )
    read_model = initial_route_run_read_model(
        fixture.definition,
        updated_at="2026-08-25T12:00:00+08:00",
    ).model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": fixture.unit_ref,
            "stage_status": {
                **fixture.state.stage_status,
                "text": "running",
            },
            "artifact_refs": {
                stage_id: ArtifactRefProjection(
                    artifact_kind=fixture.definition.stage(stage_id).artifact_kind,
                    artifact_ref=artifact_ref,
                )
                for stage_id, artifact_ref in fixture.state.artifact_refs.items()
            },
            "sequential_stage_progress": {
                "text": SequentialStageProgress(
                    ordered_unit_refs=(fixture.unit_ref,)
                )
            },
            "pending_decisions": (decision,),
        }
    )
    repository.create(
        fixture.definition,
        state=fixture.state,
        read_model=read_model,
    )
    editing = Phase32ArtifactEditingService(
        repository,
        fixture.artifacts,
        Phase32ArtifactDraftStore(tmp_path / "drafts"),
    )

    current = editing.current(
        fixture.definition.run_id,
        "text",
        unit_ref=fixture.unit_ref,
    )

    assert current.status == "committed"
    assert current.artifact_ref == fixture.source.artifact_ref
    assert current.editable is False
    assert current.pending_decision == decision
    with pytest.raises(
        Phase32ArtifactEditingConflict,
        match="cannot edit an accepted Artifact",
    ):
        editing.save_draft(
            fixture.definition.run_id,
            decision.decision_id,
            domain_revision=0,
            source_artifact_ref=fixture.source.artifact_ref,
            payload=fixture.source.payload,
        )


def _fixture(
    root: Path,
    route: CreationRouteSpec,
    *,
    payloads: list[dict[str, Any]] | None = None,
    definition: GraphRunDefinition | None = None,
    text_operation_admission: Any | None = None,
) -> _WritebackFixture:
    definition = definition or _definition(route)
    artifacts = Phase32ArtifactStore(root / "artifacts")
    cast = artifacts.save_deterministic(
        run_id=definition.run_id,
        creation_route_id=route.route_id,
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(_payload_for(route.route_id, "cast")),
    )
    stage_id = "script" if route.route_id == "screenplay_sample" else "text"
    artifact_type = {
        "screenplay_sample": ScreenplayDraftArtifact,
        "short_novel": ShortProseUnitArtifact,
        "long_novel": ChapterArtifact,
    }[route.route_id]
    source = artifacts.save_deterministic(
        run_id=definition.run_id,
        creation_route_id=route.route_id,
        stage_id=stage_id,
        artifact=artifact_type.model_validate(_payload_for(route.route_id, stage_id)),
    )
    unit_ref = {
        "screenplay_sample": "scene-1",
        "short_novel": "unit-1",
        "long_novel": "chapter-1",
    }[route.route_id]
    progress = SequentialStageProgress(ordered_unit_refs=(unit_ref,))
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": stage_id,
            "active_unit_ref": unit_ref,
            "artifact_refs": {"cast": cast.artifact_ref},
            "sequential_stage_progress": {
                stage_id: progress.model_dump(mode="json")
            },
        }
    )
    gateway = _WritebackGateway(payloads)
    evidence = Phase32EvidenceStore(root / "evidence")
    canon = Phase32CanonStore(root / "canon")
    wiki = Phase32WikiProjectionStore(root / "wiki")
    outbox = Phase32WritebackOutbox(root / "outbox", canon=canon, wiki=wiki)
    provider_inputs = Phase32ProviderInputStore(root / "provider_inputs")
    provider_operations = Phase32ProviderOperationStore(
        root / "provider_operations",
        provider_inputs=provider_inputs,
    )
    service = Phase32WritebackService(
        artifacts=artifacts,
        evidence=evidence,
        canon=canon,
        outbox=outbox,
        provider_inputs=provider_inputs,
        provider_operations=provider_operations,
        gateway=gateway,
        text_operation_admission=text_operation_admission,
    )
    return _WritebackFixture(
        root=root,
        definition=definition,
        state=state,
        stage_id=stage_id,
        unit_ref=unit_ref,
        source=source,
        artifacts=artifacts,
        evidence=evidence,
        canon=canon,
        wiki=wiki,
        outbox=outbox,
        provider_inputs=provider_inputs,
        provider_operations=provider_operations,
        gateway=gateway,
        text_operation_admission=text_operation_admission,
        service=service,
    )


def _reopen(fixture: _WritebackFixture) -> _WritebackFixture:
    reopened = _fixture(
        fixture.root,
        {
            "screenplay_sample": SCREENPLAY_SAMPLE_ROUTE,
            "short_novel": SHORT_NOVEL_ROUTE,
            "long_novel": LONG_NOVEL_ROUTE,
        }[fixture.definition.creation_route_id],
        payloads=fixture.gateway.payloads,
        definition=fixture.definition,
        text_operation_admission=fixture.text_operation_admission,
    )
    reopened.gateway = fixture.gateway
    reopened.service.gateway = fixture.gateway
    return reopened


async def _commit(
    fixture: _WritebackFixture,
    *,
    artifact_ref: str | None = None,
    retry: bool = False,
):
    return await fixture.service.commit(
        definition=fixture.definition,
        state=fixture.state,
        stage=fixture.definition.stage(fixture.stage_id),
        artifact_ref=artifact_ref or fixture.source.artifact_ref,
        unit_ref=fixture.unit_ref,
        retry=retry,
    )


def _story_claims() -> dict[str, Any]:
    return {
        "claims": [
            {
                "kind": "fact",
                "claim": "主角已经取得一份可继续核验的档案证据。",
                "span_ids": ["span-0001"],
                "state": {"type": "story", "epistemic_status": "fact"},
            }
        ]
    }
