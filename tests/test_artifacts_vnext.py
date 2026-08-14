from __future__ import annotations

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.artifacts_vnext import (
    ARTIFACT_MODELS,
    CharacterBibleArtifact,
    STAGE_ORDER,
    validate_artifact_vnext,
    validate_detail_writeback_identity,
)


def cast() -> dict[str, object]:
    return {
        "subjects": [{
            "id": "subject-lin",
            "name": "林默",
            "kind": "protagonist",
            "function": "承担取证",
            "drive": "找到母带",
            "change": "从独自调查转向公开真相",
            "debut": "chapter:1",
            "limits": ["不得无证据背叛同伴"],
            "demand_refs": ["demand-investigator"],
        }],
        "relations": [],
    }


def test_phase27_stage_order_is_the_only_production_order() -> None:
    assert STAGE_ORDER == ("brief", "spine", "cast", "volumes", "detail", "text", "cover", "export")


@pytest.mark.parametrize("stage_id", STAGE_ORDER)
def test_every_artifact_schema_forbids_unknown_keys(stage_id: str) -> None:
    schema = ARTIFACT_MODELS[stage_id].model_json_schema()  # type: ignore[index]
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False


def test_character_bible_freezes_subject_registry_and_rejects_unknown_relation() -> None:
    with pytest.raises(ValidationError):
        CharacterBibleArtifact.model_validate({**cast(), "extra": True})
    invalid = cast()
    invalid["relations"] = [{"a": "subject-lin", "b": "subject-missing", "type": "盟友", "pressure": "互不信任"}]
    with pytest.raises(ValidationError, match="registered subjects"):
        CharacterBibleArtifact.model_validate(invalid)


def test_character_bible_requires_protagonist_and_covers_role_demands() -> None:
    no_protagonist = cast()
    no_protagonist["subjects"][0]["kind"] = "major"  # type: ignore[index]
    with pytest.raises(ValidationError, match="protagonist"):
        CharacterBibleArtifact.model_validate(no_protagonist)
    with pytest.raises(ValueError, match="does not cover"):
        validate_artifact_vnext("cast", cast(), demand_keys={"demand-investigator", "demand-witness"})


def test_volume_contract_references_known_subjects_and_turns() -> None:
    volume = {"volumes": [{"id": "volume-1", "title": "雾港残响", "promise": "找到母带", "conflict": "证据被删", "climax": "公开母带", "closure": "真相公开", "turn_refs": ["turn-1"], "cast_ids": ["subject-lin"], "thread_ids": [], "length_hint": "short"}]}
    assert validate_artifact_vnext("volumes", volume, subject_ids={"subject-lin"}, turn_ids={"turn-1"})
    with pytest.raises(ValueError, match="unknown spine turns"):
        validate_artifact_vnext("volumes", {"volumes": [{**volume["volumes"][0], "turn_refs": ["turn-x"]}]}, subject_ids={"subject-lin"}, turn_ids={"turn-1"})


def test_detail_requires_exact_frozen_chapter_refs_and_formal_cast() -> None:
    detail = {"chapters": [{"ref": "chapter-1", "volume_ref": "volume-1", "title": "档案余烬", "target_characters": 3000, "purpose": "取得母带", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移副本", "conflict": "出口被封", "turn": "找到暗门", "result": "带走副本"}], "handoff": "追查签名"}]}
    assert validate_artifact_vnext("detail", detail, subject_ids={"subject-lin"}, chapter_refs={"chapter-1"}, volume_cast_ids={"volume-1": {"subject-lin"}})
    with pytest.raises(ValueError, match="match the frozen chapter refs"):
        validate_artifact_vnext("detail", detail, subject_ids={"subject-lin"}, chapter_refs={"chapter-2"})
    outside_volume = {"chapters": [{**detail["chapters"][0], "cast_ids": ["subject-lin", "subject-zhou"]}]}
    with pytest.raises(ValueError, match="outside volume-1"):
        validate_artifact_vnext("detail", outside_volume, subject_ids={"subject-lin", "subject-zhou"}, volume_cast_ids={"volume-1": {"subject-lin"}})
    with pytest.raises(ValidationError, match="include its POV"):
        validate_artifact_vnext("detail", {"chapters": [{**detail["chapters"][0], "cast_ids": ["subject-zhou"]}]})


@pytest.mark.parametrize(
    "title",
    ["第一章", "第1章 雾起", "第1章雾起", "Chapter 2", "Chapter 2A"],
)
def test_numbered_chapter_placeholders_are_rejected(title: str) -> None:
    detail = {"chapters": [{"ref": "chapter-1", "volume_ref": "volume-1", "title": title, "target_characters": 3000, "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移", "conflict": "追捕", "turn": "找到出口", "result": "离开"}], "handoff": "继续追查"}]}
    with pytest.raises(ValidationError, match="creative title"):
        validate_artifact_vnext("detail", detail)


def test_volume_and_chapter_titles_are_unique_across_the_whole_artifact() -> None:
    duplicate_volumes = {"volumes": [
        {"id": f"volume-{index}", "title": "雾港残响", "promise": "p", "conflict": "c", "climax": "x", "closure": "z", "turn_refs": [f"turn-{index}"], "cast_ids": ["subject-lin"], "thread_ids": [], "length_hint": "short"}
        for index in (1, 2)
    ]}
    with pytest.raises(ValidationError, match="titles must be unique"):
        validate_artifact_vnext("volumes", duplicate_volumes)

    base = {"volume_ref": "volume-1", "title": "档案余烬", "target_characters": 3000, "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移", "conflict": "追捕", "turn": "找到出口", "result": "离开"}], "handoff": "继续追查"}
    duplicate_chapters = {"chapters": [{"ref": f"chapter-{index}", **base} for index in (1, 2)]}
    with pytest.raises(ValidationError, match="titles must be unique"):
        validate_artifact_vnext("detail", duplicate_chapters)


def test_detail_writeback_cannot_change_code_owned_budget_or_volume() -> None:
    source = validate_artifact_vnext("detail", {"chapters": [{"ref": "chapter-1", "volume_ref": "volume-1", "title": "档案余烬", "target_characters": 3000, "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移", "conflict": "追捕", "turn": "找到出口", "result": "离开"}], "handoff": "继续追查"}]})
    candidate = source.model_copy(deep=True)
    candidate.chapters[0].title = "暗门余温"
    validate_detail_writeback_identity(source, candidate)
    candidate.chapters[0].target_characters = 6000
    with pytest.raises(ValueError, match="code-owned"):
        validate_detail_writeback_identity(source, candidate)
