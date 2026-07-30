from __future__ import annotations

import hashlib
import json
from typing import Any

from novel_workflow.orchestration.character_network import normalize_tier, register_characters, upsert_relation
from novel_workflow.workflows.schemas import NovelRunState


def outline_reference_errors(state: NovelRunState, artifact: Any) -> list[str]:
    if not isinstance(artifact, dict):
        return ["Outline artifact must be an object"]
    known_names = _confirmed_info_names(state)
    world_detail = _confirmed_world_detail(state)
    if not known_names:
        return ["Outline character progression requires confirmed Info characters"]
    if not world_detail:
        return ["Outline world reveals require confirmed Info worldbuilding"]

    errors: list[str] = []
    referencable = set(known_names)
    for volume_index, volume in enumerate(_record_list(artifact.get("volumes"))):
        for item_index, item in enumerate(_record_list(volume.get("new_characters"))):
            prefix = f"volumes.{volume_index}.new_characters.{item_index}"
            name = _text(item.get("name"))
            if not name:
                errors.append(f"{prefix}.name is required")
                continue
            if name in referencable:
                errors.append(f"{prefix}.name duplicates an existing character")
                continue
            if normalize_tier(item.get("tier"), default="supporting") in {"protagonist", "major"}:
                errors.append(f"{prefix}.tier cannot introduce protagonist/major characters outside Info")
            referencable.add(name)
        seen_relations: set[tuple[str, str]] = set()
        for item_index, item in enumerate(_record_list(volume.get("character_progression"))):
            character = _text(item.get("character"))
            related_to = _text(item.get("related_to"))
            prefix = f"volumes.{volume_index}.character_progression.{item_index}"
            if character not in referencable:
                errors.append(f"{prefix}.character must reference a confirmed Info character")
            if related_to not in referencable:
                errors.append(f"{prefix}.related_to must reference a confirmed Info character")
            if character and character == related_to:
                errors.append(f"{prefix}.related_to must reference a different character")
            relation_key = tuple(sorted((character, related_to)))
            if character and related_to and relation_key in seen_relations:
                errors.append(f"{prefix} duplicates an existing character relationship")
            if character and related_to:
                seen_relations.add(relation_key)

        for item_index, item in enumerate(_record_list(volume.get("world_reveal"))):
            anchor = _text(item.get("anchor"))
            if anchor and anchor not in world_detail:
                errors.append(
                    f"volumes.{volume_index}.world_reveal.{item_index}.anchor must reference confirmed Info worldbuilding"
                )

        seen_clues: set[str] = set()
        for item_index, item in enumerate(_record_list(volume.get("foreshadow_plan"))):
            name = _text(item.get("name"))
            if name and name in seen_clues:
                errors.append(f"volumes.{volume_index}.foreshadow_plan.{item_index}.name duplicates an existing clue")
            if name:
                seen_clues.add(name)
    return errors


def commit_outline_writebacks(
    runner: Any,
    node: Any,
    artifact: Any,
    state: NovelRunState,
    run_id: str,
) -> list[dict[str, Any]]:
    errors = outline_reference_errors(state, artifact)
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
    state.story_bible = runner.quality_engine.update_story_bible(state.story_bible, node, artifact)
    _update_character_writebacks(state, artifact, node.id)
    _update_world_writebacks(state, artifact, node.id)
    _update_foreshadow_writebacks(state, artifact, node.id)
    state.wiki_state = runner._wiki_state(state)
    state.continuity_state = runner._continuity_state(state)
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
            "message": "分卷人物承接已写入人物关系网。",
        },
        {
            "type": "worldbuilding_updated",
            "run_id": run_id,
            "node_id": node.id,
            "node_type": node.type,
            "label": node.label,
            "worldbuilding": state.worldbuilding_state,
            "message": "分卷揭示与硬规则已写入世界观。",
        },
    ]
    runner.run_store.update_state(run_id, state)
    for event in events:
        runner.run_store.append_event(run_id, event)
    return events


def _update_character_writebacks(state: NovelRunState, artifact: Any, node_id: str) -> None:
    graph = state.character_graph.model_copy(deep=True)
    edges = list(graph.edges)
    profiles = dict(state.story_bible.character_profiles)
    for volume in _record_list(artifact.get("volumes")):
        volume_title = _text(volume.get("title"))
        added = register_characters(graph, _record_list(volume.get("new_characters")), tier="supporting", stage=node_id)
        for node in added:
            profiles.setdefault(node.name, {"role": node.role, "tier": node.tier, "introduced_in": volume_title, "updated_by": node_id})
        nodes_by_name = {item.name: item for item in graph.nodes}
        for item in _record_list(volume.get("character_progression")):
            character = _text(item.get("character"))
            related_to = _text(item.get("related_to"))
            node = nodes_by_name.get(character)
            if node is not None:
                node.status = _text(item.get("pressure")) or _text(item.get("change")) or node.status
            profile = dict(profiles.get(character, {}))
            progressions = [entry for entry in profile.get("outline_progressions", []) if entry.get("volume") != volume_title]
            progressions.append({"volume": volume_title, **item, "updated_by": node_id})
            profiles[character] = {**profile, "outline_progressions": progressions, "updated_by": node_id}
            upsert_relation(edges, graph, character, related_to, item, stage=node_id, default_strength=0.58)
    graph.edges = edges
    graph.updated_by = node_id
    state.character_graph = graph
    state.story_bible.character_profiles = profiles
    state.story_bible.relationships = [edge.model_dump() for edge in edges]
    state.story_bible.updated_by = node_id


def _update_world_writebacks(state: NovelRunState, artifact: Any, node_id: str) -> None:
    reveals: list[dict[str, Any]] = []
    rules: list[str] = []
    for volume in _record_list(artifact.get("volumes")):
        volume_title = _text(volume.get("title"))
        for item in _record_list(volume.get("world_reveal")):
            reveals.append({"volume": volume_title, **item, "updated_by": node_id})
            rule = _text(item.get("rule"))
            if rule:
                rules.append(rule)
    state.worldbuilding_state["outline_reveals"] = reveals
    state.worldbuilding_state["hard_rules"] = _unique([*state.worldbuilding_state.get("hard_rules", []), *rules])
    state.worldbuilding_state["updated_by"] = node_id
    state.story_bible.world_rules = _unique([*state.story_bible.world_rules, *rules])


def _update_foreshadow_writebacks(state: NovelRunState, artifact: Any, node_id: str) -> None:
    incoming: list[dict[str, Any]] = []
    for volume in _record_list(artifact.get("volumes")):
        volume_title = _text(volume.get("title"))
        for item in _record_list(volume.get("foreshadow_plan")):
            name = _text(item.get("name"))
            incoming.append({"id": f"outline:{volume_title}:{name}", "source": node_id, "volume": volume_title, **item})
    retained = [item for item in state.story_bible.foreshadow_ledger if item.get("source") != node_id]
    state.story_bible.foreshadow_ledger = [*retained, *incoming][-30:]
    state.foreshadow_ledger = state.story_bible.foreshadow_ledger


def _confirmed_info_artifact(state: NovelRunState) -> dict[str, Any]:
    artifact = state.approved_artifacts.get("info_recommend")
    if not isinstance(artifact, dict):
        content = state.story_brief.get("content") if isinstance(state.story_brief, dict) else None
        artifact = content if isinstance(content, dict) else state.artifacts.get("info_recommend")
    return artifact if isinstance(artifact, dict) else {}


def _confirmed_info_names(state: NovelRunState) -> set[str]:
    return {_text(item.get("name")) for item in _record_list(_confirmed_info_artifact(state).get("characters")) if _text(item.get("name"))}


def _confirmed_world_detail(state: NovelRunState) -> str:
    return _text(_confirmed_info_artifact(state).get("worldbuilding_detail"))


def _record_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _unique(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(_text(value) for value in values if _text(value)))


def _artifact_signature(artifact: Any) -> str:
    payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
