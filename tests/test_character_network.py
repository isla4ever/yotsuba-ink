from novel_workflow.orchestration.character_network import (
    compact_graph_lines,
    graph_from_brief,
    normalize_kind,
    normalize_polarity,
    normalize_tier,
    register_characters,
    upsert_relation,
)
from novel_workflow.workflows.schemas import CharacterGraph


BRIEF = {
    "characters": [
        {"name": "林拾", "identity": "档案馆修复师", "motivation": "追查母亲失踪真相", "tier": "protagonist", "faction": "档案馆", "faction_stance": "主角方"},
        {"name": "沈决", "identity": "缉私警", "motivation": "洗刷冤屈", "tier": "major", "faction": "海关缉私科"},
        {"name": "周聿", "identity": "旧案证人", "motivation": "隐瞒往事", "tier": "配角"},
    ],
    "relationships": [
        {"source": "林拾", "target": "沈决", "relation": "互相利用的调查同盟", "kind": "ally", "polarity": "complex", "strength": 0.7},
        {"source": "沈决", "target": "周聿", "relation": "旧案对峙", "kind": "敌对", "polarity": "负向"},
    ],
}


def test_normalizers_accept_english_and_chinese_synonyms():
    assert normalize_tier("主角") == "protagonist"
    assert normalize_tier("配角") == "supporting"
    assert normalize_tier("unknown-value", default="minor") == "minor"
    assert normalize_kind("敌对") == "rival"
    assert normalize_kind("") == "other"
    assert normalize_polarity("负向") == "negative"
    assert normalize_polarity(None) == "neutral"


def test_graph_from_brief_builds_tiers_factions_and_provenance():
    graph = graph_from_brief("info", BRIEF)
    by_name = {node.name: node for node in graph.nodes}
    assert by_name["林拾"].tier == "protagonist"
    assert by_name["沈决"].tier == "major"
    assert by_name["周聿"].tier == "supporting"
    assert by_name["林拾"].faction_id and by_name["林拾"].faction == "档案馆"
    assert all(node.first_appearance_stage == "info" for node in graph.nodes)
    assert {faction.name for faction in graph.factions} == {"档案馆", "海关缉私科"}
    assert next(faction for faction in graph.factions if faction.name == "档案馆").stance == "protagonist_side"


def test_graph_from_brief_does_not_fabricate_missing_data():
    graph = graph_from_brief("info", {"characters": [{"name": "甲"}, {"name": "乙"}]})
    assert all(node.faction == "" and node.faction_id == "" for node in graph.nodes)
    assert graph.factions == []
    assert graph.edges == []


def test_graph_edge_semantics_and_strength_clamp():
    graph = graph_from_brief("info", BRIEF)
    ally = next(edge for edge in graph.edges if edge.kind == "ally")
    assert ally.polarity == "complex" and ally.strength == 0.7 and ally.valid_from_stage == "info"
    rival = next(edge for edge in graph.edges if edge.kind == "rival")
    assert rival.polarity == "negative" and rival.strength == 0.5


def test_legacy_graph_dict_parses_without_new_fields():
    legacy = {
        "nodes": [{"id": "character-1", "name": "旧角色", "role": "旧身份", "faction": "未分组", "status": "旧状态"}],
        "edges": [{"source": "character-1", "target": "character-1", "relation": "旧关系", "strength": 0.4}],
        "updated_by": "info",
    }
    graph = CharacterGraph.model_validate(legacy)
    assert graph.nodes[0].tier == "supporting"
    assert graph.edges[0].kind == "other" and graph.edges[0].history == []
    assert graph.factions == []


def test_register_characters_skips_duplicates_and_stamps_provenance():
    graph = graph_from_brief("info", BRIEF)
    added = register_characters(
        graph,
        [
            {"name": "老周", "role": "码头线人", "faction": "码头帮"},
            {"name": "林拾", "role": "重复的名字"},
        ],
        tier="minor",
        stage="detail",
        chapter="第3章",
    )
    assert [node.name for node in added] == ["老周"]
    node = added[0]
    assert node.tier == "minor"
    assert node.first_appearance_stage == "detail" and node.first_appearance_chapter == "第3章"
    assert any(faction.name == "码头帮" for faction in graph.factions)


def test_upsert_relation_appends_history_and_updates_semantics():
    graph = graph_from_brief("info", BRIEF)
    edges = list(graph.edges)
    upsert_relation(
        edges,
        graph,
        "林拾",
        "沈决",
        {"relation": "转为公开合作", "polarity": "positive", "strength": 0.85, "change": "联手公开旧案"},
        stage="outline",
    )
    edge = next(item for item in edges if {item.source, item.target} == {"character-1", "character-2"})
    assert edge.relation == "转为公开合作" and edge.polarity == "positive" and edge.strength == 0.85
    assert edge.history[-1] == {"stage": "outline", "chapter": "", "change": "联手公开旧案"}

    upsert_relation(
        edges,
        graph,
        "林拾",
        "周聿",
        {"relation": "试探接近", "kind": "secret", "strength": 0.3},
        stage="detail",
        chapter="第5章",
    )
    new_edge = next(item for item in edges if {item.source, item.target} == {"character-1", "character-3"})
    assert new_edge.kind == "secret" and new_edge.valid_from_stage == "detail" and new_edge.valid_from_chapter == "第5章"


def test_compact_graph_lines_filters_by_names():
    graph = graph_from_brief("info", BRIEF)
    lines = compact_graph_lines(graph, only_names={"林拾", "沈决"})
    text = "\n".join(lines)
    assert "林拾" in text and "沈决" in text and "周聿" not in text
    assert "ally/complex" in text
