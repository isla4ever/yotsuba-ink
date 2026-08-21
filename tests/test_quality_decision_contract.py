from __future__ import annotations

from novel_workflow.quality.decision_contract import (
    build_quality_decision,
    contract_blocker,
    review_warning,
)


def test_reviewer_blocking_self_rating_stays_advisory_and_acceptable() -> None:
    warning = review_warning(
        {
            "code": "pacing",
            "severity": "blocking",
            "claim": "解释段略长。",
            "evidence": "他又复述了一遍流程。",
            "subject_ids": ["subject-lin"],
        },
        reviewer_role="prose",
        subject_labels={"subject-lin": "林远"},
    )

    decision = build_quality_decision(review_warnings=[warning])

    assert decision.contract_blockers == []
    assert decision.review_warnings[0].source_severity == "blocking"
    assert decision.allowed_actions() == ["accept", "regenerate", "cancel"]


def test_deterministic_blocker_allows_one_targeted_regeneration_then_stops() -> None:
    blocker = contract_blocker(
        {
            "code": "time_rule_conflict",
            "claim": "正文让 24 小时后的事故在同一时段兑现。",
            "evidence": "几分钟后撞击声响起。",
            "subject_ids": ["subject-lin"],
        },
        subject_labels={"subject-lin": "林远"},
    )

    first = build_quality_decision(contract_blockers=[blocker])
    exhausted = build_quality_decision(
        contract_blockers=[blocker],
        regeneration_used=1,
    )

    assert first.allowed_actions() == ["regenerate", "cancel"]
    assert first.regeneration_recommendation is not None
    assert first.regeneration_recommendation.kind == "required"
    assert exhausted.allowed_actions() == ["cancel"]
    assert exhausted.regeneration_used == exhausted.regeneration_limit == 1


def test_evidence_recovery_is_independent_from_prose_regeneration_quota() -> None:
    decision = build_quality_decision(
        evidence_status="needs_action",
        regeneration_used=1,
        accepted=True,
    )

    assert decision.evidence_degraded is True
    assert decision.accepted is True
    assert decision.allowed_actions() == ["retry_evidence", "cancel"]


def test_accepted_version_keeps_advisory_warnings_visible() -> None:
    warning = review_warning(
        {
            "code": "voice",
            "severity": "warning",
            "claim": "个别句子声纹趋同。",
            "evidence": "三人连续用了相同句式。",
            "subject_ids": [],
        },
        reviewer_role="prose",
        subject_labels={},
    )

    decision = build_quality_decision(
        review_warnings=[warning],
        accepted=True,
    )

    assert decision.accepted is True
    assert [item.code for item in decision.review_warnings] == ["voice"]


def test_required_review_unavailable_stops_without_regenerating_prose() -> None:
    blocker = contract_blocker(
        {
            "code": "required_review_unavailable",
            "claim": "必需审稿角色不可用。",
            "evidence": "Unavailable required reviewers: continuity",
            "subject_ids": [],
        },
        subject_labels={},
    )

    decision = build_quality_decision(contract_blockers=[blocker])

    assert blocker.resolution == "manual"
    assert decision.allowed_actions() == ["cancel"]
