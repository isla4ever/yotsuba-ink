from __future__ import annotations

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.artifacts_vnext import (
    ARTIFACT_MODELS,
    CharacterBibleArtifact,
    CharacterDossierBatch,
    CharacterRelation,
    DetailScene,
    DetailLayoutProposalBatch,
    RoleDemandProposalBatch,
    STAGE_ORDER,
    VolumeArchitectureUnitArtifact,
    validate_artifact_vnext,
    validate_character_dossier_modes,
    validate_detail_scene_quality,
    validate_detail_writeback_identity,
)


def cast() -> dict[str, object]:
    return {
        "subjects": [{
            "id": "subject-lin",
            "name": "林默",
            "kind": "protagonist",
            "function": "承担取证",
            "background": "旧港公共档案修复师，母亲失踪案与她的职业记录相互冲突。",
            "conflict_history": "她曾参与旧港事故档案的初次修复，亲眼见过母带被替换。",
            "present_stakes": "若证据失效，她会失去职业资格并放弃母亲的去向。",
            "temperament": "受压时先核对事实，再逼迫对方明确选择。",
            "speech_style": "短句，少用判断词，常复述记录原文。",
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


def test_role_demand_requires_an_explicit_subject_mode() -> None:
    proposal = {
        "demand_key": "demand-witness",
        "function": "让证词在当下改变案件走向",
        "required_change": "证词从私人记忆变为公开证据",
        "active_turn_refs": ["turn-3"],
    }

    with pytest.raises(ValidationError, match="subject_mode"):
        RoleDemandProposalBatch.model_validate({"proposals": [proposal]})
    historical = RoleDemandProposalBatch.model_validate(
        {
            "proposals": [
                {
                    "demand_key": "demand-protagonist",
                    "subject_mode": "actor",
                    "narrative_role": "protagonist",
                    "function": "公开追查被替换的事故母带",
                    "required_change": "从私人核验转向承担公开指证后果",
                    "irreducibility": "她必须决定公开自己的违规修复记录并承担职业资格被撤销的后果。",
                    "active_turn_refs": ["turn-1", "turn-3"],
                },
                {
                    **proposal,
                    "subject_mode": "historical_record",
                    "narrative_role": "historical_record",
                    "irreducibility": "这份历史证词必须保持同一身份，不能并入现存调查者。",
                },
            ]
        }
    )
    assert historical.proposals[1].subject_mode == "historical_record"


@pytest.mark.parametrize(
    "irreducibility",
    [
        "不能合并到其他角色",
        "该角色不可替代",
        "剧情需要这个角色",
        "为了丰富剧情",
    ],
)
def test_role_demand_rejects_vague_irreducibility(irreducibility: str) -> None:
    with pytest.raises(ValidationError, match="concrete choice, pressure, or consequence"):
        RoleDemandProposalBatch.model_validate(
            {
                "proposals": [
                    {
                        "demand_key": "demand-protagonist",
                        "subject_mode": "actor",
                        "narrative_role": "protagonist",
                        "function": "公开追查被替换的事故母带",
                        "required_change": "从私人核验转向承担公开指证后果",
                        "irreducibility": irreducibility,
                        "active_turn_refs": ["turn-1", "turn-3"],
                    }
                ]
            }
        )


def test_role_demand_batch_rejects_multiple_protagonists_and_duplicate_functions() -> None:
    protagonist = {
        "subject_mode": "actor",
        "narrative_role": "protagonist",
        "function": "公开追查被替换的事故母带",
        "required_change": "从私人核验转向承担公开指证后果",
        "irreducibility": "此人必须公开自己的违规修复记录并承担职业资格被撤销的后果。",
        "active_turn_refs": ["turn-1", "turn-3"],
    }
    with pytest.raises(ValidationError, match="exactly one protagonist"):
        RoleDemandProposalBatch.model_validate(
            {
                "proposals": [
                    {"demand_key": "demand-protagonist-a", **protagonist},
                    {"demand_key": "demand-protagonist-b", **protagonist},
                ]
            }
        )

    with pytest.raises(ValidationError, match="duplicate functions"):
        RoleDemandProposalBatch.model_validate(
            {
                "proposals": [
                    {"demand_key": "demand-protagonist", **protagonist},
                    {
                        "demand_key": "demand-witness",
                        **protagonist,
                        "narrative_role": "relationship",
                        "irreducibility": "证人必须选择撤回实名授权，使主角失去公开证据并改变合作关系。",
                    },
                ]
            }
        )


def test_role_demand_batch_rejects_duplicate_required_changes() -> None:
    base = {
        "subject_mode": "actor",
        "required_change": "从回避风险转为承担公开后果",
        "irreducibility": "必须独立作出公开选择并承担职业资格被撤销的后果。",
        "active_turn_refs": ["turn-1", "turn-3"],
    }
    with pytest.raises(ValidationError, match="duplicate required changes"):
        RoleDemandProposalBatch.model_validate(
            {
                "proposals": [
                    {
                        "demand_key": "demand-protagonist",
                        "narrative_role": "protagonist",
                        "function": "公开追查被替换的事故母带",
                        **base,
                    },
                    {
                        "demand_key": "demand-witness",
                        "narrative_role": "relationship",
                        "function": "决定是否撤回实名证词",
                        **base,
                    },
                ]
            }
        )


def test_detail_scene_quality_rejects_pure_cognition_and_repeated_work() -> None:
    with pytest.raises(ValidationError, match="visible action"):
        DetailScene.model_validate(
            {
                "place": "档案室",
                "objective": "取证",
                "conflict": "封锁",
                "turn": "意识到签名被替换",
                "result": "拿到副本",
            }
        )
    scenes = [
        DetailScene.model_validate(
            {
                "place": "档案室",
                "objective": "取证",
                "conflict": "封锁",
                "turn": "打开保全柜",
                "result": "拿到副本",
            }
        ),
        DetailScene.model_validate(
            {
                "place": "门厅",
                "objective": "取证",
                "conflict": "广播拦截",
                "turn": "关闭广播",
                "result": "副本带出现场",
            }
        ),
    ]
    with pytest.raises(ValueError, match="repeated scene work"):
        validate_detail_scene_quality(scenes)

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("background", "暂无具体背景，需要后续创作时再补充。"),
        ("conflict_history", "尚未确定与核心冲突的既往联系。"),
        ("present_stakes", "未知，等待剧情进一步发展后决定。"),
        ("temperament", "性格复杂。。。。"),
        ("speech_style", "待补充具体的语言和表达习惯。"),
        ("background", "他有一段神秘的过去，具体身份和经历来历成谜。"),
        ("present_stakes", "如果失败，他将付出代价并面临严重后果。"),
    ],
)
def test_character_dossier_rejects_padded_vague_fields(field: str, value: str) -> None:
    dossier = {
        "name": "林秋蘅",
        "kind": "major",
        "function": "在公开听证前决定是否撤回实名证词",
        "background": "旧港广播站值守员，事故当夜负责切换备用信号。",
        "conflict_history": "她曾按命令删除一段值守记录，因此一直回避公开作证。",
        "present_stakes": "若实名证词公开，她会失去广播站职位并承担违规删除责任。",
        "temperament": "压力越大越依赖程序用语，真正下决定前会反复确认退路。",
        "speech_style": "措辞正式，长句较多，犹豫时会重复对方问题。",
        "drive": "保护广播站的同事",
        "change": "从自保沉默转向公开承担证词后果",
        "debut": "chapter:2-3",
        "limits": ["不得无因撤回已经公开的证词"],
        "demand_refs": ["demand-witness"],
    }
    dossier[field] = value

    with pytest.raises(ValidationError, match="concrete enough to perform"):
        CharacterDossierBatch.model_validate({"subjects": [dossier]})


def test_character_dossier_rejects_placeholder_limits() -> None:
    payload = cast()["subjects"][0]  # type: ignore[index]
    dossier = {key: value for key, value in payload.items() if key != "id"}  # type: ignore[union-attr]
    dossier["limits"] = ["无特殊限制"]

    with pytest.raises(ValidationError, match="concrete narrative boundary"):
        CharacterDossierBatch.model_validate({"subjects": [dossier]})


@pytest.mark.parametrize(
    ("subject_mode", "kind", "message"),
    [
        ("historical_record", "major", "must produce a historical_record"),
        ("actor", "historical_record", "actor demand cannot produce"),
    ],
)
def test_cast_dossier_kind_must_match_the_frozen_subject_mode(
    subject_mode: str,
    kind: str,
    message: str,
) -> None:
    dossiers = CharacterDossierBatch.model_validate(
        {
            "subjects": [
                {
                    "name": "林秋蘅",
                    "kind": kind,
                    "function": "以旧录音改变当下证词判断",
                        "background": "事故前负责保存原始录音，死亡后只留下可验证记录。",
                        "conflict_history": "她保存的原始录音是旧案唯一未被改写的来源。",
                        "present_stakes": "证词一旦失去可信度，遗留记录将被永久封存。",
                    "temperament": "生前谨慎，坚持所有修改保留异议。",
                    "speech_style": "录音中用词准确，句子短，不作情绪总结。",
                    "drive": "保留未经校准的原始声音",
                    "change": "录音从家庭遗物变成公开证据",
                    "debut": "chapter:4",
                    "limits": ["历史主体不得产生当下行动"],
                    "demand_refs": ["demand-mother-record"],
                }
            ]
        }
    )

    with pytest.raises(ValueError, match=message):
        validate_character_dossier_modes(
            dossiers,
            [
                {
                    "id": "subject-1",
                    "demand_key": "demand-mother-record",
                    "subject_mode": subject_mode,
                    "narrative_role": (
                        "historical_record"
                        if subject_mode == "historical_record"
                        else "opposition"
                    ),
                }
            ],
        )
    correct_kind = "historical_record" if subject_mode == "historical_record" else "major"
    corrected = dossiers.model_copy(
        update={
            "subjects": [
                dossiers.subjects[0].model_copy(update={"kind": correct_kind})
            ]
        }
    )
    validate_character_dossier_modes(
        corrected,
        [
            {
                "id": "subject-1",
                "demand_key": "demand-mother-record",
                "subject_mode": subject_mode,
                "narrative_role": (
                    "historical_record"
                    if subject_mode == "historical_record"
                    else "opposition"
                ),
            }
        ],
    )


@pytest.mark.parametrize("title", ["待定书名", "未命名作品", "untitled", "TBD"])
def test_story_brief_rejects_placeholder_book_titles(title: str) -> None:
    payload = {
        "title": title,
        "premise": "修表匠发现城市每天丢失一分钟。",
        "promise": "追查失时机制。",
        "world_rules": ["失去的时间不会留下公共记录"],
        "theme": "记忆与责任",
        "ending_promise": "失时机制将得到回答。",
        "voice": "第三人称限知",
        "length_envelope": {"word_target_soft": 100_000},
    }
    with pytest.raises(ValidationError, match="real book title"):
        validate_artifact_vnext("brief", payload)


@pytest.mark.parametrize("stage_id", STAGE_ORDER)
def test_every_artifact_schema_forbids_unknown_keys(stage_id: str) -> None:
    schema = ARTIFACT_MODELS[stage_id].model_json_schema()  # type: ignore[index]
    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False


def test_detail_layout_insufficient_state_requires_a_diagnosis_without_chapters() -> None:
    result = DetailLayoutProposalBatch.model_validate(
        {
            "status": "insufficient",
            "diagnosis": "第二卷只有一个可逆程序动作，无法支撑合理最低章数",
            "volumes": [],
        }
    )

    assert result.status == "insufficient"
    with pytest.raises(ValidationError, match="requires a capacity diagnosis"):
        DetailLayoutProposalBatch.model_validate(
            {"status": "insufficient", "diagnosis": "", "volumes": []}
        )


def test_detail_layout_sufficient_state_cannot_omit_volume_plans() -> None:
    with pytest.raises(ValidationError, match="must contain volume plans"):
        DetailLayoutProposalBatch.model_validate(
            {"status": "sufficient", "diagnosis": "", "volumes": []}
        )


def test_detail_layout_sufficient_state_cannot_report_unverified_counts() -> None:
    with pytest.raises(ValidationError, match="keep diagnosis empty"):
        DetailLayoutProposalBatch.model_validate(
            {
                "status": "sufficient",
                "diagnosis": "第一卷 14 章，全书 40 章",
                "volumes": [
                    {
                        "volume_ref": "volume-1",
                        "chapters": [
                            {
                                "turn_refs": ["turn-1"],
                                "dramatic_job": "让证据改变公开程序",
                                "length_hint": "standard",
                            }
                        ],
                    }
                ],
            }
        )


def test_character_bible_freezes_subject_registry_and_rejects_unknown_relation() -> None:
    with pytest.raises(ValidationError):
        CharacterBibleArtifact.model_validate({**cast(), "extra": True})
    invalid = cast()
    invalid["relations"] = [{"a": "subject-lin", "b": "subject-missing", "type": "盟友", "pressure": "互不信任"}]
    with pytest.raises(ValidationError, match="registered subjects"):
        CharacterBibleArtifact.model_validate(invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "潜在盟友"),
        ("pressure", "两人可能在公开听证前建立信任"),
    ],
)
def test_character_relation_rejects_ambiguous_pressure(field: str, value: str) -> None:
    relation = {
        "a": "subject-lin",
        "b": "subject-witness",
        "type": "互相担保",
        "pressure": "林默公开记录会使证人失去撤回证词的最后机会",
    }
    relation[field] = value

    with pytest.raises(ValidationError, match="established, concrete relationship pressure"):
        CharacterRelation.model_validate(relation)


def test_character_bible_requires_protagonist_and_covers_role_demands() -> None:
    no_protagonist = cast()
    no_protagonist["subjects"][0]["kind"] = "major"  # type: ignore[index]
    with pytest.raises(ValidationError, match="protagonist"):
        CharacterBibleArtifact.model_validate(no_protagonist)
    with pytest.raises(ValueError, match="does not cover"):
        validate_artifact_vnext("cast", cast(), demand_keys={"demand-investigator", "demand-witness"})


def test_character_bible_rejects_duplicate_names_even_when_subject_ids_differ() -> None:
    duplicated = cast()
    duplicated["subjects"].append(  # type: ignore[union-attr]
        {
            **duplicated["subjects"][0],  # type: ignore[index]
            "id": "subject-lin-copy",
            "kind": "major",
            "demand_refs": ["demand-witness"],
        }
    )

    with pytest.raises(ValidationError, match="names must be unique"):
        CharacterBibleArtifact.model_validate(duplicated)


def test_character_bible_edit_must_preserve_the_exact_frozen_subject_registry() -> None:
    frozen = {"subject-lin", "subject-witness"}
    with pytest.raises(ValueError, match="registry must match"):
        validate_artifact_vnext("cast", cast(), subject_ids=frozen)

    added = cast()
    added["subjects"].append(  # type: ignore[union-attr]
        {
                **added["subjects"][0],  # type: ignore[index]
                "id": "subject-extra",
                "name": "额外证人",
                "kind": "major",
        }
    )
    with pytest.raises(ValueError, match="registry must match"):
        validate_artifact_vnext("cast", added, subject_ids={"subject-lin"})


def test_character_debut_windows_fit_the_dynamic_chapter_range_minimum() -> None:
    assert validate_artifact_vnext("cast", cast(), chapter_target=45)
    outside = cast()
    outside["subjects"][0]["debut"] = "chapter:44-46"  # type: ignore[index]

    with pytest.raises(ValueError, match="debut windows exceed"):
        validate_artifact_vnext("cast", outside, chapter_target=45)


def test_volume_contract_references_known_subjects_and_turns() -> None:
    volume = {"volumes": [{"id": "volume-1", "title": "雾港残响", "promise": "找到母带", "conflict": "证据被删", "climax": "公开母带", "climax_turn_ref": "turn-1", "closure": "真相公开", "turn_refs": ["turn-1"], "cast_ids": ["subject-lin"], "length_hint": "short"}]}
    assert validate_artifact_vnext("volumes", volume, subject_ids={"subject-lin"}, turn_ids={"turn-1"})
    with pytest.raises(ValueError, match="unknown spine turns"):
        validate_artifact_vnext("volumes", {"volumes": [{**volume["volumes"][0], "turn_refs": ["turn-2"], "climax_turn_ref": "turn-2"}]}, subject_ids={"subject-lin"}, turn_ids={"turn-1"})
    with pytest.raises(ValidationError, match="thread_ids"):
        validate_artifact_vnext(
            "volumes",
            {"volumes": [{**volume["volumes"][0], "thread_ids": ["turn-1"]}]},
        )


def test_volume_provider_unit_schema_allows_exactly_one_contract() -> None:
    schema = VolumeArchitectureUnitArtifact.model_json_schema()
    volumes = schema["properties"]["volumes"]
    assert volumes["minItems"] == 1
    assert volumes["maxItems"] == 1


def test_detail_requires_exact_frozen_chapter_refs_and_formal_cast() -> None:
    detail = {"chapters": [{"ref": "chapter-1", "volume_ref": "volume-1", "title": "档案余烬", "target_characters": 3000, "turn_refs": ["turn-1"], "purpose": "取得母带", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移副本", "conflict": "出口被封", "turn": "找到暗门", "result": "带走副本"}], "handoff": "追查签名"}]}
    assert validate_artifact_vnext("detail", detail, subject_ids={"subject-lin"}, chapter_refs={"chapter-1"}, volume_cast_ids={"volume-1": {"subject-lin"}})
    with pytest.raises(ValueError, match="match the frozen chapter refs"):
        validate_artifact_vnext("detail", detail, subject_ids={"subject-lin"}, chapter_refs={"chapter-2"})
    outside_volume = {"chapters": [{**detail["chapters"][0], "cast_ids": ["subject-lin", "subject-zhou"]}]}
    with pytest.raises(ValueError, match="outside volume-1"):
        validate_artifact_vnext("detail", outside_volume, subject_ids={"subject-lin", "subject-zhou"}, volume_cast_ids={"volume-1": {"subject-lin"}})
    with pytest.raises(ValidationError, match="include its POV"):
        validate_artifact_vnext("detail", {"chapters": [{**detail["chapters"][0], "cast_ids": ["subject-zhou"]}]})
    with pytest.raises(ValueError, match="historical subjects"):
        validate_artifact_vnext(
            "detail",
            detail,
            historical_subject_ids={"subject-lin"},
        )


def test_detail_schema_accepts_projection_owned_scene_counts() -> None:
    scene = {
        "place": "档案室",
        "objective": "取证",
        "conflict": "封锁",
        "turn": "发现签名",
        "result": "拿到副本",
    }
    payload = {
        "chapters": [{
            "ref": "chapter-1",
            "volume_ref": "volume-1",
            "title": "六段取证",
            "target_characters": 3000,
            "turn_refs": ["turn-1"],
            "purpose": "完成一段连续取证",
            "pov": "subject-lin",
            "cast_ids": ["subject-lin"],
            "scenes": [scene for _ in range(6)],
            "handoff": "证据进入保全链",
        }],
    }

    artifact = validate_artifact_vnext(
        "detail",
        payload,
        subject_ids={"subject-lin"},
        chapter_refs={"chapter-1"},
        volume_cast_ids={"volume-1": {"subject-lin"}},
    )

    assert len(artifact.chapters[0].scenes) == 6


def test_detail_schema_does_not_force_adjacent_chapters_to_use_similar_scene_counts() -> None:
    scene = {
        "place": "档案室",
        "objective": "取证",
        "conflict": "封锁",
        "turn": "发现签名",
        "result": "拿到副本",
    }
    chapters = [
        {
            "ref": "chapter-1",
            "volume_ref": "volume-1",
            "title": "孤灯受理",
            "target_characters": 2500,
            "turn_refs": ["turn-1"],
            "purpose": "用一场重戏建立受理压力",
            "pov": "subject-lin",
            "cast_ids": ["subject-lin"],
            "scenes": [scene],
            "handoff": "申请被留置复核",
        },
        {
            "ref": "chapter-2",
            "volume_ref": "volume-1",
            "title": "四处核验",
            "target_characters": 2500,
            "turn_refs": ["turn-1"],
            "purpose": "通过四个时空单元完成核验",
            "pov": "subject-lin",
            "cast_ids": ["subject-lin"],
            "scenes": [scene for _ in range(4)],
            "handoff": "核验结果进入下一章",
        },
    ]

    artifact = validate_artifact_vnext(
        "detail",
        {"chapters": chapters},
        subject_ids={"subject-lin"},
        chapter_refs={"chapter-1", "chapter-2"},
        volume_cast_ids={"volume-1": {"subject-lin"}},
    )

    assert [len(chapter.scenes) for chapter in artifact.chapters] == [1, 4]


def test_detail_turn_refs_are_checked_against_frozen_chapter_beats() -> None:
    detail = {
        "chapters": [{
            "ref": "chapter-1",
            "volume_ref": "volume-1",
            "title": "档案余烬",
            "target_characters": 3000,
            "turn_refs": ["turn-1"],
            "purpose": "取得母带",
            "pov": "subject-lin",
            "cast_ids": ["subject-lin"],
            "scenes": [
                {"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"},
                {"place": "旧潮道", "objective": "转移副本", "conflict": "出口被封", "turn": "找到暗门", "result": "带走副本"},
            ],
            "handoff": "追查签名",
        }],
    }
    assert validate_artifact_vnext(
        "detail",
        detail,
        chapter_turn_refs={"chapter-1": ["turn-1"]},
    )
    with pytest.raises(ValueError, match="turn bindings"):
        validate_artifact_vnext(
            "detail",
            {"chapters": [{**detail["chapters"][0], "turn_refs": ["turn-2"]}]},
            chapter_turn_refs={"chapter-1": ["turn-1"]},
        )


@pytest.mark.parametrize(
    "title",
    ["第一章", "第1章 雾起", "第1章雾起", "Chapter 2", "Chapter 2A"],
)
def test_numbered_chapter_placeholders_are_rejected(title: str) -> None:
    detail = {"chapters": [{"ref": "chapter-1", "volume_ref": "volume-1", "title": title, "target_characters": 3000, "turn_refs": ["turn-1"], "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移", "conflict": "追捕", "turn": "找到出口", "result": "离开"}], "handoff": "继续追查"}]}
    with pytest.raises(ValidationError, match="creative title"):
        validate_artifact_vnext("detail", detail)


def test_volume_titles_are_unique_while_reused_chapter_titles_remain_editable() -> None:
    duplicate_volumes = {"volumes": [
        {"id": f"volume-{index}", "title": "雾港残响", "promise": "p", "conflict": "c", "climax": "x", "climax_turn_ref": f"turn-{index}", "closure": "z", "turn_refs": [f"turn-{index}"], "cast_ids": ["subject-lin"], "length_hint": "short"}
        for index in (1, 2)
    ]}
    with pytest.raises(ValidationError, match="titles must be unique"):
        validate_artifact_vnext("volumes", duplicate_volumes)

    base = {"volume_ref": "volume-1", "title": "档案余烬", "target_characters": 3000, "turn_refs": ["turn-1"], "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移", "conflict": "追捕", "turn": "找到出口", "result": "离开"}], "handoff": "继续追查"}
    duplicate_chapters = {"chapters": [{"ref": f"chapter-{index}", **base} for index in (1, 2)]}
    detail = validate_artifact_vnext("detail", duplicate_chapters)
    assert [chapter.title for chapter in detail.chapters] == ["档案余烬", "档案余烬"]


def test_detail_writeback_cannot_change_code_owned_budget_or_volume() -> None:
    source = validate_artifact_vnext("detail", {"chapters": [{"ref": "chapter-1", "volume_ref": "volume-1", "title": "档案余烬", "target_characters": 3000, "turn_refs": ["turn-1"], "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [{"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}, {"place": "旧潮道", "objective": "转移", "conflict": "追捕", "turn": "找到出口", "result": "离开"}], "handoff": "继续追查"}]})
    candidate = source.model_copy(deep=True)
    candidate.chapters[0].title = "暗门余温"
    validate_detail_writeback_identity(source, candidate)
    candidate.chapters[0].target_characters = 6000
    with pytest.raises(ValueError, match="code-owned"):
        validate_detail_writeback_identity(source, candidate)
    candidate = source.model_copy(deep=True)
    candidate.chapters[0].turn_refs = ["turn-2"]
    with pytest.raises(ValueError, match="code-owned"):
        validate_detail_writeback_identity(source, candidate)


def test_detail_rejects_extreme_or_abrupt_chapter_target_gaps() -> None:
    scene = {"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "发现签名", "result": "拿到副本"}
    base = {"volume_ref": "volume-1", "turn_refs": ["turn-1"], "purpose": "取证", "pov": "subject-lin", "cast_ids": ["subject-lin"], "scenes": [scene, scene], "handoff": "继续追查"}

    with pytest.raises(ValidationError, match="within 10%"):
        validate_artifact_vnext("detail", {"chapters": [
            {"ref": "chapter-1", "title": "档案余烬", "target_characters": 2400, **base},
            {"ref": "chapter-2", "title": "暗门余温", "target_characters": 3600, **base},
        ]})

    with pytest.raises(ValidationError, match="rhythm band"):
        validate_artifact_vnext("detail", {"chapters": [
            {"ref": "chapter-1", "title": "档案余烬", "target_characters": 2700, **base},
            {"ref": "chapter-2", "title": "暗门余温", "target_characters": 3300, **base},
        ]})
