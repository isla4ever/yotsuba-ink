from __future__ import annotations

import pytest

from novel_workflow.runtime.graph.stage_executor import (
    _bind_detail_segment_turn_refs,
    _detail_reused_titles,
    _validate_stage_unit,
)
from novel_workflow.output_contracts.artifacts_vnext import (
    DetailLayoutProposalBatch,
    DetailSegmentArtifact,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.runtime.graph.detail_planning import (
    validate_detail_layout_proposal,
)
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile


def chapter_beat(
    offset: int,
    turn_refs: list[str],
    dramatic_job: str,
    *,
    length_hint: str = "standard",
) -> dict[str, object]:
    return {
        "chapter_offset": offset,
        "turn_refs": turn_refs,
        "dramatic_job": dramatic_job,
        "length_hint": length_hint,
    }


def test_detail_unit_rejects_historical_subject_in_present_action_cast() -> None:
    context = {
        "material": {
            "selected_dossiers": [
                {
                    "id": "subject-1",
                    "kind": "protagonist",
                },
                {
                    "id": "subject-2",
                    "kind": "historical_record",
                },
            ],
            "reserved_titles": [],
            "scale_projection": {
                "volume_ref": "volume-1",
                "segment_ref": "volume-1.segment-1",
                "segment_index": 1,
                "segment_count": 1,
                "chapter_target": 1,
                "chapter_beats": [
                    chapter_beat(1, ["turn-1"], "从旧档中固定可追溯签名")
                ],
                "chapter_target_band": {
                    "preferred_characters": 2500,
                    "min_characters": 2000,
                    "max_characters": 3000,
                    "max_adjacent_delta": 375,
                    "counting_rule": "non_whitespace_characters",
                },
                "scenes_per_chapter_min": 2,
                "scenes_per_chapter_max": 4,
                "is_final_volume": True,
                "chapter_number_start": 1,
            },
        },
        "output_budget": {"scene_cap": 4},
    }
    payload = {
        "chapters": [
                {
                    "title": "旧档回声",
                    "purpose": "读取历史记录",
                "pov": "subject-1",
                "cast_ids": ["subject-1", "subject-2"],
                "scenes": [
                    {
                        "place": "档案室",
                        "objective": "读取记录",
                        "conflict": "记录受损",
                        "turn": "修复设备恢复索引",
                        "result": "索引可读",
                    },
                    {
                        "place": "修复台",
                        "objective": "核对签名",
                        "conflict": "签名模糊",
                        "turn": "校验程序锁定签名",
                        "result": "签名被固定",
                    },
                ],
                "handoff": "签名已固定，等待核查来源",
            }
        ]
    }

    with pytest.raises(ValueError, match="historical_record"):
        _validate_stage_unit("detail", "volume-1.segment-1", context, payload)


def test_detail_runtime_binds_turn_refs_after_provider_script() -> None:
    context = {
        "material": {
            "selected_dossiers": [{"id": "subject-1", "kind": "protagonist"}],
            "reserved_titles": ["档案余烬"],
            "scale_projection": {
                "volume_ref": "volume-1",
                "segment_ref": "volume-1.segment-1",
                "segment_index": 1,
                "segment_count": 1,
                "chapter_target": 1,
                "chapter_beats": [
                    chapter_beat(1, ["turn-1"], "取得副本并启动公开调查")
                ],
                "scenes_per_chapter_min": 2,
                "scenes_per_chapter_max": 4,
                "chapter_number_start": 1,
            },
        },
        "output_budget": {"scene_cap": 4},
    }
    payload = {
        "chapters": [{
            "title": "档案余烬",
            "purpose": "完成取证",
            "pov": "subject-1",
            "cast_ids": ["subject-1"],
            "scenes": [
                {"place": "档案室", "objective": "取证", "conflict": "封锁", "turn": "拿到副本", "result": "副本到手"},
                {"place": "门厅", "objective": "离开", "conflict": "警报", "turn": "冲出封锁", "result": "调查启动"},
            ],
            "handoff": "继续核查来源",
        }],
    }
    assert _detail_reused_titles(
        ["档案余烬"],
        context["material"]["reserved_titles"],
    ) == ["档案余烬"]
    _validate_stage_unit("detail", "volume-1.segment-1", context, payload)
    bound = _bind_detail_segment_turn_refs(payload, context)
    assert bound["chapters"][0]["turn_refs"] == ["turn-1"]


def test_detail_scene_counts_may_change_with_each_chapters_dramatic_load() -> None:
    context = {
        "material": {
            "selected_dossiers": [{"id": "subject-1", "kind": "protagonist"}],
            "reserved_titles": [],
            "scale_projection": {
                "volume_ref": "volume-1",
                "segment_ref": "volume-1.segment-1",
                "segment_index": 1,
                "segment_count": 1,
                "chapter_target": 2,
                "chapter_beats": [
                    chapter_beat(1, ["turn-1"], "让申请被留置复核"),
                    chapter_beat(2, ["turn-1"], "完成跨地点证据核验"),
                ],
                "scenes_per_chapter_min": 1,
                "scenes_per_chapter_max": 4,
                "chapter_number_start": 1,
            },
        },
        "output_budget": {"scene_cap": 4},
    }

    def scene(index: int) -> dict[str, str]:
        return {
            "place": f"场所{index}",
            "objective": f"目标{index}",
            "conflict": f"阻力{index}",
            "turn": f"转折{index}",
            "result": f"结果{index}",
        }

    payload = {
        "chapters": [
            {
                "title": "孤灯受理",
                "purpose": "用一场重戏建立受理压力",
                "pov": "subject-1",
                "cast_ids": ["subject-1"],
                "scenes": [scene(1)],
                "handoff": "申请被留置复核",
            },
            {
                "title": "四处核验",
                "purpose": "在多个时空单元里完成证据核验",
                "pov": "subject-1",
                "cast_ids": ["subject-1"],
                "scenes": [scene(index) for index in range(2, 6)],
                "handoff": "核验结果进入下一章",
            },
        ]
    }

    _validate_stage_unit("detail", "volume-1.segment-1", context, payload)


def test_detail_script_contract_rejects_prose_scale_chapter_cards() -> None:
    scene = {
        "place": "档案室" * 20,
        "objective": "核对记录" * 20,
        "conflict": "索引受损，时间正在流失" * 20,
        "turn": "程序锁定一条可追溯的签名" * 20,
        "result": "证据进入保全链，但来源仍未确认" * 20,
    }
    with pytest.raises(ValueError, match="target_characters is prose budget metadata only"):
        DetailSegmentArtifact.model_validate(
            {
                "chapters": [
                    {
                        "title": "档案余烬",
                        "purpose": "完成本章取证" * 20,
                        "pov": "subject-1",
                        "cast_ids": ["subject-1"],
                        "scenes": [scene, scene.copy()],
                        "handoff": "证据已保全，下一章核对来源" * 20,
                    }
                ]
            }
        )


def detail_planning_artifacts() -> tuple[VolumeArchitectureArtifact, StorySpineArtifact]:
    architecture = VolumeArchitectureArtifact.model_validate(
        {
            "volumes": [
                {
                    "id": "volume-1",
                    "title": "潮痕卷",
                    "promise": "找到母带来源",
                        "conflict": "档案系统持续删除证据",
                        "climax": "主角公开母带",
                        "climax_turn_ref": "turn-2",
                    "closure": "旧案重启",
                    "turn_refs": ["turn-1", "turn-2"],
                    "cast_ids": ["subject-1"],
                    "length_hint": "medium",
                }
            ]
        }
    )
    spine = StorySpineArtifact.model_validate(
        {
            "turns": [
                {"id": "turn-1", "cause": "母带被删", "change": "主角开始调查", "progress_type": "information", "milestones": ["inciting", "commitment", "midpoint_reversal", "crisis", "climax"]},
                {"id": "turn-2", "cause": "调查取得签名", "change": "旧案正式重启", "progress_type": "external", "milestones": ["aftermath"]},
            ],
            "ending": "删除责任被追究",
            "open_questions": [],
            "progress_types": ["information", "external"],
        }
    )
    return architecture, spine


def test_detail_layout_accepts_multiple_distinct_chapter_jobs_for_one_turn() -> None:
    architecture, spine = detail_planning_artifacts()
    layout = DetailLayoutProposalBatch.model_validate(
        {
            "status": "sufficient",
            "diagnosis": "",
            "volumes": [
                {
                    "volume_ref": "volume-1",
                    "chapters": [
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "让删除事实变成主角无法回避的职业风险",
                            "length_hint": "compact",
                        },
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "迫使主角公开选择继续调查",
                            "length_hint": "standard",
                        },
                        {
                            "turn_refs": ["turn-2"],
                            "dramatic_job": "用签名证据触发旧案重启",
                            "length_hint": "expansive",
                        },
                    ],
                }
            ],
        }
    )

    validate_detail_layout_proposal(
        layout,
        architecture=architecture,
        spine=spine,
        profile=NarrativeScaleProfile(word_target_soft=7_500),
    )


def test_detail_layout_rejects_repeated_dramatic_jobs() -> None:
    architecture, spine = detail_planning_artifacts()
    layout = DetailLayoutProposalBatch.model_validate(
        {
            "status": "sufficient",
            "diagnosis": "",
            "volumes": [
                {
                    "volume_ref": "volume-1",
                    "chapters": [
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "重复提交申请",
                            "length_hint": "compact",
                        },
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "重复提交申请",
                            "length_hint": "standard",
                        },
                        {
                            "turn_refs": ["turn-2"],
                            "dramatic_job": "触发旧案重启",
                            "length_hint": "expansive",
                        },
                    ],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="repeats a dramatic job"):
        validate_detail_layout_proposal(
            layout,
            architecture=architecture,
            spine=spine,
            profile=NarrativeScaleProfile(word_target_soft=7_500),
        )


def test_detail_layout_rejects_a_missing_causal_turn() -> None:
    architecture, spine = detail_planning_artifacts()
    layout = DetailLayoutProposalBatch.model_validate(
        {
            "status": "sufficient",
            "diagnosis": "",
            "volumes": [
                {
                    "volume_ref": "volume-1",
                    "chapters": [
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "让删除事实造成职业风险",
                            "length_hint": "standard",
                        },
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "迫使主角选择继续调查",
                            "length_hint": "standard",
                        },
                        {
                            "turn_refs": ["turn-1"],
                            "dramatic_job": "让主角承担公开调查的职业后果",
                            "length_hint": "expansive",
                        },
                    ],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="cover every volume-1 turn"):
        validate_detail_layout_proposal(
            layout,
            architecture=architecture,
            spine=spine,
            profile=NarrativeScaleProfile(word_target_soft=7_500),
        )
