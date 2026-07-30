"""Character network semantics: tier/kind/polarity normalization, faction
registry, baseline graph building and stage-aware relation upserts.

Phase 10.0A contract: the graph is initialized once at Info (baseline) and
expanded by later stages under explicit quotas; every node/edge records where
it first appeared so the UI can replay network growth over time. Missing data
stays missing — this module never fabricates factions, edges or strengths.
"""
from __future__ import annotations

import re
from typing import Any

from novel_workflow.workflows.run_schemas import (
    CharacterEdge,
    CharacterGraph,
    CharacterNode,
    FactionInfo,
)

_TIER_SYNONYMS: dict[str, str] = {
    "protagonist": "protagonist", "主角": "protagonist", "男主": "protagonist", "女主": "protagonist",
    "major": "major", "要角": "major", "主要角色": "major", "反派": "major", "antagonist": "major",
    "supporting": "supporting", "配角": "supporting", "次要角色": "supporting",
    "minor": "minor", "龙套": "minor", "小角色": "minor",
    "npc": "npc", "路人": "npc",
}

_KIND_SYNONYMS: dict[str, str] = {
    "kinship": "kinship", "亲缘": "kinship", "亲人": "kinship", "家人": "kinship", "血缘": "kinship",
    "romance": "romance", "情感": "romance", "恋人": "romance", "爱慕": "romance",
    "ally": "ally", "盟友": "ally", "同盟": "ally", "战友": "ally", "朋友": "ally",
    "rival": "rival", "敌对": "rival", "对手": "rival", "仇敌": "rival", "宿敌": "rival",
    "superior": "superior", "从属": "superior", "上下级": "superior", "师徒": "superior",
    "trade": "trade", "交易": "trade", "利益": "trade", "合作": "trade",
    "secret": "secret", "秘密": "secret", "隐秘": "secret",
    "other": "other",
}

_POLARITY_SYNONYMS: dict[str, str] = {
    "positive": "positive", "正向": "positive", "友好": "positive",
    "negative": "negative", "负向": "negative", "敌意": "negative",
    "complex": "complex", "复杂": "complex", "爱恨": "complex",
    "neutral": "neutral", "中立": "neutral",
}

_STANCE_SYNONYMS: dict[str, str] = {
    "protagonist_side": "protagonist_side", "主角方": "protagonist_side", "正方": "protagonist_side",
    "antagonist_side": "antagonist_side", "反派方": "antagonist_side", "敌对方": "antagonist_side",
    "neutral": "neutral", "中立": "neutral",
    "hidden": "hidden", "隐藏": "hidden", "暗线": "hidden",
}


def normalize_tier(value: Any, default: str = "supporting") -> str:
    return _TIER_SYNONYMS.get(str(value or "").strip().lower(), _TIER_SYNONYMS.get(str(value or "").strip(), default))


def normalize_kind(value: Any) -> str:
    return _KIND_SYNONYMS.get(str(value or "").strip().lower(), _KIND_SYNONYMS.get(str(value or "").strip(), "other"))


def normalize_polarity(value: Any) -> str:
    return _POLARITY_SYNONYMS.get(str(value or "").strip().lower(), _POLARITY_SYNONYMS.get(str(value or "").strip(), "neutral"))


def normalize_stance(value: Any) -> str:
    return _STANCE_SYNONYMS.get(str(value or "").strip().lower(), _STANCE_SYNONYMS.get(str(value or "").strip(), "neutral"))


def _faction_id(name: str) -> str:
    slug = re.sub(r"\s+", "-", name.strip())
    return f"faction-{slug}" if slug else ""


def _clamp_strength(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def graph_from_brief(node_id: str, record: dict[str, Any], current: CharacterGraph | None = None) -> CharacterGraph:
    """Build the baseline graph from an approved Story Brief artifact."""
    characters = record.get("characters") if isinstance(record.get("characters"), list) else []
    if not characters:
        if current and current.nodes:
            return current.model_copy(update={"updated_by": node_id})
        return CharacterGraph(nodes=[], edges=[], factions=[], updated_by=node_id)

    factions: dict[str, FactionInfo] = {}
    nodes: list[CharacterNode] = []
    ids_by_name: dict[str, str] = {}
    for index, item in enumerate(characters, start=1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        faction_name = str(item.get("faction") or item.get("group") or "").strip()
        faction_id = ""
        if faction_name:
            faction_id = _faction_id(faction_name)
            factions.setdefault(
                faction_id,
                FactionInfo(
                    id=faction_id,
                    name=faction_name,
                    stance=normalize_stance(item.get("faction_stance")),
                    first_appearance_stage=node_id,
                ),
            )
        character_id = f"character-{index}"
        ids_by_name[name] = character_id
        nodes.append(
            CharacterNode(
                id=character_id,
                name=name,
                role=str(item.get("identity") or item.get("role") or "").strip(),
                tier=normalize_tier(item.get("tier"), default="protagonist" if index == 1 and not item.get("tier") else "supporting"),
                faction=faction_name,
                faction_id=faction_id,
                status=str(item.get("motivation") or item.get("status") or "").strip(),
                first_appearance_stage=node_id,
            )
        )

    edges: list[CharacterEdge] = []
    relationships = record.get("relationships") if isinstance(record.get("relationships"), list) else []
    for item in relationships:
        if not isinstance(item, dict):
            continue
        source = ids_by_name.get(str(item.get("source") or "").strip())
        target = ids_by_name.get(str(item.get("target") or "").strip())
        if not source or not target:
            continue
        edges.append(
            CharacterEdge(
                source=source,
                target=target,
                relation=str(item.get("relation") or "").strip(),
                kind=normalize_kind(item.get("kind")),
                polarity=normalize_polarity(item.get("polarity")),
                strength=_clamp_strength(item.get("strength")),
                valid_from_stage=node_id,
            )
        )
    return CharacterGraph(nodes=nodes, edges=edges, factions=list(factions.values()), updated_by=node_id)


def register_characters(
    graph: CharacterGraph,
    entries: list[dict[str, Any]],
    *,
    tier: str,
    stage: str,
    chapter: str = "",
) -> list[CharacterNode]:
    """Register stage-introduced characters (Outline supporting / Detail NPC).

    Skips names that already exist; returns the nodes actually added.
    """
    existing = {node.name for node in graph.nodes}
    added: list[CharacterNode] = []
    next_index = len(graph.nodes) + 1
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name in existing:
            continue
        faction_name = str(entry.get("faction") or "").strip()
        faction_id = _faction_id(faction_name) if faction_name else ""
        if faction_id and all(item.id != faction_id for item in graph.factions):
            graph.factions.append(
                FactionInfo(id=faction_id, name=faction_name, stance=normalize_stance(entry.get("faction_stance")), first_appearance_stage=stage)
            )
        node = CharacterNode(
            id=f"character-{next_index}",
            name=name,
            role=str(entry.get("role") or entry.get("identity") or "").strip(),
            tier=normalize_tier(entry.get("tier"), default=tier),
            faction=faction_name,
            faction_id=faction_id,
            status=str(entry.get("stance") or entry.get("status") or "").strip(),
            first_appearance_stage=stage,
            first_appearance_chapter=chapter,
        )
        graph.nodes.append(node)
        existing.add(name)
        added.append(node)
        next_index += 1
    return added


def upsert_relation(
    edges: list[CharacterEdge],
    graph: CharacterGraph,
    source_name: str,
    target_name: str,
    item: dict[str, Any],
    *,
    stage: str,
    chapter: str = "",
    default_strength: float = 0.5,
) -> None:
    """Shared relation upsert with provenance stamping and history."""
    ids = {node.name: node.id for node in graph.nodes}
    source, target = ids.get(source_name), ids.get(target_name)
    relation = str(item.get("relation") or "").strip()
    if not source or not target or source == target:
        return
    change_note = str(item.get("change") or item.get("pressure") or relation).strip()
    history_entry = {"stage": stage, "chapter": chapter, "change": change_note}
    for index, edge in enumerate(edges):
        if {edge.source, edge.target} == {source, target}:
            update: dict[str, Any] = {"history": [*edge.history, history_entry]}
            if relation:
                update["relation"] = relation
            if item.get("kind"):
                update["kind"] = normalize_kind(item.get("kind"))
            if item.get("polarity"):
                update["polarity"] = normalize_polarity(item.get("polarity"))
            if item.get("strength") is not None:
                update["strength"] = _clamp_strength(item.get("strength"), edge.strength)
            edges[index] = edge.model_copy(update=update)
            return
    if not relation:
        return
    edges.append(
        CharacterEdge(
            source=source,
            target=target,
            relation=relation,
            kind=normalize_kind(item.get("kind")),
            polarity=normalize_polarity(item.get("polarity")),
            strength=_clamp_strength(item.get("strength"), default_strength),
            valid_from_stage=stage,
            valid_from_chapter=chapter,
            history=[history_entry],
        )
    )


def compact_graph_lines(graph: CharacterGraph, *, only_names: set[str] | None = None, max_nodes: int = 40, max_edges: int = 60) -> list[str]:
    """Render the graph as compact prompt lines (L3 entity-state injection).

    When only_names is provided, restrict to those characters and the edges
    between them — this is the lorebook-style on-demand hit path.
    """
    nodes = graph.nodes
    if only_names is not None:
        nodes = [node for node in nodes if node.name in only_names]
    nodes = nodes[:max_nodes]
    included_ids = {node.id for node in nodes}
    lines = [
        f"- {node.name}（{node.tier}｜{node.faction or '无阵营'}）：{node.role}；当前状态：{node.status or '未记录'}"
        for node in nodes
    ]
    names_by_id = {node.id: node.name for node in graph.nodes}
    edge_lines = [
        f"- {names_by_id.get(edge.source, edge.source)} -[{edge.kind}/{edge.polarity}]-> {names_by_id.get(edge.target, edge.target)}：{edge.relation}（强度 {edge.strength:.2f}）"
        for edge in graph.edges
        if edge.source in included_ids and edge.target in included_ids
    ][:max_edges]
    if edge_lines:
        lines.append("关系：")
        lines.extend(edge_lines)
    return lines
