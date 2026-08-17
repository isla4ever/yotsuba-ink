from __future__ import annotations

import pytest

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterRelation,
    CharacterSubject,
    RoleDemandProposalBatch,
    StorySpineArtifact,
)
from novel_workflow.output_contracts.provider_tasks import SpineSemanticFinding
from novel_workflow.runtime.graph.spine_preflight import (
    build_spine_repair_material,
    deterministic_spine_resolution_findings,
)
from novel_workflow.runtime.graph.stage_executor import (
    _bind_story_spine,
    _relationship_turn_ids,
    _validate_cast_relationship_coverage,
    _validate_role_demand_plan,
    _validate_stage_unit,
)
from novel_workflow.workflows.prompt_templates import default_prompt_templates
from novel_workflow.workflows.narrative_scale import spine_milestone_positions


def _spine_payload(turn_count: int) -> dict[str, object]:
    progress_types = ("information", "external", "relationship", "information", "internal")
    return {
        "turns": [
            {
                "cause": f"前因 {index}",
                "change": f"变化 {index}",
                "progress_type": progress_types[(index - 1) % len(progress_types)],
            }
            for index in range(1, turn_count + 1)
        ],
        "ending": "最终变化已经兑现立项承诺",
        "open_questions": [],
    }


def _spine_context(*, target: int = 27) -> dict[str, object]:
    return {
        "material": {
            "scale_plan": {
                "turn_target": target,
                "turn_capacity_range": [23, 34],
                "milestone_positions": spine_milestone_positions(target),
                "chapter_target": 40,
            }
        },
        "output_budget": {
            "kind": "spine",
            "expected_items": target,
            "item_cap": target,
            "field_char_cap": 125,
            "max_tokens": 6_000,
        },
    }


def test_spine_rejects_turn_count_outside_frozen_scale_before_candidate() -> None:
    with pytest.raises(ValueError, match="returned 20 turns.*requires exactly 27"):
        _validate_stage_unit("spine", "", _spine_context(), _spine_payload(20))


def test_spine_accepts_only_the_code_owned_exact_target() -> None:
    _validate_stage_unit("spine", "", _spine_context(), _spine_payload(27))
    with pytest.raises(ValueError, match="requires exactly 27"):
        _validate_stage_unit("spine", "", _spine_context(), _spine_payload(28))


def test_spine_allows_story_actions_that_determine_a_later_publication_choice() -> None:
    payload = _spine_payload(25)
    payload["turns"][17]["cause"] = "林妍整理已有证据，供后续确定公开方式。"  # type: ignore[index]

    _validate_stage_unit("spine", "", _spine_context(target=25), payload)


def test_spine_normalizes_known_milestone_labels_used_as_progress_types() -> None:
    payload = _spine_payload(25)
    payload["turns"][23]["progress_type"] = "climax"  # type: ignore[index]
    payload["turns"][24]["progress_type"] = "aftermath"  # type: ignore[index]

    _validate_stage_unit("spine", "", _spine_context(target=25), payload)
    bound = _bind_story_spine(payload)

    assert bound["turns"][23]["progress_type"] == "external"
    assert bound["turns"][24]["progress_type"] == "internal"


def test_runtime_binds_code_owned_milestones_to_the_exact_turn_plan() -> None:
    artifact = StorySpineArtifact.model_validate(_bind_story_spine(_spine_payload(27)))
    actual = {
        milestone: index
        for index, turn in enumerate(artifact.turns, start=1)
        for milestone in turn.milestones
    }

    assert actual == spine_milestone_positions(27)


def test_spine_resolution_gate_rejects_terminal_outcome_before_climax() -> None:
    payload = _bind_story_spine(_spine_payload(20))
    payload["turns"][17]["change"] = "最终听证会做出最终裁决，弟弟被正式吊销执业资格"
    findings = deterministic_spine_resolution_findings(payload)
    assert len(findings) == 1
    assert findings[0].code == "premature_resolution"
    assert findings[0].turn_refs == ["turn-18", "turn-19"]


@pytest.mark.parametrize(
    "terminal_outcome",
    [
        "警方结案",
        "林远最终免于起诉",
        "林远被正式解雇",
        "林远被正式解除职务",
        "林远被判处缓刑",
        "中心永久吊销林远的调度员资格",
        "林远失去调度员资格",
    ],
)
def test_spine_resolution_gate_catches_explicit_legal_closure_before_climax(
    terminal_outcome: str,
) -> None:
    payload = _bind_story_spine(_spine_payload(20))
    payload["turns"][15]["change"] = terminal_outcome  # type: ignore[index]

    findings = deterministic_spine_resolution_findings(payload)

    assert len(findings) == 1
    assert findings[0].code == "premature_resolution"
    assert findings[0].turn_refs == ["turn-16", "turn-19"]


def test_spine_allows_information_runs_but_requires_external_and_relationship_progress() -> None:
    information_run = _spine_payload(25)
    for turn in information_run["turns"][:3]:  # type: ignore[index]
        turn["progress_type"] = "information"
    _validate_stage_unit("spine", "", _spine_context(target=25), information_run)

    for forbidden, message in (
        ("external", "external-pressure"),
        ("relationship", "relationship turn"),
    ):
        payload = _spine_payload(25)
        for turn in payload["turns"]:  # type: ignore[index]
            if turn["progress_type"] == forbidden:
                turn["progress_type"] = "internal"
        with pytest.raises(ValueError, match=message):
            _validate_stage_unit("spine", "", _spine_context(target=25), payload)

    one_external = _spine_payload(25)
    seen_external = False
    for turn in one_external["turns"]:  # type: ignore[index]
        if turn["progress_type"] == "external":
            if seen_external:
                turn["progress_type"] = "internal"
            seen_external = True
    _validate_stage_unit("spine", "", _spine_context(target=25), one_external)


def test_spine_rejects_repeated_or_noop_turn_states() -> None:
    repeated = _spine_payload(25)
    repeated["turns"][1]["change"] = repeated["turns"][0]["change"]  # type: ignore[index]
    with pytest.raises(ValueError, match="repeat the same change"):
        _validate_stage_unit("spine", "", _spine_context(target=25), repeated)

    noop = _spine_payload(25)
    noop["turns"][4]["change"] = noop["turns"][4]["cause"]  # type: ignore[index]
    with pytest.raises(ValueError, match="different states"):
        _validate_stage_unit("spine", "", _spine_context(target=25), noop)


def test_role_demand_protagonist_must_span_the_spine_and_respect_dynamic_capacity() -> None:
    spine = StorySpineArtifact.model_validate(_bind_story_spine(_spine_payload(25)))
    protagonist = {
        "demand_key": "demand-protagonist",
        "subject_mode": "actor",
        "narrative_role": "protagonist",
        "function": "公开追查被替换的事故母带",
        "required_change": "从私人核验转向承担公开指证后果",
        "irreducibility": "她必须公开自己的违规修复记录并承担职业资格被撤销的后果。",
        "active_turn_refs": ["turn-1"],
    }
    missing_final = RoleDemandProposalBatch.model_validate({"proposals": [protagonist]})
    with pytest.raises(ValueError, match="opening and final Spine turns"):
        _validate_role_demand_plan(missing_final, spine, recommended_min=1, hard_max=11)

    complete = {
        **protagonist,
        "active_turn_refs": ["turn-1", "turn-25"],
    }
    advisory_relationship_gap = RoleDemandProposalBatch.model_validate(
        {"proposals": [complete]}
    )
    _validate_role_demand_plan(
        advisory_relationship_gap,
        spine,
        recommended_min=1,
        hard_max=11,
    )

    relationship = {
        "demand_key": "demand-witness",
        "subject_mode": "actor",
        "narrative_role": "relationship",
        "function": "实名授权关键证词并在危机时决定是否撤回",
        "required_change": "从自保沉默转向公开承担证词后果",
        "irreducibility": "此人必须选择撤回实名授权，使主角失去公开证据并改变合作关系。",
        "active_turn_refs": ["turn-3", "turn-8", "turn-13", "turn-18", "turn-23"],
    }
    over_capacity = RoleDemandProposalBatch.model_validate(
        {"proposals": [complete, relationship]}
    )
    with pytest.raises(ValueError, match="allows at most 1"):
        _validate_role_demand_plan(
            over_capacity,
            spine,
            recommended_min=1,
            hard_max=1,
        )


def test_explicit_family_pressure_counts_as_relationship_turn() -> None:
    spine_payload = _spine_payload(10)
    spine_payload["turns"][4] = {
        "cause": "主角得知父亲被带走",
        "change": "父子关系从疏离转为共同承担后果",
        "progress_type": "internal",
    }
    spine = StorySpineArtifact.model_validate(_bind_story_spine(spine_payload))
    batch = RoleDemandProposalBatch.model_validate(
        {
            "proposals": [
                {
                    "demand_key": "demand-protagonist",
                    "subject_mode": "actor",
                    "narrative_role": "protagonist",
                    "function": "承担调查与选择",
                    "required_change": "从回避转为承担",
                    "irreducibility": "主角必须承担终局选择。",
                    "active_turn_refs": ["turn-1", "turn-10"],
                },
                {
                    "demand_key": "demand-father",
                    "subject_mode": "actor",
                    "narrative_role": "relationship",
                    "function": "父亲与主角共同承担家庭后果",
                    "required_change": "从疏离转为共同承担",
                    "irreducibility": "父亲的选择不可由机构或主角代替。",
                    "active_turn_refs": ["turn-5"],
                },
                {
                    "demand_key": "demand-colleague",
                    "subject_mode": "actor",
                    "narrative_role": "relationship",
                    "function": "同事在调查中改变合作关系",
                    "required_change": "从谨慎转为合作",
                    "irreducibility": "同事的选择改变调查风险。",
                    "active_turn_refs": ["turn-3", "turn-4", "turn-8"],
                },
            ]
        }
    )

    _validate_role_demand_plan(batch, spine, recommended_min=2, hard_max=11)


def test_family_case_mentions_do_not_become_relationship_turns_by_themselves() -> None:
    spine_payload = _spine_payload(10)
    spine_payload["turns"][3]["cause"] = "主角发现父亲旧案出现新证据"  # type: ignore[index]
    spine_payload["turns"][3]["change"] = "调查方向转向当年的急救记录"  # type: ignore[index]
    spine = StorySpineArtifact.model_validate(_bind_story_spine(spine_payload))

    assert "turn-4" not in _relationship_turn_ids(spine)


def test_cast_relationship_gate_rejects_an_orphan_relationship_subject() -> None:
    spine = StorySpineArtifact.model_validate(_bind_story_spine(_spine_payload(25)))
    demands = RoleDemandProposalBatch.model_validate(
        {
            "proposals": [
                {
                    "demand_key": "demand-protagonist",
                    "subject_mode": "actor",
                    "narrative_role": "protagonist",
                    "function": "公开追查被替换的事故母带",
                    "required_change": "从私人核验转向承担公开指证后果",
                    "irreducibility": "主角必须公开自己的违规修复记录并承担职业资格被撤销的后果。",
                    "active_turn_refs": ["turn-1", "turn-25"],
                },
                {
                    "demand_key": "demand-witness",
                    "subject_mode": "actor",
                    "narrative_role": "relationship",
                    "function": "决定是否撤回实名证词",
                    "required_change": "从自保沉默转向公开承担证词后果",
                    "irreducibility": "证人必须选择是否撤回实名授权，使主角失去公开证据并改变合作关系。",
                    "active_turn_refs": ["turn-3", "turn-8", "turn-13", "turn-18", "turn-23"],
                },
            ]
        }
    )

    def subject(subject_id: str, name: str, demand_key: str, kind: str) -> CharacterSubject:
        return CharacterSubject.model_validate(
            {
                "id": subject_id,
                "name": name,
                "kind": kind,
                "function": "承担一项不可合并的取证与选择职责",
                "background": "旧港档案修复师，事故前已长期负责原始记录保存。",
                "conflict_history": "曾因旧案记录被替换而承担过一次公开责任追究。",
                "present_stakes": "若证词失效，将失去职业资格和与主角的信任关系。",
                "temperament": "压力下先核对可见事实，再用沉默争取判断时间。",
                "speech_style": "短句为主，回答前会复述关键词并保留停顿。",
                "drive": "让被替换的记录重新获得公开检验",
                "change": "从回避责任转向承担公开选择的后果",
                "debut": "chapter:1",
                "limits": ["不得替代另一主体完成最终选择"],
                "demand_refs": [demand_key],
            }
        )

    subjects = [
        subject("subject-1", "林默", "demand-protagonist", "protagonist"),
        subject("subject-2", "周屿", "demand-witness", "major"),
    ]
    with pytest.raises(ValueError, match="missing subjects"):
        _validate_cast_relationship_coverage(subjects, [], demands, spine)

    _validate_cast_relationship_coverage(
        subjects,
        [
            CharacterRelation(
                a="subject-1",
                b="subject-2",
                type="互相隐瞒的调查搭档",
                pressure="公开证词会让双方同时承担职业后果",
            )
        ],
        demands,
        spine,
    )


def test_long_role_demands_reject_one_off_history_and_misaligned_relationship_roles() -> None:
    spine = StorySpineArtifact.model_validate(_bind_story_spine(_spine_payload(25)))
    protagonist = {
        "demand_key": "demand-protagonist",
        "subject_mode": "actor",
        "narrative_role": "protagonist",
        "function": "公开追查被替换的事故母带",
        "required_change": "从私人核验转向承担公开指证后果",
        "irreducibility": "她必须公开自己的违规修复记录并承担职业资格被撤销的后果。",
        "active_turn_refs": ["turn-1", "turn-25"],
    }
    historical = {
        "demand_key": "demand-record",
        "subject_mode": "historical_record",
        "narrative_role": "historical_record",
        "function": "以事故前录音改变当下责任判断",
        "required_change": "录音从家庭遗物变成公开责任证据",
        "irreducibility": "同一名死者的声音必须跨阶段保持身份，才能让证词归属及责任后果可追溯。",
        "active_turn_refs": ["turn-5"],
    }
    relationship = {
        "demand_key": "demand-sibling",
        "subject_mode": "actor",
        "narrative_role": "relationship",
        "function": "在公开听证前决定是否撤回工程签字",
        "required_change": "从保护家人转向承担公开签字责任",
        "irreducibility": "弟弟必须亲自决定撤回签字，使工程延期并改变与主角的家庭关系。",
        "active_turn_refs": ["turn-2", "turn-4"],
    }

    one_off_history = RoleDemandProposalBatch.model_validate(
        {"proposals": [protagonist, historical, {**relationship, "active_turn_refs": ["turn-3", "turn-8"]}]}
    )
    with pytest.raises(ValueError, match="historical demands must span at least two"):
        _validate_role_demand_plan(one_off_history, spine, recommended_min=3, hard_max=11)

    misaligned_relationship = RoleDemandProposalBatch.model_validate(
        {
            "proposals": [
                protagonist,
                {**historical, "active_turn_refs": ["turn-5", "turn-10"]},
                relationship,
            ]
        }
    )
    with pytest.raises(ValueError, match="must cite at least one relationship Spine turn"):
        _validate_role_demand_plan(
            misaligned_relationship,
            spine,
            recommended_min=3,
            hard_max=11,
        )


def test_single_turn_relationship_bridge_is_allowed_when_it_covers_the_turn() -> None:
    spine_payload = _spine_payload(10)
    for turn in spine_payload["turns"]:  # type: ignore[index]
        turn["progress_type"] = "internal"
    spine_payload["turns"][2]["progress_type"] = "relationship"  # type: ignore[index]
    spine_payload["turns"][3]["progress_type"] = "external"  # type: ignore[index]
    spine = StorySpineArtifact.model_validate(_bind_story_spine(spine_payload))
    protagonist = {
        "demand_key": "demand-protagonist",
        "subject_mode": "actor",
        "narrative_role": "protagonist",
        "function": "追查旧案并承担终局选择",
        "required_change": "从回避转为承担",
        "irreducibility": "主角必须亲自完成终局选择。",
        "active_turn_refs": ["turn-1", "turn-10"],
    }
    bridge = {
        "demand_key": "demand-bridge",
        "subject_mode": "actor",
        "narrative_role": "relationship",
        "function": "在一次会面中警告主角并留下关键线索",
        "required_change": "从警告转为留下可执行线索",
        "irreducibility": "该主体的唯一选择改变主角下一步行动。",
        "active_turn_refs": ["turn-3"],
    }
    batch = RoleDemandProposalBatch.model_validate(
        {"proposals": [protagonist, bridge]}
    )
    _validate_role_demand_plan(batch, spine, recommended_min=1, hard_max=11)


def test_final_volume_must_bind_the_whole_book_climax_turn() -> None:
    context = {
        "material": {
            "volume_spine_turns": [
                {"id": "turn-20", "milestones": []},
                {"id": "turn-21", "milestones": ["climax"]},
                {"id": "turn-22", "milestones": ["aftermath"]},
            ],
            "closure_policy": {"contains_final_volume": True},
            "reserved_titles": [],
        }
    }
    payload = {
        "volumes": [
            {
                "title": "潮痕终审",
                "promise": "让证词进入最终审理",
                "conflict": "公开证据与职业代价正面冲突",
                "climax": "主角公开原始母带",
                "climax_turn_ref": "turn-22",
                "closure": "证词生效且主角承担资格撤销后果",
                "cast_ids": ["subject-1"],
                "length_hint": "medium",
            }
        ]
    }

    with pytest.raises(ValueError, match="whole-book climax turn"):
        _validate_stage_unit("volumes", "volume-3", context, payload)


def test_spine_prompt_keeps_cast_ownership_and_terminal_events_in_order() -> None:
    prompt = next(
        item.content for item in default_prompt_templates() if item.stage_type == "spine"
    )

    assert "不得在 Cast 前取名" in prompt
    assert "全书至多允许一个 turn 的主要 change 只是“又获得一份证明”" in prompt
    assert "每个 cause 必须直接利用上一 change" in prompt
    assert "v1 执行优先" in prompt
    assert "open_questions 只能保留不影响本书闭环" in prompt
    assert "turn_target 是代码按章节承载密度冻结的精确转折数" in prompt
    assert "turn_capacity_range 只说明编辑容量" in prompt
    assert "milestone_positions 已给出六个代码冻结位置" in prompt
    assert "不要在 JSON 中返回这些标签" in prompt
    assert "不用不断获取新工具、新权限、新样本或新文件冒充推进" in prompt


def _semantic_finding(code: str, turn_refs: list[str]) -> SpineSemanticFinding:
    return SpineSemanticFinding(
        code=code,
        turn_refs=turn_refs,
        claim=f"{code} blocks the causal chain",
        required_fix=f"repair {code}",
    )


def test_systemic_spine_repair_discards_the_failed_draft_instead_of_anchoring_to_it() -> None:
    rejected = _bind_story_spine(_spine_payload(20))
    rejected["turns"][12]["change"] = "这句失败稿内容绝不能进入重构上下文"  # type: ignore[index]
    material = build_spine_repair_material(
        {"story_brief": {"title": "雾港旧声"}, "scale_plan": {"turn_target": 20}},
        rejected,
        [
            _semantic_finding("premature_resolution", ["turn-13", "turn-19"]),
            _semantic_finding("redundant_progress", ["turn-10", "turn-13"]),
            _semantic_finding("causal_handoff", ["turn-12", "turn-14"]),
            _semantic_finding("ending_derivation", ["turn-19", "turn-20"]),
        ],
    )

    assert "rejected_spine_draft" not in material
    assert material["discarded_spine_failure"]["strategy"] == "fresh_causal_replan"
    assert "这句失败稿内容绝不能进入重构上下文" not in str(material)
    assert "不要复原、改写或沿用原草稿" in material["revision_request"]["direction"]


def test_local_spine_repair_keeps_the_draft_for_a_bounded_causal_edit() -> None:
    rejected = _bind_story_spine(_spine_payload(20))
    material = build_spine_repair_material(
        {"story_brief": {"title": "雾港旧声"}, "scale_plan": {"turn_target": 20}},
        rejected,
        [_semantic_finding("motivation_bridge", ["turn-7", "turn-8"])],
    )

    assert material["rejected_spine_draft"] == rejected
    assert "discarded_spine_failure" not in material
    assert "只重写 findings 指向的 turn" in material["revision_request"]["direction"]
