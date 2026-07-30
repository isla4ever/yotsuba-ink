from __future__ import annotations

import hashlib
import json
from typing import Any

from novel_workflow.workflows.schemas import CharacterGraph, NovelRunState


def summary_reference_errors(state: NovelRunState, artifact: Any) -> list[str]:
    if not isinstance(artifact, dict):
        return ["Summary artifact must be an object"]
    known_names = _confirmed_info_names(state)
    if not known_names:
        return ["Summary character arcs require confirmed Info characters"]
    errors: list[str] = []
    seen: set[str] = set()
    arcs = artifact.get("character_arcs") if isinstance(artifact.get("character_arcs"), list) else []
    for index, arc in enumerate(arcs):
        if not isinstance(arc, dict):
            continue
        name = str(arc.get("name") or "").strip()
        if name not in known_names:
            errors.append(f"character_arcs.{index}.name must reference a confirmed Info character")
        if name and name in seen:
            errors.append(f"character_arcs.{index}.name duplicates an existing character arc")
        if name:
            seen.add(name)
    return errors


def commit_summary_writebacks(
    runner: Any,
    node: Any,
    artifact: Any,
    state: NovelRunState,
    run_id: str,
) -> list[dict[str, Any]]:
    errors = summary_reference_errors(state, artifact)
    if errors:
        raise ValueError("; ".join(errors))
    marker_key = f"{node.id}_confirmed_writeback"
    signature = _artifact_signature(artifact)
    marker = state.stage_display_artifacts.get(marker_key)
    if isinstance(marker, dict) and marker.get("signature") == signature:
        return []

    output_key = node.output_key or node.id
    refs = runner._write_memory(node, output_key, artifact, state) if node.memory_policy.write else []
    state.wiki_refs.extend(refs)
    state.wiki_state = runner._wiki_state(state)
    state.story_bible = runner.quality_engine.update_story_bible(state.story_bible, node, artifact)
    _update_story_bible_characters(state, artifact, node.id)
    state.foreshadow_ledger = state.story_bible.foreshadow_ledger
    runner._update_worldbuilding_state(node, artifact, state)
    state.continuity_state = runner._continuity_state(state)
    state.character_graph = _summary_character_graph(state.character_graph, artifact, node.id)
    state.stage_display_artifacts[marker_key] = {"signature": signature, "status": "committed"}

    events = [
        {
            "type": "memory_writeback_completed",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "written": refs,
            "status": runner.wiki_store.status(state.project_id),
        },
        {
            "type": "story_bible_updated",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "story_bible": state.story_bible.model_dump(),
        },
        {
            "type": "character_graph_updated",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "character_graph": state.character_graph.model_dump(),
            "message": "梗概人物弧、关系压力和后续影响已写入人物关系网。",
        },
    ]
    runner.run_store.update_state(run_id, state)
    for event in events:
        runner.run_store.append_event(run_id, event)
    return events


def _confirmed_info_names(state: NovelRunState) -> set[str]:
    artifact = state.approved_artifacts.get("info_recommend")
    if not isinstance(artifact, dict):
        content = state.story_brief.get("content") if isinstance(state.story_brief, dict) else None
        artifact = content if isinstance(content, dict) else state.artifacts.get("info_recommend")
    characters = artifact.get("characters") if isinstance(artifact, dict) and isinstance(artifact.get("characters"), list) else []
    return {
        str(item.get("name") or "").strip()
        for item in characters
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _summary_character_graph(current: CharacterGraph, artifact: Any, node_id: str) -> CharacterGraph:
    arcs = artifact.get("character_arcs") if isinstance(artifact, dict) and isinstance(artifact.get("character_arcs"), list) else []
    by_name = {str(item.get("name") or "").strip(): item for item in arcs if isinstance(item, dict)}
    nodes = []
    for node in current.nodes:
        arc = by_name.get(node.name)
        status = str((arc or {}).get("pressure") or (arc or {}).get("arc") or node.status).strip()
        nodes.append(node.model_copy(update={"status": status}))
    return current.model_copy(update={"nodes": nodes, "updated_by": node_id})


def _update_story_bible_characters(state: NovelRunState, artifact: Any, node_id: str) -> None:
    arcs = artifact.get("character_arcs") if isinstance(artifact, dict) and isinstance(artifact.get("character_arcs"), list) else []
    profiles = dict(state.story_bible.character_profiles)
    for arc in arcs:
        if not isinstance(arc, dict):
            continue
        name = str(arc.get("name") or "").strip()
        if not name:
            continue
        profiles[name] = {
            **profiles.get(name, {}),
            "arc": str(arc.get("arc") or "").strip(),
            "pressure": str(arc.get("pressure") or "").strip(),
            "next": str(arc.get("next") or "").strip(),
            "updated_by": node_id,
        }
    state.story_bible.character_profiles = profiles
    if not state.story_bible.relationships and state.character_graph.edges:
        state.story_bible.relationships = [edge.model_dump() for edge in state.character_graph.edges]
    state.story_bible.updated_by = node_id


def _artifact_signature(artifact: Any) -> str:
    payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
