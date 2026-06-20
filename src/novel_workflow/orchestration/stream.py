from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.orchestration.chapters import run_chapter_text_node
from novel_workflow.orchestration.constants import TEXT_NODE_TYPES
from novel_workflow.orchestration.control import pause_if_requested, wait_for_artifact_approval
from novel_workflow.orchestration.helpers import (
    character_graph,
    continuity_state,
    detail_outline_issue,
    memory_query,
    node_with_mode_policy,
    quality_event,
    update_worldbuilding_state,
    wiki_state,
)
from novel_workflow.orchestration.quality import quality_loop_for_result
from novel_workflow.orchestration.variants import execute_with_variants
from novel_workflow.workflows.schemas import NovelRunState


async def stream_workflow(runner: Any, workflow: Any, run_id: str, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    project_id = str(inputs.get("project_id") or run_id)
    state = NovelRunState(run_id=run_id, project_id=project_id, workflow_id=workflow.id, inputs=inputs)
    ordered_nodes = runner.compiler.compile_order(workflow)
    total = len(ordered_nodes)
    start_event = {"type": "run_started", "run_id": run_id, "total_nodes": total}
    runner.run_store.append_event(run_id, start_event)
    yield start_event

    for index, raw_node in enumerate(ordered_nodes, start=1):
        async for event in pause_if_requested(runner, run_id, state, node_id=raw_node.id):
            yield event
        node = node_with_mode_policy(raw_node, workflow)
        if node.memory_policy.read:
            memory_context = runner.wiki_store.load_context(
                state.project_id,
                node_id=node.id,
                node_type=node.type,
                query=memory_query(node, state),
                kinds=[str(kind) for kind in node.memory_policy.kinds],
            )
            state.memory_contexts[node.id] = memory_context
            memory_event = {
                "type": "memory_context_loaded",
                "run_id": run_id,
                "node_id": node.id,
                "node_type": node.type,
                "label": node.label,
                "memory": memory_context,
            }
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, memory_event)
            yield memory_event

        started = {
            "type": "node_started",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "index": index,
            "total": total,
        }
        runner.run_store.append_event(run_id, started)
        yield started

        try:
            if node.type == "chapter_text":
                issue = detail_outline_issue(node, state)
                if issue:
                    qevent = quality_event(node, issue)
                    qevent.score = 0.32
                    qevent.passed = False
                    qevent.checks = {"detail_outline_complete": False}
                    qevent.warnings = [issue]
                    state.quality_events.append(qevent)
                    state.quality_reports.append(qevent.model_dump())
                    event = {
                        "type": "quality_check_completed",
                        "run_id": run_id,
                        "node_id": node.id,
                        "node_type": node.type,
                        "label": node.label,
                        "quality": qevent.model_dump(),
                    }
                    error = {"type": "node_failed", "run_id": run_id, "node_id": node.id, "error": issue}
                    state.errors.append(error)
                    state.progress[node.id] = {"status": "failed", "error": issue}
                    runner.run_store.update_state(run_id, state)
                    runner.run_store.append_event(run_id, event)
                    runner.run_store.append_event(run_id, error)
                    yield event
                    yield error
                    break
                async for event in run_chapter_text_node(runner, node, state, workflow, run_id, index, total):
                    yield event
                continue

            result, variant_events = await execute_with_variants(runner, node, state, workflow)
            for event in variant_events:
                event["run_id"] = run_id
                runner.run_store.append_event(run_id, event)
                yield event
            output_key = node.output_key or node.id
            state.artifacts[output_key] = result
            state.progress[node.id] = {"status": "completed", "output_key": output_key}
            update_worldbuilding_state(node, result, state)
            completed = {"type": "node_completed", "run_id": run_id, "node_id": node.id, "output_key": output_key, "result": result}
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, completed)
            yield completed

            if node.type == "info_recommend":
                state.story_brief = {"source": "draft_artifact", "content": result}
                state.approval_required = True
                runner.run_store.update_state(run_id, state)
                async for event in wait_for_artifact_approval(runner, run_id, state, node_id=node.id, output_key=output_key, artifact=result):
                    yield event
                approved_artifact = state.approved_artifacts.get(output_key, state.artifacts.get(output_key, result))
                if approved_artifact != result:
                    state.artifacts[output_key] = approved_artifact
                    state.story_brief = {"source": "approved_artifact", "content": approved_artifact}
                    update_worldbuilding_state(node, approved_artifact, state)
                    runner.run_store.update_state(run_id, state)
                result = approved_artifact

            if node.type in TEXT_NODE_TYPES:
                async for event in quality_loop_for_result(runner, node, result, state, workflow, run_id):
                    yield event
                if state.errors:
                    break
                result = state.artifacts.get(output_key, result)
                if node.type in {"info_recommend", "chapter_text"}:
                    state.character_graph = character_graph(node.id)
                    graph_event = {
                        "type": "character_graph_updated",
                        "run_id": run_id,
                        "node_id": node.id,
                        "node_type": node.type,
                        "label": node.label,
                        "character_graph": state.character_graph.model_dump(),
                    }
                    runner.run_store.update_state(run_id, state)
                    runner.run_store.append_event(run_id, graph_event)
                    yield graph_event

            if node.memory_policy.write:
                refs = runner._write_memory(node, output_key, result, state)
                state.wiki_refs.extend(refs)
                state.wiki_state = wiki_state(runner, state)
                memory_event = {
                    "type": "memory_writeback_completed",
                    "run_id": run_id,
                    "node_id": node.id,
                    "node_type": node.type,
                    "label": node.label,
                    "written": refs,
                    "status": runner.wiki_store.status(state.project_id),
                }
                runner.run_store.update_state(run_id, state)
                runner.run_store.append_event(run_id, memory_event)
                yield memory_event

            if node.type in {"info_recommend", "summary", "outline", "detail_outline"}:
                state.story_bible = runner.quality_engine.update_story_bible(state.story_bible, node, result)
                state.foreshadow_ledger = state.story_bible.foreshadow_ledger
                state.continuity_state = continuity_state(state)
                story_event = {
                    "type": "story_bible_updated",
                    "run_id": run_id,
                    "node_id": node.id,
                    "node_type": node.type,
                    "label": node.label,
                    "story_bible": state.story_bible.model_dump(),
                }
                runner.run_store.update_state(run_id, state)
                runner.run_store.append_event(run_id, story_event)
                yield story_event
        except Exception as exc:
            error = {"type": "node_failed", "run_id": run_id, "node_id": node.id, "error": str(exc)}
            state.errors.append(error)
            state.progress[node.id] = {"status": "failed", "error": str(exc)}
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, error)
            yield error
            break

    done = {"type": "run_completed" if not state.errors else "run_failed", "run_id": run_id, "state": state.model_dump()}
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, done)
    yield done
