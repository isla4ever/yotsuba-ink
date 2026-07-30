from __future__ import annotations

from typing import Any

from novel_workflow.orchestration.helpers import character_graph, continuity_state, quality_event, update_worldbuilding_state, wiki_state
from novel_workflow.orchestration.chapter_review_model import chapter_with_decided_writebacks
from novel_workflow.memory.canon import commit_canon_writebacks
from novel_workflow.usage import record_stage_usage


def commit_chapter_effects(
    runner: Any,
    node: Any,
    state: Any,
    chapter: dict[str, Any],
    *,
    chapter_name: str,
    chapter_index: int,
    prompt_text: str,
    candidate_count: int,
    track_usage: bool = True,
    writeback: bool = True,
) -> tuple[Any, Any | None]:
    content = str(chapter["content"])
    stage_key = f"{node.id}:{chapter_name}"
    usage = None
    if track_usage:
        usage = record_stage_usage(
            state,
            stage_key=stage_key,
            node=node,
            prompt_text=prompt_text,
            output_text=content,
            candidate_count=candidate_count,
            revision_count=len([item for item in state.revision_directives if item.chapter == chapter_name]),
        )
        state.stage_usage_summaries[stage_key] = usage.model_dump()

    quality = quality_event(node, content)
    committed_report = {**quality.model_dump(), "chapter": chapter_name, "record_type": "chapter_commit"}
    already_recorded = any(
        item.get("node_id") == node.id
        and item.get("chapter") == chapter_name
        and item.get("record_type") == "chapter_commit"
        for item in state.quality_reports
    )
    state.quality_reports = [
        item for item in state.quality_reports
        if not (
            item.get("node_id") == node.id
            and item.get("chapter") == chapter_name
            and item.get("record_type") == "chapter_commit"
        )
    ]
    state.quality_reports.append(committed_report)
    if not already_recorded:
        state.quality_events.append(quality)

    progress = next(item for item in state.chapter_progress if item.node_id == node.id and item.chapter == chapter_name)
    progress.status = "completed"
    progress.words = len(content)
    progress.quality_score = quality.score

    update_worldbuilding_state(node, content, state, chapter_name=chapter_name)
    state.character_graph = character_graph(node.id, current=state.character_graph)
    context_packet = next((item for item in state.chapter_context_packets if item.chapter == chapter_name), None)
    proposal = chapter.get("writeback_proposal")
    preserve_foreshadow_ledger = isinstance(proposal, dict) and proposal.get("status") != "accepted"
    previous_foreshadows = [dict(item) for item in state.story_bible.foreshadow_ledger]
    state.story_bible = runner.quality_engine.update_story_bible(
        state.story_bible,
        node,
        content,
        chapter=chapter_name,
        context_packet=context_packet,
    )
    if preserve_foreshadow_ledger:
        state.story_bible.foreshadow_ledger = previous_foreshadows
    _replace_chapter_summary(state, chapter_name, str(chapter.get("summary") or ""))
    if writeback:
        canon_result = commit_canon_writebacks(state.canon_facts, state.canon_conflicts, chapter)
        state.canon_facts = canon_result["facts"]
        state.canon_conflicts = canon_result["conflicts"]
        canon_commits = state.stage_display_artifacts.setdefault("canon_commits", {})
        canon_commits[chapter_name] = {
            "committed": canon_result["committed"],
            "resolved": canon_result["resolved"],
            "pending_conflicts": [item for item in canon_result["conflicts"] if item.get("status") == "pending"],
        }
        writeback_chapter = {
            **chapter_with_decided_writebacks(chapter),
            "wiki_writebacks": canon_result["effective_writebacks"],
        }
        _apply_character_shift(state, writeback_chapter.get("character_shift"), chapter_name)
        _apply_foreshadow_updates(state, writeback_chapter.get("foreshadow_updates"), chapter_name)
        _write_chapter_memory(runner, node, state, writeback_chapter, chapter_index)
    state.foreshadow_ledger = state.story_bible.foreshadow_ledger
    state.continuity_state = continuity_state(state)
    state.wiki_state = wiki_state(runner, state)
    return quality, usage


def _replace_chapter_summary(state: Any, chapter_name: str, summary: str) -> None:
    if not summary.strip():
        return
    for item in state.story_bible.chapter_summaries:
        if item.get("chapter") == chapter_name:
            item["summary"] = summary.strip()
            return


def _write_chapter_memory(runner: Any, node: Any, state: Any, chapter: dict[str, Any], chapter_index: int) -> None:
    output_key = f"chapter-{chapter_index}"
    if node.memory_policy.write and not _has_output_ref(state, node.id, output_key):
        _extend_unique_refs(state, runner._write_memory(node, output_key, chapter["content"], state))
    for writeback_index, item in enumerate(chapter.get("wiki_writebacks") or [], start=1):
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or "").strip()
        fact = str(item.get("fact") or "").strip()
        writeback_key = f"{output_key}:wiki:{writeback_index}"
        if not target or not fact or _has_output_ref(state, node.id, writeback_key):
            continue
        ref = runner.wiki_store.write(state.project_id, title=target, content=fact, source_type="chapter_writeback")
        _extend_unique_refs(
            state,
            [{**ref, "node_id": node.id, "node_type": node.type, "output_key": writeback_key, "kinds": ["chapter"]}],
        )


def _has_output_ref(state: Any, node_id: str, output_key: str) -> bool:
    return any(item.get("node_id") == node_id and item.get("output_key") == output_key for item in state.wiki_refs)


def _extend_unique_refs(state: Any, refs: list[dict[str, Any]]) -> None:
    known = {str(item.get("id") or "") for item in state.wiki_refs}
    for ref in refs:
        ref_id = str(ref.get("id") or "")
        if ref_id and ref_id not in known:
            state.wiki_refs.append(ref)
            known.add(ref_id)


def _apply_character_shift(state: Any, shift: Any, chapter_name: str) -> None:
    record = shift if isinstance(shift, dict) else {}
    text = str(record.get("change") or record.get("impact") or shift or "").strip()
    explicit = str(record.get("character") or "").strip()
    characters = [
        node.name for node in state.character_graph.nodes
        if node.name == explicit or (not explicit and node.name and node.name in text)
    ]
    shifts = [
        item for item in state.stage_display_artifacts.get("chapter_character_shifts", [])
        if isinstance(item, dict) and item.get("chapter") != chapter_name
    ]
    shifts.append({"chapter": chapter_name, "character": explicit, "change": text})
    state.stage_display_artifacts["chapter_character_shifts"] = shifts
    if not text:
        return
    for node in state.character_graph.nodes:
        if node.name not in characters:
            continue
        node.status = text
        profile = dict(state.story_bible.character_profiles.get(node.name, {}))
        chapter_shifts = [item for item in profile.get("chapter_shifts", []) if item.get("chapter") != chapter_name]
        chapter_shifts.append({"chapter": chapter_name, "change": text, **record})
        state.story_bible.character_profiles[node.name] = {**profile, "chapter_shifts": chapter_shifts, "updated_by": chapter_name}


def _apply_foreshadow_updates(state: Any, updates: Any, chapter_name: str) -> None:
    if not isinstance(updates, list):
        return
    ledger = [dict(item) for item in state.story_bible.foreshadow_ledger]
    for update in updates:
        if not isinstance(update, dict):
            continue
        name = str(update.get("name") or "").strip()
        if not name:
            continue
        ledger = [item for item in ledger if str(item.get("name") or item.get("summary") or "") != name]
        ledger.append(
            {
                "id": str(update.get("id") or f"chapter-{chapter_name}-{name}"),
                "name": name,
                "summary": str(update.get("note") or name),
                "status": str(update.get("status") or "推进"),
                "source": chapter_name,
            }
        )
    state.story_bible.foreshadow_ledger = ledger
