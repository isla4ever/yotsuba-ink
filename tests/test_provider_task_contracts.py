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
