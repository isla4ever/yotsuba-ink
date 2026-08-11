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
    request = ChapterReviewRequest(
        operation_key=operation_key,
        run_id=run_id,
        chapter_id=chapter_id,
        chapter_version_id=version_id,
        role=role,
        required=required,
        binding=binding,
        context=executor.context_compiler().review(state, role),
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
            response = await executor.provider.review_chapter(request)
            result = ChapterReviewResult.model_validate(response.payload)
            if result.role != role:
                raise ValueError("Reviewer result role does not match its frozen lane")
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
