from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.orchestration.chapter_artifact import (
    chapter_at,
    complete_chapter_commit,
    drafting_chapter,
    initialize_chapter_progress,
    normalize_chapter_artifact,
    prepare_chapter_commit,
    upsert_chapter,
    upsert_context_packet,
)
from novel_workflow.orchestration.chapter_commit import commit_chapter_effects
from novel_workflow.orchestration.chapter_generation import generate_chapter_candidates
from novel_workflow.orchestration.chapter_pipeline_events import canon_commit_event, chapter_pipeline_step_event
from novel_workflow.orchestration.chapter_final_artifact import mark_chapter_artifact_committed
from novel_workflow.orchestration.control import pause_if_requested
from novel_workflow.orchestration.helpers import (
    chapter_count,
    chapter_deltas,
    effective_variant_policy,
    quality_event,
)
from novel_workflow.orchestration.model_review import chapter_model_reviewer, stored_model_review
from novel_workflow.orchestration.quality import quality_loop_for_result
from novel_workflow.orchestration.recovery import mark_stable_checkpoint, register_failure
from novel_workflow.output_contracts import validate_stage_artifact
from novel_workflow.workflows.schemas import ChapterContextPacket


async def run_chapter_text_node(
    runner: Any,
    node: Any,
    state: Any,
    workflow: Any,
    run_id: str,
    index: int,
    total: int,
) -> AsyncIterator[dict[str, Any]]:
    del index, total
    output_key = node.output_key or node.id
    target = chapter_count(node, state)
    artifact = normalize_chapter_artifact(state.artifacts.get(output_key), target)
    initialize_chapter_progress(state, node.id, target, artifact)
    state.artifacts[output_key] = artifact
    state.current_phase = "writing"

    phase_event = _event("phase_changed", run_id, node, phase="writing")
    progress_event = _progress_event(run_id, node, state)
    for event in (phase_event, progress_event):
        _persist_event(runner, run_id, state, event)
        yield event

    policy = effective_variant_policy(node, workflow, state)
    candidate_count = policy.candidate_count if policy.enabled else 1
    model_reviewer = chapter_model_reviewer(runner, node, state, workflow, run_id)
    for chapter_index in range(1, target + 1):
        chapter_name = f"第{chapter_index}章"
        existing = chapter_at(artifact, chapter_index)
        if existing and existing.get("status") == "completed":
            continue

        async for event in pause_if_requested(runner, run_id, state, node_id=node.id, chapter=chapter_name):
            yield event

        context_packet = _context_packet(runner, state, existing, chapter_index, target)
        upsert_context_packet(state, context_packet)
        if not existing:
            located = chapter_pipeline_step_event(
                run_id, node, chapter_name, 1, index=chapter_index, total=target
            )
            _persist_event(runner, run_id, state, located)
            yield located
            context_event = _event(
                "chapter_context_built",
                run_id,
                node,
                chapter=chapter_name,
                context_packet=context_packet.model_dump(),
            )
            _persist_event(runner, run_id, state, context_event)
            yield context_event
            context_step = chapter_pipeline_step_event(
                run_id, node, chapter_name, 2, context_packet=context_packet.model_dump()
            )
            _persist_event(runner, run_id, state, context_step)
            yield context_step

        prompt_text = runner.stages.prompt_builder.build(node, state)
        if existing and existing.get("status") == "committing":
            async for event in _finish_commit(
                runner,
                node,
                state,
                artifact,
                existing,
                run_id,
                chapter_index,
                chapter_name,
                prompt_text,
                candidate_count,
                workflow.quality_mode != "deep",
            ):
                yield event
            continue

        if not existing:
            script_step = chapter_pipeline_step_event(
                run_id, node, chapter_name, 3, context_kind=context_packet.chapter_kind
            )
            _persist_event(runner, run_id, state, script_step)
            yield script_step
            progress = next(
                item for item in state.chapter_progress
                if item.node_id == node.id and item.chapter == chapter_name
            )
            progress.status = "running"
            started = _event("chapter_started", run_id, node, chapter=chapter_name, index=chapter_index, total=target)
            _persist_event(runner, run_id, state, started)
            yield started
            chapter_result, content, generation_events = await generate_chapter_candidates(
                runner,
                node,
                state,
                run_id,
                chapter_index,
                chapter_name,
                candidate_count,
                policy,
            )
            for event in generation_events:
                yield event
            if chapter_result is None:
                message = f"{chapter_name} 所有候选均未通过结构化合同校验"
                failure = register_failure(
                    state,
                    node_id=node.id,
                    node_type=node.type,
                    chapter=chapter_name,
                    code="artifact_validation",
                    message=message,
                )
                error = _event(
                    "node_failed",
                    run_id,
                    node,
                    error=message,
                    failure=failure,
                    recovery_state=state.recovery_state,
                )
                state.errors.append(error)
                state.progress[node.id] = {"status": "failed", "error": error["error"]}
                _persist_event(runner, run_id, state, error)
                yield error
                return
            existing = drafting_chapter(
                chapter_result,
                index=chapter_index,
                content=content,
                context_packet=context_packet,
            )
            upsert_chapter(artifact, existing)
            state.artifacts[output_key] = artifact
            runner.run_store.update_state(run_id, state)
            for delta in chapter_deltas(content):
                event = _event("chapter_delta", run_id, node, chapter=chapter_name, delta=delta)
                runner.run_store.append_event(run_id, event)
                yield event
            for step_event in (
                chapter_pipeline_step_event(run_id, node, chapter_name, 4, words=len(content)),
                chapter_pipeline_step_event(run_id, node, chapter_name, 5, valid=True),
                chapter_pipeline_step_event(
                    run_id, node, chapter_name, 6, checkpoint="drafting"
                ),
            ):
                _persist_event(runner, run_id, state, step_event)
                yield step_event

        revised_content = str(existing["content"])
        async for event in quality_loop_for_result(
            runner,
            node,
            revised_content,
            state,
            workflow,
            run_id,
            chapter=chapter_name,
            context_packet=context_packet,
            model_reviewer=model_reviewer,
        ):
            yield event
        if state.errors:
            return
        reports = [item for item in state.quality_reports if item.get("node_id") == node.id and item.get("chapter") == chapter_name]
        if reports and reports[-1].get("revised_content"):
            revised_content = str(reports[-1]["revised_content"])
        report = reports[-1] if reports else quality_event(node, revised_content).model_dump()
        quality_step = chapter_pipeline_step_event(
            run_id,
            node,
            chapter_name,
            7,
            score=float(report.get("score") or 0),
            passed=bool(report.get("passed", True)),
        )
        _persist_event(runner, run_id, state, quality_step)
        yield quality_step
        revisions = [item.model_dump() for item in state.revision_directives if item.chapter == chapter_name]
        prepared = prepare_chapter_commit(
            existing,
            content=revised_content,
            quality_report=report,
            revision_history=revisions,
        )
        if workflow.quality_mode == "deep":
            # Deep mode: the human signs off with the full review report on the
            # chapter artifact (status "unavailable" is kept as-is — no fake scores).
            model_review = stored_model_review(state, chapter_name)
            if model_review:
                prepared["model_review"] = model_review
        upsert_chapter(artifact, prepared)
        state.artifacts[output_key] = artifact
        runner.run_store.update_state(run_id, state)
        async for event in _finish_commit(
            runner,
            node,
            state,
            artifact,
            prepared,
            run_id,
            chapter_index,
            chapter_name,
            prompt_text,
            candidate_count,
            workflow.quality_mode != "deep",
        ):
            yield event

    final_result = normalize_chapter_artifact(artifact, target)
    final_result["status"] = "completed"
    state.artifacts[output_key] = final_result
    state.artifacts["chapters_text"] = "\n\n".join(str(item["content"]) for item in final_result["chapters"])
    state.progress[node.id] = {"status": "completed", "output_key": output_key}
    validation = validate_stage_artifact(node.type, final_result)
    if validation.valid and workflow.quality_mode != "deep":
        mark_chapter_artifact_committed(state, node, final_result)
    validation_event = _event(
        "artifact_validated" if validation.valid else "artifact_validation_failed",
        run_id,
        node,
        schema_name=validation.schema_name,
        errors=validation.errors,
    )
    completed = _event("node_completed", run_id, node, output_key=output_key, result=final_result, artifact_source="live")
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, validation_event)
    yield validation_event
    if not validation.valid:
        message = "; ".join(validation.errors)
        failure = register_failure(
            state,
            node_id=node.id,
            node_type=node.type,
            code="artifact_validation",
            message=message,
        )
        error = _event(
            "node_failed",
            run_id,
            node,
            error=message,
            failure=failure,
            recovery_state=state.recovery_state,
        )
        state.errors.append(error)
        state.progress[node.id] = {"status": "failed", "error": error["error"]}
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, error)
        yield error
        return
    mark_stable_checkpoint(
        state,
        node_id=node.id,
        node_type=node.type,
        output_key=output_key,
        status="awaiting_confirmation" if workflow.quality_mode == "deep" else "completed",
        artifact=final_result,
    )
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, completed)
    yield completed


async def _finish_commit(
    runner: Any,
    node: Any,
    state: Any,
    artifact: dict[str, Any],
    chapter: dict[str, Any],
    run_id: str,
    chapter_index: int,
    chapter_name: str,
    prompt_text: str,
    candidate_count: int,
    writeback: bool,
) -> AsyncIterator[dict[str, Any]]:
    quality, usage = commit_chapter_effects(
        runner,
        node,
        state,
        chapter,
        chapter_name=chapter_name,
        chapter_index=chapter_index,
        prompt_text=prompt_text,
        candidate_count=candidate_count,
        writeback=writeback,
    )
    completed_chapter = complete_chapter_commit(chapter)
    upsert_chapter(artifact, completed_chapter)
    state.artifacts[node.output_key or node.id] = artifact
    state.progress[node.id] = {
        "status": "running",
        "completed_chapters": sum(item.get("status") == "completed" for item in artifact["chapters"]),
        "total_chapters": artifact["target_chapters"],
    }
    mark_stable_checkpoint(
        state,
        node_id=node.id,
        node_type=node.type,
        output_key=node.output_key or node.id,
        chapter=chapter_name,
        status="chapter_committed",
        artifact=artifact,
    )
    events = [
        chapter_pipeline_step_event(
            run_id, node, chapter_name, 8, summary=completed_chapter.get("summary", "")
        ),
        chapter_pipeline_step_event(
            run_id, node, chapter_name, 9, score=float(quality.score)
        ),
        *_chapter_completed_events(
            run_id, node, state, completed_chapter, chapter_name, quality, usage
        ),
        chapter_pipeline_step_event(
            run_id, node, chapter_name, 10, version=completed_chapter.get("version")
        ),
    ]
    canon_summary = state.stage_display_artifacts.get("canon_commits", {}).get(chapter_name)
    if canon_summary:
        events.insert(0, canon_commit_event(run_id, node, chapter_name, canon_summary))
    for event in events:
        _persist_event(runner, run_id, state, event)
        yield event


def _context_packet(runner: Any, state: Any, chapter: dict[str, Any] | None, index: int, target: int) -> ChapterContextPacket:
    saved = chapter.get("context_packet") if chapter else None
    if isinstance(saved, dict) and saved:
        return ChapterContextPacket.model_validate(saved)
    return runner.quality_engine.build_chapter_context(chapter_index=index, total_chapters=target, state=state)


def _chapter_completed_events(
    run_id: str,
    node: Any,
    state: Any,
    chapter: dict[str, Any],
    chapter_name: str,
    quality: Any,
    usage: Any,
) -> list[dict[str, Any]]:
    return [
        _event("quality_check_completed", run_id, node, chapter=chapter_name, quality=quality.model_dump()),
        _event("chapter_completed", run_id, node, chapter=chapter_name, content=chapter["content"], words=chapter["words"], quality=quality.model_dump(), artifact=chapter),
        _progress_event(run_id, node, state),
        _event("character_graph_updated", run_id, node, character_graph=state.character_graph.model_dump()),
        _event("worldbuilding_updated", run_id, node, worldbuilding=state.worldbuilding_state),
        _event("wiki_state_updated", run_id, node, wiki_state=state.wiki_state),
        _event("story_bible_updated", run_id, node, chapter=chapter_name, story_bible=state.story_bible.model_dump()),
        _event("token_estimate_updated", run_id, node, token_estimates=state.token_estimates),
        _event("stage_usage_updated", run_id, node, chapter=chapter_name, usage=usage.model_dump()),
        _event("stage_usage_finalized", run_id, node, chapter=chapter_name, usage=usage.model_dump()),
    ]


def _progress_event(run_id: str, node: Any, state: Any) -> dict[str, Any]:
    return _event("chapter_progress_updated", run_id, node, chapters=[item.model_dump() for item in state.chapter_progress])


def _event(event_type: str, run_id: str, node: Any, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, **payload}


def _persist_event(runner: Any, run_id: str, state: Any, event: dict[str, Any]) -> None:
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, event)
