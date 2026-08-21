from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from novel_workflow.runtime.graph.chapter_scene_facts import (
    PersistentFactViolation,
    QuantifiedFactRepairWindow,
    apply_quantified_fact_repair,
    introduced_persistent_fact_violations,
    introduced_quantified_fact_tokens,
    quantified_fact_repair_window,
)
from novel_workflow.runtime.graph.chapter_scene_length import SceneLengthContract
from novel_workflow.runtime.graph.context_compiler import _context_snippet, _manifest_hash
from novel_workflow.runtime.graph.provider_gateway import compile_provider_input
from novel_workflow.runtime.graph.provider_requests import (
    ChapterSceneGenerationRequest,
    ProviderOperationError,
)
from novel_workflow.runtime.graph.stage_executor import _is_transient_network_error
from novel_workflow.workflows.narrative_scale import count_prose_characters

if TYPE_CHECKING:
    from novel_workflow.runtime.graph.stage_executor import StageExecutor


_SCENE_NETWORK_ATTEMPTS = 3
_SCENE_REPAIR_OUTPUT_TOKEN_CAP = 900


@dataclass(frozen=True, slots=True)
class SceneContractExecutionResult:
    content: str
    operation_keys: tuple[str, ...]
    accepted_operation_key: str


class SceneProseContractError(ValueError):
    def __init__(self, message: str, *, operation_key: str) -> None:
        super().__init__(message)
        self.operation_key = operation_key


async def execute_scene_contract(
    executor: StageExecutor,
    *,
    request: ChapterSceneGenerationRequest,
    source_manifest: ContextManifest,
    contract: SceneLengthContract,
) -> SceneContractExecutionResult:
    content, receipt_status = await _scene_provider_content(
        executor,
        request,
        kind="chapter_scene_generation",
    )
    fact_drift = introduced_quantified_fact_tokens(content, source_manifest)
    persistent_drift = introduced_persistent_fact_violations(content, source_manifest)
    if receipt_status == "succeeded" and (fact_drift or persistent_drift):
        raise SceneProseContractError(
            "Accepted scene receipt violates its frozen fact contract",
            operation_key=request.operation_key,
        )
    if receipt_status == "contract_rejected":
        fact_drift = _receipt_fact_drift(
            executor,
            request.run_id,
            request.operation_key,
        )
        persistent_drift = _receipt_persistent_fact_drift(
            executor,
            request.run_id,
            request.operation_key,
        )
    elif receipt_status == "provider_returned":
        _finish_scene_contract(
            executor,
            run_id=request.run_id,
            operation_key=request.operation_key,
            content=content,
            contract=contract,
            fact_drift=fact_drift,
            persistent_drift=persistent_drift,
        )
    if persistent_drift:
        raise SceneProseContractError(
            "Scene introduced durable facts absent from frozen context: "
            + ", ".join(item.code for item in persistent_drift),
            operation_key=request.operation_key,
        )
    if not fact_drift:
        return SceneContractExecutionResult(
            content=content.strip(),
            operation_keys=(request.operation_key,),
            accepted_operation_key=request.operation_key,
        )
    return await _repair_scene_fact_drift(
        executor,
        request=request,
        source_content=content,
        source_manifest=source_manifest,
        rejected_fact_tokens=fact_drift,
        contract=contract,
    )


def build_scene_fact_repair_manifest(
    source: ContextManifest,
    *,
    window: QuantifiedFactRepairWindow,
    output_tokens: int,
) -> ContextManifest:
    retained_refs = {
        "detail.chapter",
        "cast.subjects",
        "volume.contract",
        "brief.world_rules",
        "scene.execution",
        "brief.voice",
        "previous.handoff",
        "previous.ending_excerpt",
        "previous.staged_beats",
        "story.current_state",
        "continuity.recent_window",
        "current_chapter.previous_scene",
    }
    snippets = [
        snippet.model_dump(mode="json")
        for snippet in source.snippets
        if snippet.ref in retained_refs
    ]
    snippets.append(
        _context_snippet(
            "revision.local_segment",
            "masked_contract_repair_window",
            {
                "scope": "single_bounded_scene_segment",
                "left_context": window.left_context,
                "masked_rejected_segment": window.masked_segment,
                "right_context": window.right_context,
                "source_characters": window.source_characters,
                "instruction": (
                    "Replace only the masked segment. Preserve its local dramatic action "
                    "and join naturally to both boundaries without adding any ordinal, "
                    "numeric, dated, counted, ranked, percentage, or identifier fact."
                ),
            },
        )
    )
    required = [
        "detail.chapter",
        "cast.subjects",
        "volume.contract",
        "brief.world_rules",
        "scene.execution",
        "revision.local_segment",
    ]
    available = {str(snippet["ref"]) for snippet in snippets}
    missing = [ref for ref in required if ref not in available]
    if missing:
        raise ValueError(f"Scene fact repair is missing frozen inputs: {missing}")
    optional = [
        ref
        for ref in (
            "brief.voice",
            "previous.handoff",
            "previous.ending_excerpt",
            "previous.staged_beats",
            "story.current_state",
            "continuity.recent_window",
            "current_chapter.previous_scene",
        )
        if ref in available
    ]
    body: dict[str, Any] = {
        "task": source.task,
        "required": required,
        "optional": optional,
        "forbidden": [
            "full_canon",
            "full_wiki",
            "unrelated_subjects",
            "full_previous_chapter",
            "full_rejected_scene",
        ],
        "snippets": snippets,
        "budget": {
            "input_chars": sum(len(item["text"]) for item in snippets),
            "output_tokens": output_tokens,
        },
    }
    body["manifest_hash"] = _manifest_hash(body)
    return ContextManifest.model_validate(body)


async def _repair_scene_fact_drift(
    executor: StageExecutor,
    *,
    request: ChapterSceneGenerationRequest,
    source_content: str,
    source_manifest: ContextManifest,
    rejected_fact_tokens: tuple[str, ...],
    contract: SceneLengthContract,
) -> SceneContractExecutionResult:
    try:
        window = quantified_fact_repair_window(source_content, rejected_fact_tokens)
    except ValueError as exc:
        raise SceneProseContractError(
            str(exc),
            operation_key=request.operation_key,
        ) from exc
    repair_binding = request.binding.model_copy(
        update={
            "max_tokens": min(
                request.binding.max_tokens,
                _SCENE_REPAIR_OUTPUT_TOKEN_CAP,
                max(240, round(window.source_characters * 1.5)),
            )
        }
    )
    repair_manifest = build_scene_fact_repair_manifest(
        source_manifest,
        window=window,
        output_tokens=repair_binding.max_tokens,
    )
    operation_key = scene_operation_key(
        request.run_id,
        request.chapter_id,
        chapter_attempt=request.chapter_attempt,
        scene_index=request.scene_index,
        scene_attempt=2,
    )
    repair_request = request.model_copy(
        update={
            "operation_key": operation_key,
            "scene_attempt": 2,
            "mode": "fact_repair",
            "binding": repair_binding,
            "context": {
                "target": "text.scene",
                "sources": {},
                "material": {
                    "chapter_context_manifest": repair_manifest.model_dump(mode="json")
                },
                "output_budget": {"max_tokens": repair_binding.max_tokens},
            },
        }
    )
    replacement, receipt_status = await _scene_provider_content(
        executor,
        repair_request,
        kind="chapter_scene_fact_repair",
    )
    if receipt_status == "succeeded":
        accepted = read_scene_receipt(
            executor.operations.read(request.run_id, operation_key).result
        )
        if (
            introduced_quantified_fact_tokens(accepted, source_manifest)
            or introduced_persistent_fact_violations(accepted, source_manifest)
        ):
            raise SceneProseContractError(
                "Accepted scene repair receipt violates its frozen fact contract",
                operation_key=operation_key,
            )
        return SceneContractExecutionResult(
            content=accepted,
            operation_keys=(request.operation_key, operation_key),
            accepted_operation_key=operation_key,
        )
    if receipt_status == "contract_rejected":
        raise SceneProseContractError(
            "The single bounded scene fact repair was contract-rejected",
            operation_key=operation_key,
        )
    repaired = apply_quantified_fact_repair(source_content, window, replacement)
    remaining = introduced_quantified_fact_tokens(repaired, source_manifest)
    persistent_remaining = introduced_persistent_fact_violations(
        repaired,
        source_manifest,
    )
    if remaining or persistent_remaining:
        no_progress = set(rejected_fact_tokens).issubset(set(remaining))
        executor.operations.reject_provider_contract(
            request.run_id,
            operation_key,
            {
                "type": "SceneProseContractError",
                "message": (
                    "Scene fact repair made no progress"
                    if no_progress
                    else "Scene fact repair introduced or retained quantified facts"
                ),
            },
            diagnostic={
                "repair_scope_characters": window.source_characters,
                "introduced_quantified_facts": list(remaining),
                "introduced_persistent_facts": [
                    item.as_dict() for item in persistent_remaining
                ],
                "no_progress": no_progress,
            },
        )
        raise SceneProseContractError(
            (
                "The bounded repair introduced a durable fact absent from frozen context"
                if persistent_remaining
                else
                "The same quantified fact violation survived the bounded repair"
                if no_progress
                else "The bounded repair still violates the quantified fact contract"
            ),
            operation_key=operation_key,
        )
    _finish_scene_contract(
        executor,
        run_id=request.run_id,
        operation_key=operation_key,
        content=replacement,
        accepted_content=repaired,
        contract=contract,
        fact_drift=(),
        persistent_drift=(),
    )
    return SceneContractExecutionResult(
        content=repaired,
        operation_keys=(request.operation_key, operation_key),
        accepted_operation_key=operation_key,
    )


async def _scene_provider_content(
    executor: StageExecutor,
    request: ChapterSceneGenerationRequest,
    *,
    kind: str,
) -> tuple[str, str]:
    receipt = executor.operations.begin_provider(
        run_id=request.run_id,
        operation_key=request.operation_key,
        kind=kind,
        provider_profile_id=request.binding.provider_profile_id,
        model=request.binding.model,
        provider_input=compile_provider_input(request),
    )
    if receipt.status == "failed":
        raise ProviderOperationError.for_operation(
            request.operation_key,
            f"Provider operation already failed: {request.operation_key}",
        )
    if receipt.status == "succeeded":
        return read_scene_receipt(receipt.result), receipt.status
    if receipt.status in {"provider_returned", "contract_rejected"}:
        return read_scene_receipt(receipt.provider_result), receipt.status
    response = None
    try:
        response = await _generate_scene_with_network_retry(executor, request)
        content = response.content.strip()
        if not content:
            raise ValueError("Chapter scene Provider returned empty prose")
    except Exception as exc:
        executor.operations.fail(
            request.run_id,
            request.operation_key,
            {"type": type(exc).__name__, "message": str(exc)},
            usage=response.usage if response is not None else getattr(exc, "usage", {}),
            diagnostic=(
                response.diagnostic
                if response is not None
                else getattr(exc, "diagnostic", {})
            ),
        )
        raise ProviderOperationError.for_operation(request.operation_key, exc) from exc
    executor.operations.record_provider_return(
        request.run_id,
        request.operation_key,
        {"content": content},
        usage=response.usage,
        diagnostic=response.diagnostic,
    )
    return content, "provider_returned"


def _finish_scene_contract(
    executor: StageExecutor,
    *,
    run_id: str,
    operation_key: str,
    content: str,
    contract: SceneLengthContract,
    fact_drift: tuple[str, ...],
    persistent_drift: tuple[PersistentFactViolation, ...],
    accepted_content: str = "",
) -> None:
    diagnostic = {
        "measured_non_whitespace_characters": count_prose_characters(
            accepted_content or content
        ),
        "scene_length_bounds": [contract.min_characters, contract.max_characters],
        "introduced_quantified_facts": list(fact_drift),
        "introduced_persistent_facts": [
            item.as_dict() for item in persistent_drift
        ],
    }
    if fact_drift or persistent_drift:
        executor.operations.reject_provider_contract(
            run_id,
            operation_key,
            {
                "type": "SceneProseContractError",
                "message": "Scene introduced facts absent from frozen context",
            },
            diagnostic=diagnostic,
        )
        return
    executor.operations.accept_provider_result(
        run_id,
        operation_key,
        {"content": accepted_content or content},
        diagnostic=diagnostic,
    )


def scene_operation_key(
    run_id: str,
    chapter_id: str,
    *,
    chapter_attempt: int,
    scene_index: int,
    scene_attempt: int,
) -> str:
    return (
        f"{run_id}:{chapter_id}:scene-{scene_index}:"
        f"generate:{chapter_attempt}.{scene_attempt}"
    )


async def _generate_scene_with_network_retry(
    executor: StageExecutor,
    request: ChapterSceneGenerationRequest,
) -> Any:
    for round_index in range(_SCENE_NETWORK_ATTEMPTS):
        try:
            return await executor.provider.generate_chapter_scene(request)
        except Exception as exc:
            if (
                round_index >= _SCENE_NETWORK_ATTEMPTS - 1
                or not _is_transient_network_error(exc)
            ):
                raise
            await asyncio.sleep(2 * (round_index + 1))
    raise RuntimeError("unreachable")


def read_scene_receipt(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Chapter scene receipt must be an object")
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Chapter scene receipt must contain non-empty text")
    return content.strip()


def _receipt_fact_drift(
    executor: StageExecutor,
    run_id: str,
    operation_key: str,
) -> tuple[str, ...]:
    receipt = executor.operations.read(run_id, operation_key)
    return tuple(
        str(token)
        for token in receipt.diagnostic.get("introduced_quantified_facts") or []
        if str(token)
    )


def _receipt_persistent_fact_drift(
    executor: StageExecutor,
    run_id: str,
    operation_key: str,
) -> tuple[PersistentFactViolation, ...]:
    receipt = executor.operations.read(run_id, operation_key)
    return tuple(
        PersistentFactViolation(
            code=str(item.get("code") or "persistent_fact_drift"),
            category=str(item.get("category") or "persistent"),
            evidence=str(item.get("evidence") or ""),
        )
        for item in receipt.diagnostic.get("introduced_persistent_facts") or []
        if isinstance(item, dict) and str(item.get("evidence") or "").strip()
    )


__all__ = [
    "SceneContractExecutionResult",
    "SceneProseContractError",
    "build_scene_fact_repair_manifest",
    "execute_scene_contract",
    "read_scene_receipt",
    "scene_operation_key",
]
