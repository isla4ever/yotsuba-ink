from __future__ import annotations

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.artifacts_vnext import (
    ARTIFACT_MODELS,
    CharacterBibleArtifact,
    STAGE_ORDER,
    validate_artifact_vnext,
)


def character_bible() -> dict[str, object]:
    return {
        "characters": [
            {
                "id": "char-lin",
                "name": "林默",
                "tier": "protagonist",
                "narrative_function": "承担真相调查",
                "external_goal": "找到失踪母带",
                "inner_need": "承认自己害怕被遗忘",
                "arc": {"start": "拒绝合作", "turning_point": "主动共享证据", "end": "接受共同记忆"},
                "first_appearance_window": "chapter:1",
                "hard_boundaries": ["不得无证据背叛同伴"],
            }
        ],
        "relationships": [],
        "npc_slots": [],
    }


def test_stage_order_includes_independent_character_bible() -> None:
    assert STAGE_ORDER == ("info", "characters", "summary", "outline", "detail", "text", "cover", "export")


@pytest.mark.parametrize("stage_id", STAGE_ORDER)
def test_every_artifact_json_schema_requires_each_declared_core_key(stage_id: str) -> None:
    schema = ARTIFACT_MODELS[stage_id].model_json_schema()  # type: ignore[index]

    def assert_object_keys_required(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if value.get("type") == "object" and isinstance(properties, dict):
                assert set(value.get("required") or []) == set(properties), value
            for item in value.values():
                assert_object_keys_required(item)
        elif isinstance(value, list):
            for item in value:
                assert_object_keys_required(item)

    assert_object_keys_required(schema)


def test_character_bible_rejects_unknown_fields_and_relationships() -> None:
    with pytest.raises(ValidationError):
        CharacterBibleArtifact.model_validate({**character_bible(), "schema_version": "2"})
    invalid = character_bible()
    invalid["relationships"] = [
        {"source_id": "char-lin", "target_id": "char-missing", "nature": "盟友", "initial_state": "陌生", "pressure": "互不信任"}
    ]
    with pytest.raises(ValidationError, match="registered characters"):
        CharacterBibleArtifact.model_validate(invalid)


def test_character_bible_requires_a_protagonist_and_bounded_appearance_windows() -> None:
    missing_protagonist = character_bible()
    missing_protagonist["characters"][0]["tier"] = "major"  # type: ignore[index]
    with pytest.raises(ValidationError, match="at least one protagonist"):
        CharacterBibleArtifact.model_validate(missing_protagonist)

    outside_plan = character_bible()
    outside_plan["characters"][0]["first_appearance_window"] = "chapter:4"  # type: ignore[index]
    with pytest.raises(ValueError, match="frozen BookScalePlan"):
        validate_artifact_vnext(
            "characters",
            outside_plan,
            chapter_ids={"chapter-1", "chapter-2", "chapter-3"},
        )


def test_downstream_artifacts_must_reference_frozen_characters() -> None:
    summary = {
        "beats": [{"id": "beat-1", "phase": "opening", "event": "母带失踪", "consequence": "林默开始调查"}],
        "climax": "林默公开母带",
        "resolution": "港区恢复公开记忆",
        "character_outcomes": [{"character_id": "char-unknown", "outcome": "离开"}],
    }
    with pytest.raises(ValueError, match="unknown characters"):
        validate_artifact_vnext("summary", summary, character_ids={"char-lin"})

    summary["character_outcomes"] = []
    with pytest.raises(ValueError, match="missing required character outcomes"):
        validate_artifact_vnext(
            "summary",
            summary,
            character_ids={"char-lin"},
            required_outcome_character_ids={"char-lin"},
        )


def test_detail_rejects_non_contiguous_chapters_and_old_detail_keys() -> None:
    detail = {
        "chapters": [
            {
                "id": "chapter-2",
                "number": 2,
                "purpose": "找到第一条线索",
                "pov_character_id": "char-lin",
                "scenes": [{"id": "scene-1", "location": "雾港", "goal": "取回母带", "obstacle": "仓库封锁", "turn": "发现副本", "outcome": "带走副本"}],
                "obligations": [],
                "handoff": {"unresolved_actions": [], "emotional_carryover": [], "next_pressure": "追兵接近"},
                "wiki_candidates": [],
            }
        ]
    }
    with pytest.raises(ValidationError):
        validate_artifact_vnext("detail", detail, character_ids={"char-lin"})


def test_outline_requires_exact_contiguous_chapter_windows_and_known_turns() -> None:
    outline = {
        "volumes": [
            {
                "id": "volume-1",
                "chapter_window": "chapter:1-2",
                "objective": "找到母带",
                "turns": [
                    {"id": "turn-1", "event": "发现副本", "consequence": "追捕升级"}
                ],
                "ending_state": "林默带着副本逃离",
                "character_windows": [
                    {
                        "character_id": "char-lin",
                        "entry_state": "独自调查",
                        "exit_state": "决定合作",
                        "turn_id": "turn-1",
                    }
                ],
                "thread_windows": [
                    {
                        "thread_id": "thread-mother-tape",
                        "kind": "mystery",
                        "action": "确认副本存在",
                        "chapter_window": "chapter:1-2",
                    }
                ],
            }
        ]
    }
    assert validate_artifact_vnext(
        "outline",
        outline,
        character_ids={"char-lin"},
        chapter_ids={"chapter-1", "chapter-2"},
    )
    outline["volumes"][0]["chapter_window"] = "1-2"  # type: ignore[index]
    with pytest.raises(ValidationError, match="chapter:N"):
        validate_artifact_vnext(
            "outline",
            outline,
            character_ids={"char-lin"},
            chapter_ids={"chapter-1", "chapter-2"},
        )


def test_detail_keeps_pov_on_formal_cast_but_allows_frozen_npc_obligations() -> None:
    detail = {
        "chapters": [
            {
                "id": "chapter-1",
                "number": 1,
                "purpose": "取得档案",
                "pov_character_id": "char-lin",
                "scenes": [
                    {
                        "id": "scene-1",
                        "location": "档案室",
                        "goal": "取得登记簿",
                        "obstacle": "管理员拒绝交付",
                        "turn": "管理员认出母带编号",
                        "outcome": "以口供换得副本",
                    }
                ],
                "obligations": [
                    {"kind": "character", "ref_id": "npc-archivist", "action": "交付档案"}
                ],
                "handoff": {
                    "unresolved_actions": ["核对编号"],
                    "emotional_carryover": ["对口供存疑"],
                    "next_pressure": "广播站开始清理档案",
                },
            }
        ]
    }
    assert validate_artifact_vnext(
        "detail",
        detail,
        character_ids={"char-lin"},
        npc_slot_ids={"npc-archivist"},
        obligation_ref_ids={
            "character": {"char-lin", "npc-archivist"},
            "thread": set(),
            "world_rule": {"world-rule-1"},
            "promise": {"ending-promise"},
        },
        chapter_ids={"chapter-1"},
    )
    detail["chapters"][0]["pov_character_id"] = "npc-archivist"  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown POV"):
        validate_artifact_vnext(
            "detail",
            detail,
            character_ids={"char-lin"},
            npc_slot_ids={"npc-archivist"},
            chapter_ids={"chapter-1"},
        )

    detail["chapters"][0]["pov_character_id"] = "char-lin"  # type: ignore[index]
    detail["chapters"][0]["obligations"][0]["ref_id"] = "npc-invented"  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown character obligations"):
        validate_artifact_vnext(
            "detail",
            detail,
            character_ids={"char-lin"},
            npc_slot_ids={"npc-archivist"},
            obligation_ref_ids={
                "character": {"char-lin", "npc-archivist"},
                "thread": set(),
                "world_rule": {"world-rule-1"},
                "promise": {"ending-promise"},
            },
            chapter_ids={"chapter-1"},
        )
