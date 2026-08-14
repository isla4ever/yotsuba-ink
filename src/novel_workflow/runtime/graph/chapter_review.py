from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from langgraph.types import Send

from novel_workflow.runtime.graph.chapter_decision import request_chapter_decision
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterReviewRequest,
    ChapterReviewResult,
    ProviderOperationError,
    validate_review_result_contract,
)
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.state import NarrativeRunState


@dataclass(frozen=True, slots=True)
class ReviewerSpec:
    role: str
    required: bool = True


DEFAULT_REVIEWERS: tuple[ReviewerSpec, ...] = (
    ReviewerSpec("continuity"),
    ReviewerSpec("character"),
    ReviewerSpec("prose", required=False),
)


def freeze_review_roles(
    reviewers: tuple[ReviewerSpec, ...],
    quality_mode: str,
) -> dict[str, Any]:
    return {
        "active_review_roles": [
            {
                "role": spec.role,
                "required": spec.required or quality_mode == "deep",
            }
            for spec in reviewers
        ]
    }


async def _review_with_contract_retry(
    executor: StageExecutor,
    request: ChapterReviewRequest,
) -> tuple[Any, ChapterReviewResult]:
    """One retry that tells the reviewer how its last answer broke the contract.

    A required lane that returns a malformed finding — an unquoted excerpt, a
    finding with no frozen subject — is discarded whole, and a discarded
    required lane stops the author decision on a chapter that may be fine. The
    reviewer usually repairs the shape when the exact rejection is quoted back,
    so retrying once here is cheaper than making the author regenerate prose.
    """
    last: ProviderOperationError | None = None
    for attempt in range(2):
        candidate = request if last is None else _with_contract_note(request, str(last))
        try:
            response = await executor.provider.review_chapter(candidate)
        except ProviderOperationError as exc:
            if attempt or not isinstance(exc.__cause__, ValueError):
                raise
            last = exc
            continue
        return response, drop_compliance_findings(
            ChapterReviewResult.model_validate(response.payload)
        )
    raise last if last is not None else ProviderOperationError(
        "Chapter review exhausted its contract retry", operation_key=request.operation_key
    )


_COMPLIANCE_CLAIMS = ("无违规", "未违反", "没有违反", "不存在违规", "符合", "一致", "no violation")
_VIOLATION_CLAIMS = ("不符合", "不一致", "未能符合", "并不一致")


def drop_compliance_findings(result: ChapterReviewResult) -> ChapterReviewResult:
    """Discard findings whose own claim says the chapter obeys the rule.

    Reviewers periodically answer a constraint check by restating that the
    chapter satisfies it, and still stamp the entry blocking. Such an entry
    stops the author on a chapter its own text declares clean, and it carries
    nothing to act on, so it is dropped rather than shown or counted.
    """
    kept = [finding for finding in result.findings if not _asserts_compliance(finding.claim)]
    if len(kept) == len(result.findings):
        return result
    return result.model_copy(update={"findings": kept})


def _asserts_compliance(claim: str) -> bool:
    text = claim.strip()
    if not text or any(marker in text for marker in _VIOLATION_CLAIMS):
        return False
    return any(marker in text for marker in _COMPLIANCE_CLAIMS)


def _with_contract_note(request: ChapterReviewRequest, reason: str) -> ChapterReviewRequest:
    context = dict(request.context)
    context["contract_violation"] = (
        f"Your previous answer was rejected: {reason}. Return only findings that satisfy the contract, "
        "or an empty findings list."
    )
    return request.model_copy(update={"context": context})


async def execute_review(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    role = str(state["review_role"])
    required = bool(state["review_required"])
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    operation_key = f"{run_id}:{chapter_id}:review:{version_id}:{role}"
    binding = executor.runs.definition(run_id).provider_bindings.get("text")
    if binding is None:
        raise ProviderOperationError("No frozen Provider binding for text review")
    planner = executor.output_budget_planner(state)
    budget = planner.for_review(binding)
    request = ChapterReviewRequest(
        operation_key=operation_key,
        run_id=run_id,
        chapter_id=chapter_id,
        chapter_version_id=version_id,
        role=role,
        required=required,
        binding=budget.bind(binding),
        context=planner.attach(executor.context_compiler().review(state, role), budget),
    )
    executor.events.append(
        run_id,
        event_id=f"{operation_key}:started",
        type="review.started",
        stage_id="text",
        node_id="text.review_chapter",
        chapter_id=chapter_id,
        status="running",
        payload={"role": role, "required": required},
        payload_ref=operation_key,
    )
    receipt = executor.operations.begin(
        run_id=run_id,
        operation_key=operation_key,
        kind="chapter_review",
        request_signature=_signature(request.model_dump(mode="json")),
        provider_profile_id=binding.provider_profile_id,
        model=binding.model,
    )
    if receipt.status == "succeeded":
        result = ChapterReviewResult.model_validate(receipt.result)
    elif receipt.status == "failed":
        result = ChapterReviewResult(role=role, available=False)
    else:
        response = None
        try:
            response, result = await _review_with_contract_retry(executor, request)
        except Exception as exc:
            executor.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=response.usage if response is not None else getattr(exc, "usage", {}),
                diagnostic=response.diagnostic if response is not None else getattr(exc, "diagnostic", {}),
            )
            result = ChapterReviewResult(role=role, available=False)
        else:
            executor.operations.succeed(
                run_id,
                operation_key,
                result.model_dump(mode="json"),
                usage=response.usage,
                diagnostic=response.diagnostic,
            )
    executor.events.append(
        run_id,
        event_id=f"{operation_key}:completed",
        type="review.completed" if result.available else "review.unavailable",
        stage_id="text",
        node_id="text.review_chapter",
        chapter_id=chapter_id,
        status="completed" if result.available else "unavailable",
        payload={
            "role": role,
            "required": required,
            "available": result.available,
            "findings": [item.model_dump(mode="json") for item in result.findings],
        },
        payload_ref=operation_key,
    )
    return {"review_operation_refs": [operation_key]}


def evaluate_review_gate(
    executor: StageExecutor,
    state: NarrativeRunState,
) -> dict[str, Any]:
    run_id = state["run_id"]
    chapter_id = state["active_chapter_id"]
    role_specs = {
        str(item["role"]): bool(item["required"])
        for item in state.get("active_review_roles") or []
    }
    results: dict[str, ChapterReviewResult] = {}
    version_id = (state.get("chapter_version_refs") or {})[chapter_id]
    prefix = f"{run_id}:{chapter_id}:review:{version_id}:"
    for operation_key in state.get("review_operation_refs") or []:
        if not operation_key.startswith(prefix):
            continue
        receipt = executor.operations.read(run_id, operation_key)
        role = operation_key.rsplit(":", 1)[-1]
        results[role] = (
            ChapterReviewResult.model_validate(receipt.result)
            if receipt.status == "succeeded"
            else ChapterReviewResult(role=role, available=False)
        )
    unavailable_required = [
        role
        for role, required in role_specs.items()
        if required and (role not in results or not results[role].available)
    ]
    unavailable_optional = [
        role
        for role, required in role_specs.items()
        if not required and (role not in results or not results[role].available)
    ]
    blocking = [
        finding.model_dump(mode="json")
        for result in results.values()
        for finding in result.findings
        if finding.severity == "blocking"
    ]
    return request_chapter_decision(
        executor,
        state,
        reason={
            "required_review_unavailable": unavailable_required,
            "optional_review_unavailable": unavailable_optional,
            "blocking_findings": blocking,
            "reviewed_roles": sorted(results),
        },
    )


def send_reviewers_or_failure(state: NarrativeRunState) -> str | list[Send]:
    if state.get("failure") is not None:
        return "fail_chapter"
    return [
        Send(
            "review_chapter",
            {
                "run_id": state["run_id"],
                "active_stage_id": "text",
                "active_chapter_id": state["active_chapter_id"],
                "active_chapter_number": state["active_chapter_number"],
                "chapter_version_refs": state.get("chapter_version_refs") or {},
                "artifact_refs": state.get("artifact_refs") or {},
                "chapter_attempts": state.get("chapter_attempts") or {},
                "chapter_revision_directions": state.get("chapter_revision_directions") or {},
                "context_manifest_ref": state.get("context_manifest_ref") or "",
                "review_role": item["role"],
                "review_required": item["required"],
            },
        )
        for item in state.get("active_review_roles") or []
    ]


def _signature(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_REVIEWERS",
    "ReviewerSpec",
    "evaluate_review_gate",
    "execute_review",
    "freeze_review_roles",
    "send_reviewers_or_failure",
]
