from __future__ import annotations

import hashlib
import json
from typing import Any

from novel_workflow.orchestration.chapter_artifact import upsert_context_packet
from novel_workflow.orchestration.chapter_commit import commit_chapter_effects
from novel_workflow.orchestration.chapter_pipeline_events import canon_commit_event
from novel_workflow.workflows.schemas import ChapterContextPacket, NovelRunState


def commit_chapter_artifact_writebacks(
    runner: Any,
    node: Any,
    artifact: Any,
    state: NovelRunState,
    run_id: str,
) -> list[dict[str, Any]]:
    if not isinstance(artifact, dict) or not isinstance(artifact.get("chapters"), list):
        raise ValueError("Chapter artifact must contain chapters")
    marker_key = f"{node.id}_confirmed_writeback"
    signature = chapter_artifact_signature(artifact)
    marker = state.stage_display_artifacts.get(marker_key)
    if isinstance(marker, dict) and marker.get("signature") == signature:
        return []

    state.stage_display_artifacts["canon_commits"] = {}
    previous_ref_ids = {str(item.get("id") or "") for item in state.wiki_refs}
    for index, chapter in enumerate(artifact["chapters"], start=1):
        if not isinstance(chapter, dict):
            continue
        chapter_name = str(chapter.get("title") or f"第{index}章")
        packet = ChapterContextPacket.model_validate(chapter.get("context_packet") or {})
        upsert_context_packet(state, packet)
        commit_chapter_effects(
            runner,
            node,
            state,
            chapter,
            chapter_name=chapter_name,
            chapter_index=index,
            prompt_text="",
            candidate_count=1,
            track_usage=False,
            writeback=True,
        )
    written = [item for item in state.wiki_refs if str(item.get("id") or "") not in previous_ref_ids]
    state.artifacts[node.output_key or node.id] = artifact
    state.artifacts["chapters_text"] = "\n\n".join(
        str(item.get("content") or "") for item in artifact["chapters"] if isinstance(item, dict)
    )
    state.stage_display_artifacts[marker_key] = {"signature": signature, "status": "committed"}
    events = [
        _event(runner, node, run_id, "memory_writeback_completed", written=written, status=runner.wiki_store.status(state.project_id)),
        _event(runner, node, run_id, "story_bible_updated", story_bible=state.story_bible.model_dump()),
        _event(runner, node, run_id, "character_graph_updated", character_graph=state.character_graph.model_dump(), message="正文人物变化已写入人物关系网。"),
        _event(runner, node, run_id, "worldbuilding_updated", worldbuilding=state.worldbuilding_state, message="正文事实、Wiki 与伏笔动作已正式写回。"),
    ]
    canon_commits = state.stage_display_artifacts.get("canon_commits", {})
    for chapter_name, summary in canon_commits.items():
        events.append(canon_commit_event(run_id, node, chapter_name, summary))
    runner.run_store.update_state(run_id, state)
    for event in events:
        runner.run_store.append_event(run_id, event)
    return events


def mark_chapter_artifact_committed(state: NovelRunState, node: Any, artifact: Any) -> None:
    state.stage_display_artifacts[f"{node.id}_confirmed_writeback"] = {
        "signature": chapter_artifact_signature(artifact),
        "status": "committed",
    }


def chapter_artifact_signature(artifact: Any) -> str:
    payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _event(runner: Any, node: Any, run_id: str, event_type: str, **payload: Any) -> dict[str, Any]:
    del runner
    return {"type": event_type, "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, **payload}
