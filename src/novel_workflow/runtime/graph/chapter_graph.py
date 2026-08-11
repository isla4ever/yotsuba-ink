from __future__ import annotations

import hashlib
import json
from typing import Any

from langgraph.graph import END, START, StateGraph

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterDraftResult,
    ChapterGenerationRequest,
    ProviderOperationError,
)
from novel_workflow.runtime.graph.chapter_review import (
    DEFAULT_REVIEWERS,
    ReviewerSpec,
    evaluate_review_gate,
    execute_review,
    freeze_review_roles,
    send_reviewers_or_failure,
)
from novel_workflow.runtime.graph.chapter_writeback import (
    await_commit_receipt,
    enqueue_domain_commit,
    extract_evidence,
)
from novel_workflow.runtime.graph.stage_executor import StageExecutor
from novel_workflow.runtime.graph.failure import (
    emit_terminal_failure,
    failure_route,
    guarded_node,
)
from novel_workflow.runtime.graph.state import (
    NarrativeRunState,
    copy_stage_status,
)


def build_chapter_graph(
    executor: StageExecutor,
    *,
    reviewers: tuple[ReviewerSpec, ...] = DEFAULT_REVIEWERS,
):
    builder = StateGraph(NarrativeRunState)

    def prepare_chapter(state: NarrativeRunState) -> dict[str, Any]:
        detail = executor.detail(state)
        next_number = int(state.get("active_chapter_number") or 0) + 1
        if next_number > len(detail.chapters):
            return {"chapter_gate_action": "finish"}
        chapter = detail.chapters[next_number - 1]
        attempts = dict(state.get("chapter_attempts") or {})
        attempts.setdefault(chapter.id, 1)
        return {
            "active_stage_id": "text",
            "active_chapter_number": next_number,
            "active_chapter_id": chapter.id,
            "chapter_gate_action": "generate",
            "chapter_attempts": attempts,
            "stage_status": copy_stage_status(state, "text", "running"),
            "status": "running",
        }

    async def generate_prose(state: NarrativeRunState) -> dict[str, Any]:
        run_id = state["run_id"]
        chapter_id = state["active_chapter_id"]
        chapter_number = state["active_chapter_number"]
        attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
        operation_key = f"{run_id}:{chapter_id}:generate:{attempt}"
        definition = executor.runs.definition(run_id)
        binding = definition.provider_bindings.get("text")
        if binding is None:
            raise ProviderOperationError("No frozen Provider binding for text")
        revision_direction = str(
            (state.get("chapter_revision_directions") or {}).get(chapter_id) or ""
        ).strip()
        if attempt > 1 and not revision_direction:
            raise ValueError("A repeated chapter generation requires an explicit revision direction")
        request = ChapterGenerationRequest(
            operation_key=operation_key,
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            binding=binding,
            context=executor.context_compiler().chapter(state),
        )
        receipt = executor.operations.begin(
            run_id=run_id,
            operation_key=operation_key,
            kind="chapter_generation",
            request_signature=_signature(request.model_dump(mode="json")),
            provider_profile_id=binding.provider_profile_id,
            model=binding.model,
        )
        if receipt.status == "failed":
            raise ProviderOperationError.for_operation(
                operation_key, f"Provider operation already failed: {operation_key}"
            )
        if receipt.status == "succeeded":
            payload = receipt.result
            draft = ChapterDraftResult.model_validate(payload)
            artifact = _chapter_artifact(draft, chapter_id=chapter_id, attempt=attempt)
            _validate_generated_chapter(
                artifact,
                chapter_id=chapter_id,
            )
        else:
            response = None
            try:
                response = await executor.provider.generate_chapter(request)
                payload = response.payload
                draft = ChapterDraftResult.model_validate(payload)
                artifact = _chapter_artifact(draft, chapter_id=chapter_id, attempt=attempt)
                _validate_generated_chapter(
                    artifact,
                    chapter_id=chapter_id,
                )
            except Exception as exc:
                executor.operations.fail(
                    run_id,
                    operation_key,
                    {"type": type(exc).__name__, "message": str(exc)},
                    usage=(
                        response.usage
                        if response is not None
                        else getattr(exc, "usage", {})
                    ),
                    diagnostic=(
                        response.diagnostic
                        if response is not None
                        else getattr(exc, "diagnostic", {})
                    ),
                )
                raise ProviderOperationError.for_operation(operation_key, exc) from exc
            executor.operations.succeed(
                run_id,
                operation_key,
                payload,
                usage=response.usage,
                diagnostic=response.diagnostic,
            )
        record = executor.chapters.write(run_id, artifact.model_dump(mode="json"))
        executor.events.append(
            run_id,
            event_id=f"{operation_key}:candidate",
            type="artifact.candidate_ready",
            stage_id="text",
            node_id="text.generate_prose",
            chapter_id=chapter_id,
            payload_ref=record.version_id,
        )
        return {
            "chapter_version_refs": _copy_chapter_ref(state, chapter_id, record.version_id),
            "pending_operation_refs": [operation_key],
        }

    def commit_chapter(state: NarrativeRunState) -> dict[str, Any]:
        run_id = state["run_id"]
        chapter_id = state["active_chapter_id"]
        candidate_version = (state.get("chapter_version_refs") or {})[chapter_id]
        candidate = executor.chapters.read(run_id, chapter_id, candidate_version).artifact
        accepted = candidate.model_copy(
            update={
                "version_id": f"{candidate.version_id}-accepted",
                "author_status": "accepted",
            }
        )
        record = executor.chapters.write(run_id, accepted.model_dump(mode="json"))
        executor.events.append(
            run_id,
            event_id=f"{run_id}:{chapter_id}:{record.version_id}:committed",
            type="artifact.committed",
            stage_id="text",
            node_id="text.commit_chapter",
            chapter_id=chapter_id,
            payload_ref=record.version_id,
        )
        return {
            "chapter_version_refs": _copy_chapter_ref(state, chapter_id, record.version_id),
            "domain_revision": int(state.get("domain_revision") or 0) + 1,
            "chapter_gate_action": "next",
        }

    def finish_chapters(state: NarrativeRunState) -> dict[str, Any]:
        return {
            "stage_status": copy_stage_status(state, "text", "completed"),
            "status": "running",
            "active_chapter_id": "",
        }

    def fail_chapter(state: NarrativeRunState) -> dict[str, Any]:
        return emit_terminal_failure(executor, state, "text")

    builder.add_node("prepare_chapter", guarded_node(executor, "text.prepare_chapter", "text", prepare_chapter))
    builder.add_node("generate_prose", guarded_node(executor, "text.generate_prose", "text", generate_prose))
    builder.add_node(
        "plan_review_roles",
        guarded_node(
            executor,
            "text.plan_review_roles",
            "text",
            lambda state: freeze_review_roles(
                reviewers,
                str(state.get("quality_mode") or "balanced"),
            ),
        ),
    )
    builder.add_node("review_chapter", guarded_node(executor, "text.review_chapter", "text", lambda state: execute_review(executor, state)))
    builder.add_node("evaluate_review_gate", guarded_node(executor, "text.evaluate_review_gate", "text", lambda state: evaluate_review_gate(executor, state)))
    builder.add_node("commit_chapter", guarded_node(executor, "text.commit_chapter", "text", commit_chapter))
    builder.add_node("extract_evidence", guarded_node(executor, "text.extract_evidence", "text", lambda state: extract_evidence(executor, state)))
    builder.add_node("enqueue_domain_commit", guarded_node(executor, "text.enqueue_domain_commit", "text", lambda state: enqueue_domain_commit(executor, state)))
    builder.add_node("await_commit_receipt", guarded_node(executor, "text.await_commit_receipt", "text", lambda state: await_commit_receipt(executor, state)))
    builder.add_node("finish_chapters", guarded_node(executor, "text.finish_chapters", "text", finish_chapters))
    builder.add_node("fail_chapter", fail_chapter)
    builder.add_edge(START, "prepare_chapter")
    builder.add_conditional_edges(
        "prepare_chapter",
        lambda state: (
            "failure" if state.get("failure") is not None else state.get("chapter_gate_action", "finish")
        ),
        {"generate": "generate_prose", "finish": "finish_chapters", "failure": "fail_chapter"},
    )
    builder.add_conditional_edges("generate_prose", lambda state: failure_route(state, "plan_review_roles"), {"failure": "fail_chapter", "plan_review_roles": "plan_review_roles"})
    builder.add_conditional_edges("plan_review_roles", send_reviewers_or_failure)
    builder.add_edge("review_chapter", "evaluate_review_gate")
    builder.add_conditional_edges(
        "evaluate_review_gate",
        lambda state: (
            "failure" if state.get("failure") is not None else state.get("chapter_gate_action", "cancel")
        ),
        {
            "accept": "commit_chapter",
            "regenerate": "generate_prose",
            "cancel": END,
            "failure": "fail_chapter",
        },
    )
    builder.add_conditional_edges("commit_chapter", lambda state: failure_route(state, "extract_evidence"), {"failure": "fail_chapter", "extract_evidence": "extract_evidence"})
    builder.add_conditional_edges("extract_evidence", lambda state: failure_route(state, "enqueue_domain_commit"), {"failure": "fail_chapter", "enqueue_domain_commit": "enqueue_domain_commit"})
    builder.add_conditional_edges("enqueue_domain_commit", lambda state: failure_route(state, "await_commit_receipt"), {"failure": "fail_chapter", "await_commit_receipt": "await_commit_receipt"})
    builder.add_conditional_edges("await_commit_receipt", lambda state: failure_route(state, "prepare_chapter"), {"failure": "fail_chapter", "prepare_chapter": "prepare_chapter"})
    builder.add_conditional_edges("finish_chapters", lambda state: failure_route(state, "done"), {"failure": "fail_chapter", "done": END})
    builder.add_edge("fail_chapter", END)
    return builder.compile(name="yotsuba_chapter_loop")
def _copy_chapter_ref(
    state: NarrativeRunState,
    chapter_id: str,
    version_id: str,
) -> dict[str, str]:
    values = dict(state.get("chapter_version_refs") or {})
    values[chapter_id] = version_id
    return values


def _validate_generated_chapter(
    artifact: ChapterArtifact,
    *,
    chapter_id: str,
) -> None:
    if artifact.chapter_id != chapter_id or artifact.author_status != "candidate":
        raise ValueError("Chapter Provider output must target the frozen chapter as a candidate")


def _chapter_artifact(
    draft: ChapterDraftResult,
    *,
    chapter_id: str,
    attempt: int,
) -> ChapterArtifact:
    return ChapterArtifact(
        chapter_id=draft.chapter_id,
        version_id=f"{chapter_id}-v{attempt}",
        title=draft.title,
        content=draft.content,
        author_status=draft.author_status,
    )


def _signature(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
__all__ = ["DEFAULT_REVIEWERS", "ReviewerSpec", "build_chapter_graph"]
