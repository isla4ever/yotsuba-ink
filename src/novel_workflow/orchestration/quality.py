from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


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

    report = runner.quality_engine.check_stage(
        node,
        result,
        story_bible=state.story_bible,
        mode=workflow.quality_mode,
        chapter=chapter,
        context_packet=context_packet,
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
        error = {"type": "node_failed", "run_id": run_id, "node_id": node.id, "chapter": chapter, "error": blocking[0].message}
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

    max_revisions = 0 if workflow.quality_mode == "fast" else 1 if workflow.quality_mode == "balanced" else 2
    current = str(result or "")
    for _ in range(max_revisions):
        directive = runner.quality_engine.directive_for(report)
        if directive is None:
            break
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
