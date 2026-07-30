from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.orchestration.recovery import register_failure
from novel_workflow.quality.model_review import primary_revision_instruction
from novel_workflow.quality.voice_drift import voice_spec_from_state
from novel_workflow.usage import drain_budget_events, record_budget_operation


async def quality_loop_for_result(
    runner: Any,
    node: Any,
    result: Any,
    state: Any,
    workflow: Any,
    run_id: str,
    *,
    chapter: str = "",
    context_packet: Any = None,
    model_reviewer: Any = None,
) -> AsyncIterator[dict[str, Any]]:
    started = {
        "type": "quality_check_started",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "chapter": chapter,
    }
    runner.run_store.append_event(run_id, started)
    yield started

    voice_spec = voice_spec_from_state(state) if node.type == "chapter_text" else None
    report = runner.quality_engine.check_stage(
        node,
        result,
        story_bible=state.story_bible,
        mode=workflow.quality_mode,
        chapter=chapter,
        context_packet=context_packet,
        voice_spec=voice_spec,
    )
    state.quality_reports.append(report.model_dump())
    completed = {
        "type": "quality_check_completed",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "label": node.label,
        "chapter": chapter,
        "quality_report": report.model_dump(),
    }
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, completed)
    yield completed

    blocking = [finding for finding in report.findings if finding.blocking]
    if blocking:
        conflict = {
            "type": "continuity_conflict_found",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter,
            "findings": [finding.model_dump() for finding in blocking],
        }
        intervention = {
            "type": "manual_intervention_required",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter,
            "reason": blocking[0].message,
            "findings": [finding.model_dump() for finding in blocking],
        }
        failure = register_failure(
            state,
            node_id=node.id,
            node_type=node.type,
            chapter=chapter,
            code="quality_blocking",
            message=blocking[0].message,
            retryable=False,
        )
        error = {
            "type": "node_failed",
            "run_id": run_id,
            "node_id": node.id,
            "chapter": chapter,
            "error": blocking[0].message,
            "failure": failure,
            "recovery_state": state.recovery_state,
        }
        state.errors.append(error)
        state.progress[node.id] = {"status": "failed", "error": blocking[0].message}
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, conflict)
        runner.run_store.append_event(run_id, intervention)
        runner.run_store.append_event(run_id, error)
        yield conflict
        yield intervention
        yield error
        return

    current = str(result or "")
    # Quality L2: model review runs after the deterministic L1 gate (fast mode
    # never reaches here with a reviewer — the hook is None by contract).
    review: dict[str, Any] | None = None
    if model_reviewer is not None and chapter:
        review, review_events = await model_reviewer(chapter, current)
        for review_event in review_events:
            yield review_event

    max_revisions = 0 if workflow.quality_mode == "fast" else 1 if workflow.quality_mode == "balanced" else 2
    if node.type != "chapter_text":
        max_revisions = 0
    for _ in range(max_revisions):
        directive = runner.quality_engine.directive_for(report)
        if directive is None:
            break
        if workflow.quality_mode == "balanced":
            review_instruction = primary_revision_instruction(review)
            if review_instruction:
                directive.instruction = review_instruction
        if getattr(state, "run_has_started", False) and not record_budget_operation(state, node, action="revision", chapter=chapter):
            for budget_event in drain_budget_events(state):
                budget_event = {"run_id": run_id, **budget_event}
                runner.run_store.append_event(run_id, budget_event)
                yield budget_event
            failure = register_failure(
                state,
                node_id=node.id,
                node_type=node.type,
                chapter=chapter,
                code="quality_budget_exhausted",
                message="质量自动修订已达到预算上限，需要人工修复后继续",
                retryable=False,
            )
            error = {
                "type": "node_failed",
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "chapter": chapter,
                "error": failure["message"],
                "failure": failure,
                "recovery_state": state.recovery_state,
                "budget_state": state.budget_state,
            }
            state.errors.append(error)
            state.progress[node.id] = {"status": "failed", "error": error["error"]}
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, error)
            yield error
            return
        state.revision_directives.append(directive)
        directive_event = {
            "type": "revision_directive_created",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter,
            "directive": directive.model_dump(),
        }
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, directive_event)
        yield directive_event

        current = runner.quality_engine.apply_directive(current, directive)
        applied_event = {
            "type": "revision_applied",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter,
            "directive": directive.model_dump(),
            "content_preview": current[-420:],
        }
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, applied_event)
        yield applied_event

        report = runner.quality_engine.check_stage(
            node,
            current,
            story_bible=state.story_bible,
            mode=workflow.quality_mode,
            chapter=chapter,
            context_packet=context_packet,
            voice_spec=voice_spec,
        )
        report.revision_required = False
        report_dump = report.model_dump()
        report_dump["revised_content"] = current
        state.quality_reports.append(report_dump)
        recheck_event = {
            "type": "quality_recheck_completed",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter,
            "quality_report": report_dump,
        }
        if not chapter:
            state.artifacts[node.output_key or node.id] = current
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, recheck_event)
        yield recheck_event
        if report.passed:
            break

    # §2.1 mode contract: all modes share the same hard-blocking line (handled
    # above); fast mode records warnings without revision and must keep going.
    if workflow.quality_mode == "fast":
        return
    if not report.passed and getattr(state, "run_has_started", False):
        intervention = {
            "type": "manual_intervention_required",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter,
            "reason": "质量自动修订已达到上限，需要人工修复当前稿后继续。",
            "quality_report": report.model_dump(),
            "budget_state": state.budget_state,
        }
        failure = register_failure(
            state,
            node_id=node.id,
            node_type=node.type,
            chapter=chapter,
            code="quality_budget_exhausted",
            message=intervention["reason"],
            retryable=False,
        )
        error = {
            "type": "node_failed",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "chapter": chapter,
            "error": intervention["reason"],
            "failure": failure,
            "recovery_state": state.recovery_state,
            "budget_state": state.budget_state,
        }
        state.errors.append(error)
        state.progress[node.id] = {"status": "failed", "error": error["error"]}
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, intervention)
        runner.run_store.append_event(run_id, error)
        yield intervention
        yield error
        return
