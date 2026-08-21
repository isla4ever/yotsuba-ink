from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from novel_workflow.output_contracts.provider_tasks import (
    ChapterEvidenceResult,
    EvidenceClaimProposal,
    EvidenceStateAssertionProposal,
    EvidenceStateTransitionProposal,
)
from novel_workflow.runtime.graph.evidence_candidates import (
    build_chapter_evidence_candidates,
)
from novel_workflow.storage.evidence_store import EvidenceSpan


_PROPERTY_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_EVIDENCE_STATE_FIELDS = {"source", "owner", "custody"}
_RETIRED_PROPERTY_ROOTS = {"document", "proof", "provenance"}


@dataclass(frozen=True, slots=True)
class EvidenceFailure:
    code: str
    message: str
    contract_error: bool


@dataclass(frozen=True, slots=True)
class EvidenceStateBinding:
    subject_id: str = ""
    property_key: str = ""
    value: str = ""
    epistemic_status: Literal[
        "fact", "rumour", "belief", "reveal", "refutation"
    ] = "fact"
    lifecycle: Literal["active", "supersedes", "resolves", "contradicted"] = (
        "active"
    )
    supersedes_fact_ids: tuple[str, ...] = ()
    resolves_fact_ids: tuple[str, ...] = ()


def bind_evidence_spans(
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


def project_evidence_state_bindings(
    result: ChapterEvidenceResult,
    context: dict[str, Any],
) -> list[EvidenceStateBinding]:
    """Resolve Provider choices into code-owned state and lifecycle fields."""
    frozen_subject_ids = {
        str(subject.get("id") or "").strip()
        for subject in context.get("frozen_subjects", [])
        if isinstance(subject, dict)
    }
    frozen_subject_ids.discard("")
    frozen_subject_ids.add("story")
    state_entries = {
        str(entry.get("source_fact_id") or "").strip(): entry
        for entry in (context.get("story_state") or {}).get("entries", [])
        if isinstance(entry, dict) and str(entry.get("source_fact_id") or "").strip()
    }
    existing_properties = {
        (
            str(entry.get("subject_id") or "").strip(),
            str(entry.get("property_key") or "").strip(),
        )
        for entry in state_entries.values()
        if str(entry.get("subject_id") or "").strip()
        and str(entry.get("property_key") or "").strip()
    }
    return [
        _project_claim_state(
            claim,
            frozen_subject_ids,
            state_entries,
            existing_properties,
        )
        for claim in result.claims
    ]


def _project_claim_state(
    claim: EvidenceClaimProposal,
    frozen_subject_ids: set[str],
    state_entries: dict[str, dict[str, Any]],
    existing_properties: set[tuple[str, str]],
) -> EvidenceStateBinding:
    state = claim.state
    if isinstance(state, EvidenceStateAssertionProposal):
        if state.subject_id not in frozen_subject_ids:
            raise ValueError(
                f"Evidence references an unfrozen subject: {state.subject_id}"
            )
        _validate_property_namespace(state.property_key)
        if (state.subject_id, state.property_key) in existing_properties:
            raise ValueError(
                "Evidence must transition the existing subject property via source_fact_id"
            )
        return EvidenceStateBinding(
            subject_id=state.subject_id,
            property_key=state.property_key,
            value=state.value,
            epistemic_status=state.epistemic_status,
        )
    if isinstance(state, EvidenceStateTransitionProposal):
        source = state_entries.get(state.source_fact_id)
        if source is None:
            raise ValueError(
                f"Evidence references unknown source facts: {[state.source_fact_id]}"
            )
        source_subject = str(source.get("subject_id") or "").strip()
        source_property = str(source.get("property_key") or "").strip()
        if not source_subject or not source_property:
            raise ValueError("Evidence source fact lacks a frozen state binding")
        return EvidenceStateBinding(
            subject_id=source_subject,
            property_key=source_property,
            value=state.value,
            epistemic_status=state.epistemic_status,
            lifecycle=state.action,
            supersedes_fact_ids=(state.source_fact_id,)
            if state.action == "supersedes"
            else (),
            resolves_fact_ids=(state.source_fact_id,)
            if state.action == "resolves"
            else (),
        )
    return EvidenceStateBinding(epistemic_status=state.epistemic_status)


def _validate_property_namespace(property_key: str) -> None:
    if property_key != property_key.casefold() or property_key.strip() != property_key:
        raise ValueError("Evidence property namespace must be lowercase and trimmed")
    parts = property_key.split(".")
    root = parts[0]
    if root in _RETIRED_PROPERTY_ROOTS:
        raise ValueError(f"Evidence property namespace root is retired: {root}")
    if root == "evidence":
        if (
            len(parts) != 3
            or not _PROPERTY_SEGMENT.fullmatch(parts[1])
            or parts[2] not in _EVIDENCE_STATE_FIELDS
        ):
            raise ValueError(
                "Evidence provenance properties must use evidence.<clue>.source, "
                "evidence.<clue>.owner, or evidence.<clue>.custody"
            )
        return
    if root == "knowledge":
        if len(parts) != 2 or not _PROPERTY_SEGMENT.fullmatch(parts[1]):
            raise ValueError("Character knowledge properties must use knowledge.<fact>")
        return
    if root == "object":
        if (
            len(parts) != 3
            or not _PROPERTY_SEGMENT.fullmatch(parts[1])
            or parts[2] != "state"
        ):
            raise ValueError("Durable object properties must use object.<object>.state")
        return
    if root == "clue":
        if (
            len(parts) != 3
            or not _PROPERTY_SEGMENT.fullmatch(parts[1])
            or parts[2] != "status"
        ):
            raise ValueError("Clue lifecycle properties must use clue.<clue>.status")
        return
    if parts[-1] in {*_EVIDENCE_STATE_FIELDS, "holder", "provenance", "knows"}:
        raise ValueError("Evidence property uses a reserved semantic outside its canonical namespace")


def provider_receipt_key(
    operation_key: str,
    *,
    recovery_count: int,
    attempt: int,
) -> str:
    receipt_key = operation_key
    if recovery_count:
        receipt_key = f"{receipt_key}:recovery-{recovery_count}"
    if attempt == 2:
        receipt_key = f"{receipt_key}:contract-correction"
    return receipt_key


def evidence_request_context(
    frozen_context: dict[str, Any],
    *,
    operation_key: str,
    content_hash: str,
    recovery_count: int,
    attempt: int,
    contract_error: str,
) -> dict[str, Any]:
    context = {
        **frozen_context,
        "evidence_operation": {
            "operation_key": operation_key,
            "chapter_content_hash": content_hash,
            "recovery_count": recovery_count,
        },
    }
    if attempt == 2:
        context["contract_correction"] = {
            "previous_error": contract_error,
            "required_action": (
                "Return a fresh complete Evidence object using only the supplied "
                "span ids, frozen subjects, and source fact ids. Do not change or "
                "reinterpret the accepted chapter."
            ),
        }
    return context


def evidence_failure_from_receipt(receipt: Any) -> EvidenceFailure:
    error = receipt.error if isinstance(receipt.error, dict) else {}
    return _classify_evidence_failure(
        error_type=str(error.get("type") or "ProviderOperationError"),
        message=str(error.get("message") or "Evidence Provider operation failed"),
        diagnostic=receipt.diagnostic,
    )


def evidence_failure_from_exception(
    error: Exception,
    diagnostic: dict[str, Any],
) -> EvidenceFailure:
    return _classify_evidence_failure(
        error_type=type(error).__name__,
        message=str(error),
        diagnostic=diagnostic,
    )


def visible_evidence_error(failure: EvidenceFailure) -> str:
    if failure.contract_error:
        return (
            "contract_invalid: Evidence did not match the frozen structured "
            "contract or supplied source spans"
        )
    return "provider_failed: Evidence extraction did not return a valid result"


def _classify_evidence_failure(
    *,
    error_type: str,
    message: str,
    diagnostic: dict[str, Any],
) -> EvidenceFailure:
    normalized = message.lower()
    contract_markers = (
        "source span",
        "evidence claim",
        "unfrozen subject",
        "unknown source fact",
        "state transition",
        "validation error",
        "json object",
    )
    contract_error = (
        error_type in {"ValueError", "ValidationError"}
        or isinstance(diagnostic.get("structured_parse"), dict)
        or any(marker in normalized for marker in contract_markers)
    )
    return EvidenceFailure(
        code="contract_invalid" if contract_error else "provider_failed",
        message=message,
        contract_error=contract_error,
    )


__all__ = [
    "EvidenceFailure",
    "EvidenceStateBinding",
    "bind_evidence_spans",
    "evidence_failure_from_exception",
    "evidence_failure_from_receipt",
    "evidence_request_context",
    "project_evidence_state_bindings",
    "provider_receipt_key",
    "visible_evidence_error",
]
