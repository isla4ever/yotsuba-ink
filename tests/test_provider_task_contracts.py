from __future__ import annotations

import pytest

from novel_workflow.output_contracts.provider_tasks import (
    CastDossierSemanticFinding,
    RoleDemandSemanticFinding,
    SpineSemanticFinding,
)


@pytest.mark.parametrize(
    ("finding_type", "payload"),
    [
        (
            SpineSemanticFinding,
            {
                "code": "causal_handoff",
                "claim": "因果交接需要复核",
                "required_fix": "核对相邻转折",
            },
        ),
        (
            RoleDemandSemanticFinding,
            {
                "code": "missing_turn_agency",
                "demand_refs": ["demand-witness"],
                "claim": "职责引用顺序需要规范化",
                "required_fix": "保留引用并按故事顺序展示",
            },
        ),
        (
            CastDossierSemanticFinding,
            {
                "code": "motivation_bridge",
                "subject_refs": ["subject-witness"],
                "demand_refs": ["demand-witness"],
                "claim": "人物动机引用顺序需要规范化",
                "required_fix": "保留引用并按故事顺序展示",
            },
        ),
    ],
)
def test_reviewer_turn_refs_are_code_ordered(finding_type, payload) -> None:
    finding = finding_type.model_validate(
        {**payload, "turn_refs": ["turn-15", "turn-4", "turn-11"]}
    )

    assert finding.turn_refs == ["turn-4", "turn-11", "turn-15"]


def test_reviewer_turn_refs_still_reject_duplicates() -> None:
    with pytest.raises(ValueError, match="turn refs must be unique"):
        RoleDemandSemanticFinding.model_validate(
            {
                "code": "missing_turn_agency",
                "demand_refs": ["demand-witness"],
                "turn_refs": ["turn-4", "turn-4"],
                "claim": "重复引用",
                "required_fix": "删除重复引用",
            }
        )


@pytest.mark.parametrize(
    ("finding_type", "payload"),
    [
        (
            SpineSemanticFinding,
            {
                "code": "ending_derivation",
                "claim": "终局问题跨越完整因果链",
                "required_fix": "核对全局因果推导",
            },
        ),
        (
            RoleDemandSemanticFinding,
            {
                "code": "missing_turn_agency",
                "demand_refs": ["demand-protagonist"],
                "claim": "主角职责覆盖全局因果链",
                "required_fix": "核对全局行动责任",
            },
        ),
        (
            CastDossierSemanticFinding,
            {
                "code": "performance_ambiguity",
                "subject_refs": ["subject-protagonist"],
                "demand_refs": ["demand-protagonist"],
                "claim": "主角行为模式跨越完整因果链",
                "required_fix": "区分全局行为倾向与表达方式",
            },
        ),
    ],
)
def test_reviewer_findings_accept_a_complete_frozen_spine(finding_type, payload) -> None:
    turn_refs = [f"turn-{number}" for number in range(1, 121)]

    finding = finding_type.model_validate({**payload, "turn_refs": turn_refs})

    assert finding.turn_refs == turn_refs


def test_reviewer_findings_reject_refs_beyond_the_spine_contract_capacity() -> None:
    with pytest.raises(ValueError, match="at most 120 items"):
        CastDossierSemanticFinding.model_validate(
            {
                "code": "performance_ambiguity",
                "subject_refs": ["subject-protagonist"],
                "demand_refs": ["demand-protagonist"],
                "turn_refs": [f"turn-{number}" for number in range(1, 122)],
                "claim": "引用超过唯一 Spine 合同容量",
                "required_fix": "只引用当前冻结 Spine",
            }
        )
