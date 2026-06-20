from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.orchestration.control import pause_if_requested
from novel_workflow.orchestration.helpers import (
    chapter_content,
    chapter_count,
    chapter_deltas,
    chapter_draft,
    character_graph,
    continuity_state,
    effective_variant_policy,
    quality_event,
    selected_variant,
    update_worldbuilding_state,
    variant_score,
    wiki_state,
)
from novel_workflow.orchestration.quality import quality_loop_for_result
from novel_workflow.usage import record_stage_usage
from novel_workflow.workflows.schemas import ChapterProgressItem


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
    state.current_phase = "writing"
    phase_event = {"type": "phase_changed", "run_id": run_id, "phase": "writing", "node_id": node.id, "node_type": node.type, "label": node.label}
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, phase_event)
    yield phase_event

    target = chapter_count(node, state)
    state.chapter_progress = [
        ChapterProgressItem(volume="第一卷", chapter=f"第{chapter}章", status="planned", words=0, quality_score=0.0, node_id=node.id)
        for chapter in range(1, target + 1)
    ]
    progress_event = {"type": "chapter_progress_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapters": [item.model_dump() for item in state.chapter_progress]}
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, progress_event)
    yield progress_event

    chapters: list[str] = []
    policy = effective_variant_policy(node, workflow)
    for chapter_index in range(1, target + 1):
        async for event in pause_if_requested(runner, run_id, state, node_id=node.id, chapter=f"第{chapter_index}章"):
            yield event
        chapter_name = f"第{chapter_index}章"
        context_packet = runner.quality_engine.build_chapter_context(chapter_index=chapter_index, total_chapters=target, state=state)
        state.chapter_context_packets.append(context_packet)
        context_event = {
            "type": "chapter_context_built",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "chapter": chapter_name,
            "context_packet": context_packet.model_dump(),
        }
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, context_event)
        yield context_event

        state.chapter_progress[chapter_index - 1].status = "running"
        chapter_started = {"type": "chapter_started", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "index": chapter_index, "total": target}
        runner.run_store.update_state(run_id, state)
        runner.run_store.append_event(run_id, chapter_started)
        yield chapter_started

        candidates = []
        candidate_count = policy.candidate_count if policy.enabled else 1
        prompt_text = runner.stages.prompt_builder.build(node, state)
        for variant_index in range(candidate_count):
            result = await runner.stages.execute(node, state)
            content = chapter_content(result, chapter_index, candidate_count, variant_index)
            variant_id = f"{node.id}-c{chapter_index}-v{variant_index + 1}"
            score = variant_score(content, variant_index)
            draft = chapter_draft(chapter_name, content, variant_id, score)
            state.chapter_drafts.append(draft)
            candidates.append(draft)
            variant_event = {"type": "variant_generated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "variant": draft.model_dump(), "preview": content[:280]}
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, variant_event)
            yield variant_event

        best = max(candidates, key=lambda item: item.score)
        selected = selected_variant(node.id, best.variant_id, best.score, chapter=chapter_name)
        state.selected_variants.append(selected)
        judged = {"type": "variant_judged", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "variants": [item.model_dump() for item in candidates], "dimensions": policy.dimensions}
        selected_event = {"type": "best_variant_selected", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "selected": selected.model_dump()}
        for event in (judged, selected_event):
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, event)
            yield event

        for delta in chapter_deltas(best.content):
            event = {"type": "chapter_delta", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "delta": delta}
            runner.run_store.append_event(run_id, event)
            yield event

        revised_content = best.content
        async for event in quality_loop_for_result(
            runner,
            node,
            revised_content,
            state,
            workflow,
            run_id,
            chapter=chapter_name,
            context_packet=context_packet,
        ):
            yield event
        if state.errors:
            break
        chapter_reports = [
            item for item in state.quality_reports
            if item.get("node_id") == node.id and item.get("chapter") == chapter_name
        ]
        if chapter_reports and chapter_reports[-1].get("revised_content"):
            revised_content = str(chapter_reports[-1]["revised_content"])
        summary = record_stage_usage(
            state,
            stage_key=f"{node.id}:{chapter_name}",
            node=node,
            prompt_text=prompt_text,
            output_text=revised_content,
            candidate_count=candidate_count,
            revision_count=len([item for item in state.revision_directives if item.chapter == chapter_name]),
        )
        qevent = quality_event(node, revised_content)
        state.quality_events.append(qevent)
        state.quality_reports.append(qevent.model_dump())
        state.chapter_progress[chapter_index - 1].status = "completed"
        state.chapter_progress[chapter_index - 1].words = len(revised_content)
        state.chapter_progress[chapter_index - 1].quality_score = qevent.score
        chapters.append(revised_content)
        state.artifacts[node.output_key or node.id] = "\n\n".join(chapters)
        state.progress[node.id] = {"status": "running", "completed_chapters": chapter_index, "total_chapters": target}
        update_worldbuilding_state(node, revised_content, state, chapter_name=chapter_name)
        state.character_graph = character_graph(node.id)
        refs = runner._write_memory(node, f"chapter-{chapter_index}", revised_content, state) if node.memory_policy.write else []
        state.wiki_refs.extend(refs)
        state.wiki_state = wiki_state(runner, state)
        state.story_bible = runner.quality_engine.update_story_bible(state.story_bible, node, revised_content, chapter=chapter_name, context_packet=context_packet)
        state.foreshadow_ledger = state.story_bible.foreshadow_ledger
        state.continuity_state = continuity_state(state)

        events = [
            {"type": "quality_check_completed", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "quality": qevent.model_dump()},
            {"type": "chapter_completed", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "content": revised_content, "words": len(revised_content), "quality": qevent.model_dump()},
            {"type": "chapter_progress_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapters": [item.model_dump() for item in state.chapter_progress]},
            {"type": "character_graph_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "character_graph": state.character_graph.model_dump()},
            {"type": "worldbuilding_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "worldbuilding": state.worldbuilding_state},
            {"type": "wiki_state_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "wiki_state": state.wiki_state},
            {"type": "story_bible_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, "chapter": chapter_name, "story_bible": state.story_bible.model_dump()},
            {"type": "token_estimate_updated", "run_id": run_id, "node_id": node.id, "token_estimates": state.token_estimates},
            {"type": "stage_usage_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "chapter": chapter_name, "usage": summary.model_dump()},
            {"type": "stage_usage_finalized", "run_id": run_id, "node_id": node.id, "node_type": node.type, "chapter": chapter_name, "usage": summary.model_dump()},
        ]
        for event in events:
            runner.run_store.update_state(run_id, state)
            runner.run_store.append_event(run_id, event)
            yield event

    if state.errors:
        return
    final_result = "\n\n".join(chapters)
    state.artifacts[node.output_key or node.id] = final_result
    state.progress[node.id] = {"status": "completed", "output_key": node.output_key or node.id}
    completed = {"type": "node_completed", "run_id": run_id, "node_id": node.id, "output_key": node.output_key or node.id, "result": final_result}
    runner.run_store.update_state(run_id, state)
    runner.run_store.append_event(run_id, completed)
    yield completed
