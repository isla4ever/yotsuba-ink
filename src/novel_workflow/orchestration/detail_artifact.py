from __future__ import annotations

import hashlib
import json
from typing import Any

from novel_workflow.orchestration.character_network import register_characters, upsert_relation
from novel_workflow.workflows.schemas import NovelRunState


def detail_reference_errors(state: NovelRunState, artifact: Any) -> list[str]:
    if not isinstance(artifact, dict):
        return ["Detail artifact must be an object"]
    character_names = _confirmed_info_names(state)
    world_detail, world_anchors = _confirmed_world_context(state)
    if not character_names:
        return ["Detail chapters require confirmed Info characters"]
    if not world_detail and not world_anchors:
        return ["Detail facts require confirmed Info or Outline worldbuilding anchors"]

    registered_names = set(character_names)
    npc_names: set[str] = set()
    for node in state.character_graph.nodes:
        if node.tier in {"minor", "npc"}:
            npc_names.add(node.name)
        else:
            registered_names.add(node.name)

    errors: list[str] = []
    seen_chapters: set[str] = set()
    for chapter_index, chapter in enumerate(_records(artifact.get("chapters"))):
        prefix = f"chapters.{chapter_index}"
        chapter_name = _text(chapter.get("chapter"))
        if chapter_name in seen_chapters:
            errors.append(f"{prefix}.chapter duplicates an existing chapter")
        if chapter_name:
            seen_chapters.add(chapter_name)
        for item_index, item in enumerate(_records(chapter.get("new_npcs"))):
            npc_prefix = f"{prefix}.new_npcs.{item_index}"
            name = _text(item.get("name"))
            if not name:
                errors.append(f"{npc_prefix}.name is required")
                continue
            if name in registered_names or name in npc_names:
                errors.append(f"{npc_prefix}.name duplicates an existing character")
                continue
            npc_names.add(name)
        pov = _text(chapter.get("pov"))
        if pov not in registered_names:
            errors.append(f"{prefix}.pov must reference a confirmed Info character")

        shift = chapter.get("character_shift") if isinstance(chapter.get("character_shift"), dict) else {}
        character = _text(shift.get("character"))
        related_to = _text(shift.get("related_to"))
        relation = _text(shift.get("relation"))
        if character not in registered_names:
            errors.append(f"{prefix}.character_shift.character must reference a confirmed Info character")
        if related_to and related_to not in registered_names:
            errors.append(f"{prefix}.character_shift.related_to must reference a confirmed Info character")
        if character and related_to == character:
            errors.append(f"{prefix}.character_shift.related_to must reference a different character")
        if bool(related_to) != bool(relation):
            errors.append(f"{prefix}.character_shift.related_to and relation must be provided together")

        seen_facts: set[str] = set()
        for item_index, item in enumerate(_records(chapter.get("fact_reveals"))):
            if not _known_world_anchor(_text(item.get("anchor")), world_detail, world_anchors):
                errors.append(f"{prefix}.fact_reveals.{item_index}.anchor must reference confirmed worldbuilding")
            fact = _text(item.get("fact"))
            if fact and fact in seen_facts:
                errors.append(f"{prefix}.fact_reveals.{item_index}.fact duplicates an existing chapter fact")
            if fact:
                seen_facts.add(fact)

        seen_wiki_titles: set[str] = set()
        for item_index, item in enumerate(_records(chapter.get("wiki_candidates"))):
            if not _known_world_anchor(_text(item.get("source_anchor")), world_detail, world_anchors):
                errors.append(f"{prefix}.wiki_candidates.{item_index}.source_anchor must reference confirmed worldbuilding")
            title = _text(item.get("title"))
            if title and title in seen_wiki_titles:
                errors.append(f"{prefix}.wiki_candidates.{item_index}.title duplicates an existing chapter Wiki candidate")
            if title:
                seen_wiki_titles.add(title)

        seen_clues: set[str] = set()
        for item_index, item in enumerate(_records(chapter.get("foreshadow"))):
            name = _text(item.get("name"))
            if name and name in seen_clues:
                errors.append(f"{prefix}.foreshadow.{item_index}.name duplicates an existing chapter clue")
            if name:
                seen_clues.add(name)
    return errors


def commit_detail_writebacks(runner: Any, node: Any, artifact: Any, state: NovelRunState, run_id: str) -> list[dict[str, Any]]:
    errors = detail_reference_errors(state, artifact)
    if errors:
        raise ValueError("; ".join(errors))
    marker_key = f"{node.id}_confirmed_writeback"
    signature = _signature(artifact)
    marker = state.stage_display_artifacts.get(marker_key)
    if isinstance(marker, dict) and marker.get("signature") == signature:
        return []

    output_key = node.output_key or node.id
    refs = runner._write_memory(node, output_key, artifact, state) if node.memory_policy.write else []
    state.wiki_refs.extend(refs)
    _update_story_bible(state, artifact, node.id)
    _update_characters(state, artifact, node.id)
    _update_world_and_wiki(state, artifact, node.id)
    _update_foreshadows(state, artifact, node.id)
    state.wiki_state = runner._wiki_state(state)
    state.continuity_state = runner._continuity_state(state)
    state.stage_display_artifacts[marker_key] = {"signature": signature, "status": "committed"}

    events = [
        _event(runner, node, run_id, "memory_writeback_completed", written=refs, status=runner.wiki_store.status(state.project_id)),
        _event(runner, node, run_id, "story_bible_updated", story_bible=state.story_bible.model_dump()),
        _event(runner, node, run_id, "character_graph_updated", character_graph=state.character_graph.model_dump(), message="章节人物变化已写入人物关系网。"),
        _event(runner, node, run_id, "worldbuilding_updated", worldbuilding=state.worldbuilding_state, message="章节事实、Wiki 候选与伏笔动作已正式写回。"),
    ]
    runner.run_store.update_state(run_id, state)
    for event in events:
        runner.run_store.append_event(run_id, event)
    return events


def _update_story_bible(state: NovelRunState, artifact: Any, node_id: str) -> None:
    retained = [item for item in state.story_bible.timeline if item.get("source") != node_id]
    entries = []
    for chapter in _records(artifact.get("chapters")):
        entries.append({
            "source": node_id,
            "chapter": _text(chapter.get("chapter")),
            "scene": _text(chapter.get("scene")),
            "goal": _text(chapter.get("goal")),
            "hook": _text(chapter.get("hook")),
            "continuity_notes": _text(chapter.get("continuity_notes")),
        })
    state.story_bible.timeline = [*retained, *entries]
    state.story_bible.updated_by = node_id


def _update_characters(state: NovelRunState, artifact: Any, node_id: str) -> None:
    graph = state.character_graph.model_copy(deep=True)
    profiles = dict(state.story_bible.character_profiles)
    edges = list(graph.edges)
    for chapter in _records(artifact.get("chapters")):
        chapter_name = _text(chapter.get("chapter"))
        added = register_characters(graph, _records(chapter.get("new_npcs")), tier="minor", stage=node_id, chapter=chapter_name)
        for node in added:
            profiles.setdefault(node.name, {"role": node.role, "tier": node.tier, "introduced_in": chapter_name, "updated_by": node_id})
        nodes_by_name = {item.name: item for item in graph.nodes}
        shift = chapter.get("character_shift") if isinstance(chapter.get("character_shift"), dict) else {}
        character = _text(shift.get("character"))
        node = nodes_by_name.get(character)
        if node is not None:
            node.status = _text(shift.get("change")) or _text(shift.get("pressure")) or node.status
        profile = dict(profiles.get(character, {}))
        shifts = [item for item in profile.get("detail_shifts", []) if item.get("chapter") != chapter_name]
        shifts.append({"chapter": chapter_name, **shift, "updated_by": node_id})
        profiles[character] = {**profile, "detail_shifts": shifts, "updated_by": node_id}
        upsert_relation(edges, graph, character, _text(shift.get("related_to")), shift, stage=node_id, chapter=chapter_name, default_strength=0.62)
    graph.edges = edges
    graph.updated_by = node_id
    state.character_graph = graph
    state.story_bible.character_profiles = profiles
    state.story_bible.relationships = [edge.model_dump() for edge in edges]


def _update_world_and_wiki(state: NovelRunState, artifact: Any, node_id: str) -> None:
    facts: list[dict[str, Any]] = []
    wiki: list[dict[str, Any]] = []
    for chapter in _records(artifact.get("chapters")):
        chapter_name = _text(chapter.get("chapter"))
        facts.extend({"chapter": chapter_name, **item, "updated_by": node_id} for item in _records(chapter.get("fact_reveals")))
        wiki.extend({"chapter": chapter_name, **item, "updated_by": node_id} for item in _records(chapter.get("wiki_candidates")))
    state.worldbuilding_state["detail_facts"] = facts
    state.worldbuilding_state["wiki_candidates"] = wiki
    state.worldbuilding_state["updated_by"] = node_id
    state.stage_display_artifacts["detail_wiki_candidates"] = wiki


def _update_foreshadows(state: NovelRunState, artifact: Any, node_id: str) -> None:
    incoming: list[dict[str, Any]] = []
    outline_names = _outline_foreshadow_names(state)
    for chapter in _records(artifact.get("chapters")):
        chapter_name = _text(chapter.get("chapter"))
        for item in _records(chapter.get("foreshadow")):
            name = _text(item.get("name"))
            incoming.append({
                "id": f"detail:{chapter_name}:{name}",
                "source": node_id,
                "source_kind": "outline" if name in outline_names else "detail",
                "chapter": chapter_name,
                **item,
            })
    retained = [item for item in state.story_bible.foreshadow_ledger if item.get("source") != node_id]
    state.story_bible.foreshadow_ledger = [*retained, *incoming][-60:]
    state.foreshadow_ledger = state.story_bible.foreshadow_ledger


def _confirmed_info(state: NovelRunState) -> dict[str, Any]:
    artifact = state.approved_artifacts.get("info_recommend")
    if not isinstance(artifact, dict):
        content = state.story_brief.get("content") if isinstance(state.story_brief, dict) else None
        artifact = content if isinstance(content, dict) else state.artifacts.get("info_recommend")
    return artifact if isinstance(artifact, dict) else {}


def _confirmed_info_names(state: NovelRunState) -> set[str]:
    return {_text(item.get("name")) for item in _records(_confirmed_info(state).get("characters")) if _text(item.get("name"))}


def _confirmed_world_context(state: NovelRunState) -> tuple[str, set[str]]:
    detail = _text(_confirmed_info(state).get("worldbuilding_detail"))
    anchors = {_text(item.get("anchor")) for volume in _outline_volumes(state) for item in _records(volume.get("world_reveal"))}
    return detail, {item for item in anchors if item}


def _known_world_anchor(anchor: str, world_detail: str, outline_anchors: set[str]) -> bool:
    return bool(anchor and (anchor in outline_anchors or anchor in world_detail))


def _outline_volumes(state: NovelRunState) -> list[dict[str, Any]]:
    artifact = state.approved_artifacts.get("outline", state.artifacts.get("outline"))
    return _records(artifact.get("volumes")) if isinstance(artifact, dict) else []


def _outline_foreshadow_names(state: NovelRunState) -> set[str]:
    return {_text(item.get("name")) for volume in _outline_volumes(state) for item in _records(volume.get("foreshadow_plan"))}


def _event(runner: Any, node: Any, run_id: str, event_type: str, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, "run_id": run_id, "node_id": node.id, "node_type": node.type, "label": node.label, **payload}


def _records(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _signature(artifact: Any) -> str:
    payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
