from __future__ import annotations

from novel_workflow.runtime.graph.provider_contract_compiler import (
    schema_for_proposal,
    schema_for_stage,
    schema_with_frozen_context_bounds,
)
from novel_workflow.runtime.graph.provider_input_compiler import compile_provider_input
from novel_workflow.runtime.graph.provider_requests import ProposalGenerationRequest, StageGenerationRequest
from tests.phase27_bindings import provider_binding


def test_spine_schema_uses_the_frozen_turn_capacity() -> None:
    base = schema_for_stage("spine")
    effective = schema_with_frozen_context_bounds(
        "spine",
        base,
        {
            "material": {
                "scale_plan": {
                    "turn_target": 27,
                    "turn_capacity_range": [23, 34],
                }
            }
        },
    )

    assert base["properties"]["turns"]["minItems"] == 1
    assert effective["properties"]["turns"]["minItems"] == 27
    assert effective["properties"]["turns"]["maxItems"] == 27


def test_dynamic_proposal_and_unit_schemas_use_frozen_cardinality() -> None:
    role_schema, _ = schema_for_proposal("role_demand")
    role_effective = schema_with_frozen_context_bounds(
        "role_demand.proposal",
        role_schema,
        {
            "material": {
                "scale_plan": {
                    "cast_recommended_range": [3, 7],
                    "cast_hard_max": 11,
                }
            }
        },
    )
    assert role_effective["properties"]["proposals"]["minItems"] == 3
    assert role_effective["properties"]["proposals"]["maxItems"] == 11

    cast_effective = schema_with_frozen_context_bounds(
        "cast",
        schema_for_stage("cast"),
        {"material": {"subject_refs": [{"id": "subject-1"}, {"id": "subject-2"}]}},
    )
    assert cast_effective["properties"]["subjects"]["minItems"] == 2
    assert cast_effective["properties"]["subjects"]["maxItems"] == 2

    boundary_schema, _ = schema_for_proposal("volume_boundary")
    boundary_effective = schema_with_frozen_context_bounds(
        "volume_boundary.proposal",
        boundary_schema,
        {"material": {"scale_plan": {"volume_target": 3}}},
    )
    assert boundary_effective["properties"]["proposals"]["minItems"] == 3
    assert boundary_effective["properties"]["proposals"]["maxItems"] == 3

    layout_schema, _ = schema_for_proposal("detail_layout")
    layout_effective = schema_with_frozen_context_bounds(
        "detail_layout.proposal",
        layout_schema,
        {"material": {"chapter_slots": [{"slot": 1}, {"slot": 2}, {"slot": 3}]}},
    )
    chapters = layout_effective["$defs"]["DetailLayoutVolumeProposal"]["properties"]["chapters"]
    assert chapters["minItems"] == 3
    assert chapters["maxItems"] == 3


def test_detail_schema_uses_the_frozen_segment_and_scene_capacity() -> None:
    effective = schema_with_frozen_context_bounds(
        "detail",
        schema_for_stage("detail"),
        {
            "material": {
                "scale_projection": {
                    "chapter_target": 7,
                    "scenes_per_chapter_min": 2,
                    "scenes_per_chapter_max": 5,
                }
            }
        },
    )

    assert effective["properties"]["chapters"]["minItems"] == 7
    assert effective["properties"]["chapters"]["maxItems"] == 7
    scenes = effective["$defs"]["DetailSegmentChapter"]["properties"]["scenes"]
    assert scenes["minItems"] == 2
    assert scenes["maxItems"] == 5


def test_detail_recovery_schema_only_requests_editable_chapters() -> None:
    effective = schema_with_frozen_context_bounds(
        "detail",
        schema_for_stage("detail"),
        {
            "material": {
                "scale_projection": {
                    "chapter_target": 3,
                    "scenes_per_chapter_min": 2,
                    "scenes_per_chapter_max": 5,
                },
                "recovery_source": {
                    "editable_chapter_refs": ["chapter-6"],
                },
            }
        },
    )

    chapters = effective["properties"]["chapters"]
    assert chapters["minItems"] == 1
    assert chapters["maxItems"] == 1
    patch = effective["$defs"]["DetailRecoveryChapterPatch"]
    assert set(patch["properties"]) == {"purpose", "scenes", "handoff"}
    assert set(patch["required"]) == {"purpose", "scenes", "handoff"}
    assert patch["additionalProperties"] is False


def test_compiled_detail_recovery_hides_preserved_and_rejected_source_content() -> None:
    source_chapter = {
        "title": "数据铁证",
        "purpose": "顾行舟核对潮位数据，决定提交证据。",
        "pov": "subject-1",
        "cast_ids": ["subject-1", "subject-4"],
        "scenes": [
            {
                "place": "废弃观测站",
                "objective": "核对纸质潮位记录",
                "conflict": "记录受潮",
                "turn": "顾行舟找到可核验的原始记录",
                "result": "顾行舟确认系统数据被修改",
            },
            {
                "place": "会议室",
                "objective": "提交证据",
                "conflict": "上级拒绝调查",
                "turn": "郑明远仍拒绝重启调查",
                "result": "顾行舟决定公开数据",
            },
        ],
        "handoff": "顾行舟整理证据，准备提交。",
    }
    context = {
        "target": "detail",
        "material": {
            "volume_spine_turns": [
                {
                    "id": "turn-4",
                    "cause": "核对数据",
                    "change": "上级拒绝调查，顾行舟决定公开数据",
                }
            ],
            "scale_projection": {
                "chapter_target": 3,
                "chapter_number_start": 4,
                "scenes_per_chapter_min": 1,
                "scenes_per_chapter_max": 3,
                "chapter_beats": [
                    {
                        "chapter_offset": 1,
                        "turn_refs": ["turn-3"],
                        "dramatic_job": "保留章四",
                        "length_hint": "standard",
                    },
                    {
                        "chapter_offset": 2,
                        "turn_refs": ["turn-3"],
                        "dramatic_job": "保留章五",
                        "length_hint": "standard",
                    },
                    {
                        "chapter_offset": 3,
                        "turn_refs": ["turn-4"],
                        "dramatic_job": "核对数据并决定提交证据",
                        "length_hint": "standard",
                    }
                ],
            },
            "selected_dossiers": [
                {"id": "subject-1", "name": "顾行舟", "kind": "protagonist"},
                {"id": "subject-2", "name": "顾清岚", "kind": "historical_record"},
                {"id": "subject-3", "name": "沈立诚", "kind": "major"},
                {"id": "subject-4", "name": "陈伯年", "kind": "major"},
                {"id": "subject-5", "name": "郑明远", "kind": "functional"},
                {"id": "subject-6", "name": "程远航", "kind": "functional"},
            ],
            "present_actor_ids": [
                "subject-1",
                "subject-3",
                "subject-4",
                "subject-5",
                "subject-6",
            ],
            "historical_record_ids": ["subject-2"],
            "debut_requirements": [
                {"subject_id": "subject-3", "name": "沈立诚"}
            ],
            "preflight_feedback": {
                "blockers": [
                    {
                        "code": "detail_duplicate_job",
                        "chapter_refs": ["chapter-6", "chapter-7"],
                        "evidence": "顾行舟决定公开数据",
                        "required_fix": "chapter 6 只决定提交证据",
                    }
                ]
            },
            "recovery_source": {
                "source_candidate_ref": "detail-candidate-source",
                "source_attempt": 3,
                "segment_ref": "volume-1.segment-2",
                "chapter_refs": ["chapter-4", "chapter-5", "chapter-6"],
                "editable_chapter_refs": ["chapter-6"],
                "preserved_chapter_refs": ["chapter-4", "chapter-5"],
                "required_removed_endpoints": {
                    "chapter-6": ["authority_refusal", "public_decision"]
                },
                "source_segment": {
                    "chapters": [
                        {**source_chapter, "title": "不应暴露的保留章四"},
                        {**source_chapter, "title": "不应暴露的保留章五"},
                        source_chapter,
                    ]
                },
            },
        },
    }

    compiled = compile_provider_input(
        StageGenerationRequest(
            operation_key="run:detail:recover:segment-2",
            run_id="run",
            stage_id="detail",
            attempt=7,
            binding=provider_binding("detail"),
            context=context,
        )
    )

    recovery = compiled.structured_context["material"]["recovery_source"]
    assert "volume_spine_turns" not in compiled.structured_context["material"]
    assert compiled.structured_context["material"]["scale_projection"]["chapter_beats"] == [
        context["material"]["scale_projection"]["chapter_beats"][2]
    ]
    assert "evidence" not in compiled.structured_context["material"]["preflight_feedback"]["blockers"][0]
    assert "source_segment" not in recovery
    assert len(recovery["editable_source_chapters"]) == 1
    visible = recovery["editable_source_chapters"][0]
    assert visible["frozen_cast_names"] == ["顾行舟", "陈伯年"]
    assert visible["omitted_source_scene_indexes"] == [2]
    assert len(visible["source_patch"]["scenes"]) == 1
    assert [
        item["id"]
        for item in compiled.structured_context["material"]["selected_dossiers"]
    ] == ["subject-1", "subject-4"]
    assert compiled.structured_context["material"]["present_actor_ids"] == [
        "subject-1",
        "subject-4",
    ]
    assert compiled.structured_context["material"]["historical_record_ids"] == []
    assert compiled.structured_context["material"]["debut_requirements"] == []
    assert "不应暴露的保留章" not in compiled.rendered_prompt
    assert "郑明远仍拒绝" not in compiled.rendered_prompt
    assert "顾行舟决定公开数据" not in compiled.rendered_prompt
    assert "沈立诚" not in compiled.rendered_prompt
    assert "程远航" not in compiled.rendered_prompt
    assert "intentionally withheld" in compiled.rendered_prompt


def test_compiled_custody_recovery_hides_the_illegal_custody_source() -> None:
    illegal_purpose = "顾行舟被拘留，通过律师程远航获得姐姐留下的最后信息。"
    illegal_handoff = "深夜，顾行舟仍在拘留所，等待律师再次探视。"
    illegal_scene = {
        "place": "拘留所探视室",
        "objective": "通过律师了解外界情况",
        "conflict": "程远航只能传递信息",
        "turn": "程远航转交一张写有坐标的纸条",
        "result": "顾行舟决定让程远航传递指令",
    }
    context = {
        "target": "detail",
        "material": {
            "scale_projection": {
                "chapter_target": 1,
                "chapter_number_start": 13,
                "scenes_per_chapter_min": 1,
                "scenes_per_chapter_max": 5,
                "chapter_beats": [
                    {
                        "chapter_offset": 1,
                        "turn_refs": ["turn-8"],
                        "dramatic_job": (
                            "顾行舟被拘留，通过律师程远航获得姐姐留下的最后信息"
                        ),
                        "length_hint": "standard",
                    }
                ],
            },
            "selected_dossiers": [
                {"id": "subject-1", "name": "顾行舟", "kind": "protagonist"},
                {
                    "id": "subject-6",
                    "name": "程远航",
                    "kind": "functional",
                    "function": "在拘留期间传递信息并促成释放",
                    "drive": "完成顾清岚的托付",
                },
            ],
            "present_actor_ids": ["subject-1", "subject-6"],
            "historical_record_ids": [],
            "debut_requirements": [],
            "previous_segment_handoff": {
                "previous_ref": "chapter-12",
                "completed_turn_refs": ["turn-7"],
                "established_chapters": [
                    {
                        "chapter_ref": "chapter-11",
                        "title": "公开指控",
                        "turn_refs": ["turn-7"],
                        "purpose": "顾行舟公开证据后遭到追捕",
                        "final_result": "顾行舟被逮捕，但证据已经公开",
                    },
                    {
                        "chapter_ref": "chapter-12",
                        "title": "留守抉择",
                        "turn_refs": ["turn-7"],
                        "purpose": "顾行舟面临被捕风险并留下组织撤离",
                        "final_result": "顾行舟仍在旧港区组织最后撤离",
                    },
                ],
                "unresolved": ["顾行舟仍在旧港区组织最后撤离"],
                "next_ref": "volume-1.segment-5",
            },
            "preflight_feedback": {
                "source_candidate_ref": "detail-candidate-source",
                "source_attempt": 3,
                "unique_blocker_count": 1,
                "omitted_blocker_count": 0,
                "blockers": [
                    {
                        "code": "custody_handoff_conflict",
                        "chapter_refs": ["chapter-12", "chapter-13"],
                        "evidence": "chapter-12 leaves the protagonist free",
                        "required_fix": "Execute a new arrest before the custody scene.",
                    }
                ],
            },
            "recovery_source": {
                "source_candidate_ref": "detail-candidate-source",
                "source_attempt": 3,
                "segment_ref": "volume-1.segment-5",
                "chapter_refs": ["chapter-13"],
                "editable_chapter_refs": ["chapter-13"],
                "preserved_chapter_refs": [],
                "required_removed_endpoints": {},
                "custody_repair_contracts": {
                    "chapter-13": {
                        "previous_chapter_ref": "chapter-12",
                        "previous_state": "free",
                        "target_state": "detained",
                        "transition_timing": "on_page_before_custody",
                        "allowed_institution": "警方",
                        "preserved_dramatic_task": (
                            "顾行舟通过律师程远航获得姐姐留下的最后信息"
                        ),
                    }
                },
                "source_segment": {
                    "chapters": [
                        {
                            "title": "拘留所来客",
                            "purpose": illegal_purpose,
                            "pov": "subject-1",
                            "cast_ids": ["subject-1", "subject-6"],
                            "scenes": [illegal_scene],
                            "handoff": illegal_handoff,
                        }
                    ]
                },
            },
        },
    }

    compiled = compile_provider_input(
        StageGenerationRequest(
            operation_key="run:detail:recover:segment-5",
            run_id="run",
            stage_id="detail",
            attempt=10,
            binding=provider_binding("detail"),
            context=context,
        )
    )

    recovery = compiled.structured_context["material"]["recovery_source"]
    visible = recovery["editable_source_chapters"][0]
    assert "frozen_title" not in visible
    assert visible["source_patch"] == {"scenes": []}
    assert visible["omitted_source_fields"] == ["purpose", "handoff"]
    assert visible["omitted_source_scene_indexes"] == [1]
    assert recovery["custody_repair_contracts"]["chapter-13"] == {
        "previous_chapter_ref": "chapter-12",
        "previous_state": "free",
        "target_state": "detained",
        "transition_timing": "on_page_before_custody",
        "allowed_institution": "警方",
        "preserved_dramatic_task": "顾行舟通过律师程远航获得姐姐留下的最后信息",
    }
    assert illegal_purpose not in compiled.rendered_prompt
    assert illegal_handoff not in compiled.rendered_prompt
    assert illegal_scene["place"] not in compiled.rendered_prompt
    assert "拘留所来客" not in compiled.rendered_prompt
    assert "在拘留期间传递信息并促成释放" not in compiled.rendered_prompt
    assert "顾行舟被逮捕，但证据已经公开" not in compiled.rendered_prompt
    assert "证据已经公开" in compiled.rendered_prompt
    assert "顾行舟仍在旧港区组织最后撤离" in compiled.rendered_prompt
    assert [
        item["chapter_ref"]
        for item in compiled.structured_context["material"][
            "previous_segment_handoff"
        ]["established_chapters"]
    ] == ["chapter-11", "chapter-12"]
    assert compiled.structured_context["material"]["selected_dossiers"][1] == {
        "id": "subject-6",
        "name": "程远航",
        "kind": "functional",
        "drive": "完成顾清岚的托付",
    }
    assert (
        compiled.structured_context["material"]["scale_projection"]["chapter_beats"][0][
            "dramatic_job"
        ]
        == "顾行舟通过律师程远航获得姐姐留下的最后信息"
    )
    assert "an on-page scene must execute a re-arrest or surrender" in compiled.rendered_prompt
    assert "never invent a named officer" in compiled.rendered_prompt
    assert "except for the one explicit custody transition" in compiled.rendered_prompt


def test_compiled_spine_input_exposes_dynamic_bounds_to_the_provider() -> None:
    compiled = compile_provider_input(
        StageGenerationRequest(
            operation_key="run:spine:1",
            run_id="run",
            stage_id="spine",
            attempt=1,
            binding=provider_binding("spine"),
            context={
                "target": "spine",
                "material": {
                    "scale_plan": {
                        "turn_target": 27,
                        "turn_capacity_range": [23, 34],
                        "chapter_target": 40,
                        "milestone_positions": {
                            "inciting": 1,
                            "commitment": 7,
                            "midpoint_reversal": 14,
                            "crisis": 19,
                            "climax": 26,
                            "aftermath": 27,
                        },
                    },
                    "story_brief": {},
                },
            },
        )
    )

    turns = compiled.output_contract.json_schema_contract["properties"]["turns"]
    assert turns["minItems"] == 27
    assert turns["maxItems"] == 27
    assert '"minItems": 27' in compiled.rendered_prompt
    assert "Return exactly 27" in compiled.rendered_prompt
