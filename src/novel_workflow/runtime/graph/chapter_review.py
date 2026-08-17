from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from langgraph.types import Send

from novel_workflow.runtime.graph.chapter_decision import request_chapter_decision
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterReviewRequest,
    ChapterReviewResult,
    ProviderOperationError,
    ReviewFinding,
    compile_provider_input,
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

def deterministic_world_rule_findings(
    *,
    world_rules: Iterable[str],
    content: str,
    subject_ids: Iterable[str],
) -> tuple[ReviewFinding, ...]:
    """Catch explicit temporal rule reversals the model may overlook.

    This is deliberately narrow: only a frozen rule that explicitly promises a
    24-hour future call or a fixed call time is checked, and only direct
    negations in a prose sentence are reported. Literary interpretation remains
    in the reviewer lane.
    """
    rules = "\n".join(str(rule) for rule in world_rules)
    if not content.strip() or not rules.strip():
        return ()
    has_call_rule = any(term in rules for term in ("电话", "来电", "报警"))
    promises_future_call = (
        has_call_rule
        and bool(re.search(r"(?:24小时|二十四小时).{0,12}(?:后|之后)", rules))
    )
    promises_fixed_time = has_call_rule and bool(
        re.search(r"固定(?:的)?(?:时间|时段)", rules)
    )
    if not promises_future_call and not promises_fixed_time:
        return ()

    ids = list(dict.fromkeys(str(value) for value in subject_ids if str(value)))
    for sentence in _sentences(content):
        if promises_future_call and (
            re.search(
                r"(?:不是|并非|并不是|不再是)(?:来自|提前)?(?:24小时|二十四小时)(?:后|之后)?",
                sentence,
            )
            or re.search(
                r"(?:电话|报警|来电)[^。！？!?]{0,30}(?:事情|事件).{0,15}(?:已经发生|发生后|同一?分钟|同时)",
                sentence,
            )
            or re.search(
                r"(?:事情|事件).{0,15}(?:已经发生|发生后|同一?分钟|同时).{0,20}(?:电话|报警|来电)",
                sentence,
            )
        ):
            return (
                ReviewFinding(
                    code="time_rule_conflict",
                    severity="blocking",
                    claim="正文直接否定了冻结的‘电话来自24小时后’世界规则。",
                    evidence=sentence,
                    subject_ids=ids,
                ),
            )
        if promises_fixed_time and re.search(
            r"(?:不是固定|不再固定|时间不对|并非固定)", sentence
        ):
            return (
                ReviewFinding(
                    code="time_rule_conflict",
                    severity="blocking",
                    claim="正文直接否定了冻结的固定来电时间规则。",
                    evidence=sentence,
                    subject_ids=ids,
                ),
            )
    if promises_future_call:
        immediate_conflict = _immediate_future_event_conflict(content)
        if immediate_conflict:
            return (
                ReviewFinding(
                    code="time_rule_conflict",
                    severity="blocking",
                    claim="正文让应在24小时后发生的报警事件在同一时段立即兑现。",
                    evidence=immediate_conflict,
                    subject_ids=ids,
                ),
            )
    return ()


_IMMEDIATE_MARKER = r"(?:马上|立刻|立即|就要|快要|正在)"
_FUTURE_EVENT = r"(?:车祸|事故|意外|火灾|爆炸|坠落|袭击|绑架|死亡|遇害)"
_EVENT_REALIZATION = re.compile(
    r"(?:车祸|事故|意外|火灾|爆炸|坠落|袭击|绑架).{0,16}(?:发生|出现|应验)"
    r"|(?:撞上|撞向|撞击|爆炸|起火|坠落|倒下|被绑架|遇害)"
)
_NEXT_DAY_TRANSITION = re.compile(
    r"(?:第二天|次日|翌日|隔天|二十四小时后|24小时后|第二晚|次日晚)"
)


def _immediate_future_event_conflict(content: str) -> str:
    prediction = re.compile(
        rf"(?:"
        rf"(?:电话|来电|听筒|报警|那头)[^。！？!?]{{0,120}}(?:"
        rf"{_IMMEDIATE_MARKER}[^。！？!?]{{0,50}}{_FUTURE_EVENT}"
        rf"|{_FUTURE_EVENT}[^。！？!?]{{0,50}}{_IMMEDIATE_MARKER})"
        rf"|[“\"][^”\"\n]{{0,120}}(?:"
        rf"{_IMMEDIATE_MARKER}[^”\"\n]{{0,50}}{_FUTURE_EVENT}"
        rf"|{_FUTURE_EVENT}[^”\"\n]{{0,50}}{_IMMEDIATE_MARKER})"
        rf")"
    )
    for match in prediction.finditer(content):
        sentence_end = re.search(r"[。！？!?]", content[match.end() :])
        tail_start = match.end() + (sentence_end.end() if sentence_end else 0)
        tail = content[tail_start:]
        realization = _EVENT_REALIZATION.search(tail)
        if realization is None:
            continue
        transition = _NEXT_DAY_TRANSITION.search(tail)
        if transition is None or realization.start() < transition.start():
            prediction_evidence = match.group(0).strip()[:120]
            realized_start = max(0, realization.start() - 40)
            realized_end = min(len(tail), realization.end() + 40)
            realized_evidence = tail[realized_start:realized_end].strip()
            return f"{prediction_evidence} …… {realized_evidence}"[:240]
    return ""


def _sentences(content: str) -> tuple[str, ...]:
    return tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?])", content)
        if sentence.strip()
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


def hard_review_findings(results: Iterable[ChapterReviewResult]) -> list[dict[str, Any]]:
    """LLM review evidence is advisory, regardless of its self-rated severity."""

    return []


def review_warning_findings(results: Iterable[ChapterReviewResult]) -> list[dict[str, Any]]:
    """Return reviewer evidence that should remain advisory in v1."""

    return [
        finding.model_dump(mode="json")
        for result in results
        for finding in result.findings
    ]


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
    attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
    request = ChapterReviewRequest(
        operation_key=operation_key,
        run_id=run_id,
        chapter_id=chapter_id,
        chapter_version_id=version_id,
        role=role,
        required=required,
        attempt=attempt,
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
    receipt = executor.operations.begin_provider(
        run_id=run_id,
        operation_key=operation_key,
        kind="chapter_review",
        provider_profile_id=binding.provider_profile_id,
        model=binding.model,
        provider_input=compile_provider_input(request),
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
    deterministic_blocking: tuple[ReviewFinding, ...] = ()
    continuity = results.get("continuity")
    if continuity is not None or "continuity" in role_specs:
        material = executor.context_compiler().review(state, "continuity")["material"]
        deterministic_blocking = deterministic_world_rule_findings(
            world_rules=material.get("world_rules") or (),
            content=(material.get("chapter") or {}).get("content") or "",
            subject_ids=(material.get("current_detail_chapter") or {}).get("cast_ids") or (),
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
    blocking = [finding.model_dump(mode="json") for finding in deterministic_blocking]
    warnings = review_warning_findings(results.values())
    return request_chapter_decision(
        executor,
        state,
        reason={
            "required_review_unavailable": unavailable_required,
            "optional_review_unavailable": unavailable_optional,
            "blocking_findings": blocking,
            "warning_findings": warnings,
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


__all__ = [
    "DEFAULT_REVIEWERS",
    "ReviewerSpec",
    "evaluate_review_gate",
    "hard_review_findings",
    "review_warning_findings",
    "execute_review",
    "freeze_review_roles",
    "send_reviewers_or_failure",
]
