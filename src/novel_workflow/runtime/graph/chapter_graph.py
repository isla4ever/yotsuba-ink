from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact, ContextManifest
from novel_workflow.runtime.graph.provider_gateway import ProviderOperationError
from novel_workflow.runtime.graph.chapter_scene_generation import (
    generate_chapter_scenes,
)
from novel_workflow.runtime.graph.chapter_review import (
    DEFAULT_REVIEWERS,
    ReviewerSpec,
    evaluate_review_gate,
    execute_review,
    freeze_review_roles,
    send_reviewers_or_failure,
)
from novel_workflow.runtime.graph.chapter_length import (
    evaluate_book_length_budget,
    evaluate_chapter_length,
)
from novel_workflow.runtime.graph.chapter_decision import request_chapter_decision
from novel_workflow.quality.decision_contract import (
    build_quality_decision,
    contract_blocker,
)
from novel_workflow.runtime.graph.chapter_evidence import (
    extract_evidence,
    request_evidence_recovery,
)
from novel_workflow.runtime.graph.chapter_writeback import (
    await_commit_receipt,
    enqueue_domain_commit,
)
from novel_workflow.runtime.graph.manuscript_review import evaluate_manuscript_gate
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
from novel_workflow.workflows.narrative_scale import (
    count_prose_characters,
    minimum_viable_book_characters,
    soft_book_length_bounds,
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
        attempts.setdefault(chapter.ref, 1)
        return {
            "active_stage_id": "text",
            "active_chapter_number": next_number,
            "active_chapter_id": chapter.ref,
            "context_manifest_ref": "",
            "chapter_gate_action": "generate",
            "chapter_attempts": attempts,
            "pending_evidence_attempt_ref": "",
            "pending_evidence_refs": [],
            "pending_writeback_ref": "",
            "evidence_gate_action": "",
            "stage_status": copy_stage_status(state, "text", "running"),
            "status": "running",
        }

    def prepare_context(state: NarrativeRunState) -> dict[str, Any]:
        run_id = state["run_id"]
        chapter_id = state["active_chapter_id"]
        attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
        definition = executor.runs.definition(run_id)
        binding = definition.provider_bindings.get("text")
        if binding is None:
            raise ProviderOperationError("No frozen Provider binding for text")
        budget = executor.output_budget_planner(state).for_chapter(binding)
        context = executor.context_compiler().chapter(
            state,
            output_tokens=budget.max_tokens,
        )
        manifest = ContextManifest.model_validate(
            context["material"]["chapter_context_manifest"]
        )
        record = executor.context_manifests.write(
            run_id,
            attempt=attempt,
            manifest=manifest,
        )
        return {"context_manifest_ref": record.manifest_id}

    async def generate_prose(state: NarrativeRunState) -> dict[str, Any]:
        run_id = state["run_id"]
        chapter_id = state["active_chapter_id"]
        chapter_number = state["active_chapter_number"]
        detail_chapter = executor.detail(state).chapters[chapter_number - 1]
        if detail_chapter.ref != chapter_id:
            raise ValueError("Active chapter does not match the frozen Detail Artifact")
        attempt = int((state.get("chapter_attempts") or {}).get(chapter_id) or 1)
        definition = executor.runs.definition(run_id)
        binding = definition.provider_bindings.get("text")
        if binding is None:
            raise ProviderOperationError("No frozen Provider binding for text")
        manifest_ref = str(state.get("context_manifest_ref") or "")
        if not manifest_ref:
            raise ValueError("Chapter generation requires a frozen Context Manifest")
        manifest_record = executor.context_manifests.read(run_id, manifest_ref)
        if manifest_record.chapter_id != chapter_id or manifest_record.attempt != attempt:
            raise ValueError("Context Manifest does not match the active chapter attempt")
        planner = executor.output_budget_planner(state)
        budget = planner.for_chapter(binding)
        generated = await generate_chapter_scenes(
            executor,
            state,
            base_manifest=manifest_record.manifest,
            detail_chapter=detail_chapter,
            binding=binding,
            budget=budget,
        )
        artifact = _chapter_artifact(
            chapter_id=chapter_id,
            attempt=attempt,
            content=generated.content,
            title=detail_chapter.title,
        )
        _validate_generated_chapter(
            artifact,
            chapter_id=chapter_id,
            expected_title=detail_chapter.title,
        )
        record = executor.chapters.write(run_id, artifact.model_dump(mode="json"))
        operation_key = generated.operation_keys[-1]
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
            "pending_operation_refs": list(generated.operation_keys),
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
        run_id = state["run_id"]
        detail = executor.detail(state)
        refs = state.get("chapter_version_refs") or {}
        accepted = [
            executor.chapters.read(run_id, chapter.ref, refs[chapter.ref]).artifact
            for chapter in detail.chapters
        ]
        actual_total = sum(count_prose_characters(chapter.content) for chapter in accepted)
        profile = executor.runs.definition(run_id).scale_profile
        soft_minimum, soft_maximum = soft_book_length_bounds(profile)
        viable_minimum = minimum_viable_book_characters(profile)
        if actual_total < viable_minimum:
            raise ValueError(
                "Whole-book prose total is below the minimum viable length of "
                f"{viable_minimum} characters (frozen target {profile.word_target_soft}, "
                f"soft range {soft_minimum}-{soft_maximum}): {actual_total}"
            )
        if not soft_minimum <= actual_total <= soft_maximum:
            executor.events.append(
                run_id,
                event_id=f"{run_id}:text:book-length-warning",
                type="quality.warning",
                stage_id="text",
                node_id="text.finish_chapters",
                chapter_id="",
                status="warning",
                payload={
                    "code": "book_length_soft_band",
                    "actual_characters": actual_total,
                    "target_characters": profile.word_target_soft,
                    "soft_bounds": [soft_minimum, soft_maximum],
                    "minimum_viable_characters": viable_minimum,
                },
            )
        return {
            "stage_status": copy_stage_status(state, "text", "running"),
            "status": "running",
            "active_chapter_id": "",
            "context_manifest_ref": "",
            "manuscript_gate_action": "",
        }

    def complete_text_stage(state: NarrativeRunState) -> dict[str, Any]:
        return {
            "stage_status": copy_stage_status(state, "text", "completed"),
            "status": "running",
        }

    def fail_chapter(state: NarrativeRunState) -> dict[str, Any]:
        return emit_terminal_failure(executor, state, "text")

    def check_book_budget(state: NarrativeRunState) -> dict[str, Any]:
        result = evaluate_book_length_budget(executor, state)
        blocker_payload = result.get("book_budget_blocker") or {}
        if not blocker_payload:
            return {"chapter_gate_action": "review"}
        labels = {
            subject.id: subject.name
            for subject in executor.character_bible(state).subjects
        }
        blocker = contract_blocker(blocker_payload, subject_labels=labels)
        quality_decision = build_quality_decision(contract_blockers=[blocker])
        return request_chapter_decision(
            executor,
            state,
            quality_decision=quality_decision,
            review_status={"book_budget": blocker_payload},
        )

    def check_chapter_length(state: NarrativeRunState) -> dict[str, Any]:
        result = evaluate_chapter_length(executor, state)
        blocker_payload = result.get("chapter_length_blocker") or {}
        if not blocker_payload:
            return {"chapter_gate_action": "review"}
        labels = {
            subject.id: subject.name
            for subject in executor.character_bible(state).subjects
        }
        blocker = contract_blocker(blocker_payload, subject_labels=labels)
        quality_decision = build_quality_decision(contract_blockers=[blocker])
        return request_chapter_decision(
            executor,
            state,
            quality_decision=quality_decision,
            review_status={"chapter_length": blocker_payload},
        )

    builder.add_node("prepare_chapter", guarded_node(executor, "text.prepare_chapter", "text", prepare_chapter))
    builder.add_node("prepare_context", guarded_node(executor, "text.prepare_context", "text", prepare_context))
    builder.add_node("generate_prose", guarded_node(executor, "text.generate_prose", "text", generate_prose))
    builder.add_node(
        "check_length_contract",
        guarded_node(
            executor,
            "text.check_length_contract",
            "text",
            check_chapter_length,
        ),
    )
    builder.add_node(
        "check_book_budget",
        guarded_node(
            executor,
            "text.check_book_budget",
            "text",
            check_book_budget,
        ),
    )
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
    builder.add_node("evidence_recovery", guarded_node(executor, "text.evidence_recovery", "text", lambda state: request_evidence_recovery(executor, state)))
    builder.add_node("enqueue_domain_commit", guarded_node(executor, "text.enqueue_domain_commit", "text", lambda state: enqueue_domain_commit(executor, state)))
    builder.add_node("await_commit_receipt", guarded_node(executor, "text.await_commit_receipt", "text", lambda state: await_commit_receipt(executor, state)))
    builder.add_node("finish_chapters", guarded_node(executor, "text.finish_chapters", "text", finish_chapters))
    builder.add_node(
        "evaluate_manuscript",
        guarded_node(
            executor,
            "text.evaluate_manuscript",
            "text",
            lambda state: evaluate_manuscript_gate(executor, state),
        ),
    )
    builder.add_node(
        "complete_text_stage",
        guarded_node(
            executor,
            "text.complete_stage",
            "text",
            complete_text_stage,
        ),
    )
    builder.add_node("fail_chapter", fail_chapter)
    builder.add_edge(START, "prepare_chapter")
    builder.add_conditional_edges(
        "prepare_chapter",
        lambda state: (
            "failure" if state.get("failure") is not None else state.get("chapter_gate_action", "finish")
        ),
        {"generate": "prepare_context", "finish": "finish_chapters", "failure": "fail_chapter"},
    )
    builder.add_conditional_edges("prepare_context", lambda state: failure_route(state, "generate_prose"), {"failure": "fail_chapter", "generate_prose": "generate_prose"})
    builder.add_conditional_edges("generate_prose", lambda state: failure_route(state, "check_length_contract"), {"failure": "fail_chapter", "check_length_contract": "check_length_contract"})
    builder.add_conditional_edges(
        "check_length_contract",
        lambda state: (
            "failure"
            if state.get("failure") is not None
            else str(state.get("chapter_gate_action") or "review")
        ),
        {
            "review": "check_book_budget",
            "regenerate": "prepare_context",
            "cancel": END,
            "failure": "fail_chapter",
        },
    )
    builder.add_conditional_edges(
        "check_book_budget",
        lambda state: (
            "failure"
            if state.get("failure") is not None
            else str(state.get("chapter_gate_action") or "review")
        ),
        {
            "review": "plan_review_roles",
            "regenerate": "prepare_context",
            "cancel": END,
            "failure": "fail_chapter",
        },
    )
    builder.add_conditional_edges("plan_review_roles", send_reviewers_or_failure)
    builder.add_edge("review_chapter", "evaluate_review_gate")
    builder.add_conditional_edges(
        "evaluate_review_gate",
        lambda state: (
            "failure" if state.get("failure") is not None else state.get("chapter_gate_action", "cancel")
        ),
        {
            "accept": "commit_chapter",
            "regenerate": "prepare_context",
            "cancel": END,
            "failure": "fail_chapter",
        },
    )
    builder.add_conditional_edges("commit_chapter", lambda state: failure_route(state, "extract_evidence"), {"failure": "fail_chapter", "extract_evidence": "extract_evidence"})
    builder.add_conditional_edges(
        "extract_evidence",
        lambda state: (
            "failure"
            if state.get("failure") is not None
            else str(state.get("evidence_gate_action") or "needs_action")
        ),
        {
            "failure": "fail_chapter",
            "succeeded": "enqueue_domain_commit",
            "needs_action": "evidence_recovery",
        },
    )
    builder.add_conditional_edges(
        "evidence_recovery",
        lambda state: (
            "failure"
            if state.get("failure") is not None
            else str(state.get("evidence_gate_action") or "cancel")
        ),
        {
            "failure": "fail_chapter",
            "retry": "extract_evidence",
            "cancel": END,
        },
    )
    builder.add_conditional_edges("enqueue_domain_commit", lambda state: failure_route(state, "await_commit_receipt"), {"failure": "fail_chapter", "await_commit_receipt": "await_commit_receipt"})
    builder.add_conditional_edges("await_commit_receipt", lambda state: failure_route(state, "prepare_chapter"), {"failure": "fail_chapter", "prepare_chapter": "prepare_chapter"})
    builder.add_conditional_edges(
        "finish_chapters",
        lambda state: failure_route(state, "evaluate_manuscript"),
        {"failure": "fail_chapter", "evaluate_manuscript": "evaluate_manuscript"},
    )
    builder.add_conditional_edges(
        "evaluate_manuscript",
        lambda state: (
            "failure"
            if state.get("failure") is not None
            else str(state.get("manuscript_gate_action") or "cancel")
        ),
        {
            "accept": "complete_text_stage",
            "cancel": END,
            "failure": "fail_chapter",
        },
    )
    builder.add_edge("complete_text_stage", END)
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
    expected_title: str,
) -> None:
    if artifact.chapter_id != chapter_id or artifact.author_status != "candidate":
        raise ValueError("Chapter Provider output must target the frozen chapter as a candidate")
    if artifact.title != expected_title:
        raise ValueError("Chapter title must be inherited from the frozen Detail Artifact")


def _chapter_artifact(
    *,
    chapter_id: str,
    attempt: int,
    content: str,
    title: str,
) -> ChapterArtifact:
    return ChapterArtifact(
        chapter_id=chapter_id,
        version_id=f"{chapter_id}-v{attempt}",
        title=title,
        content=content,
        author_status="candidate",
    )


__all__ = ["DEFAULT_REVIEWERS", "ReviewerSpec", "build_chapter_graph"]
