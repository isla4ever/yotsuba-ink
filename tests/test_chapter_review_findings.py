from __future__ import annotations

from novel_workflow.runtime.graph.chapter_review import (
    drop_compliance_findings,
    deterministic_world_rule_findings,
    hard_review_findings,
    review_warning_findings,
)
from novel_workflow.runtime.graph.provider_gateway import ChapterReviewResult
from novel_workflow.output_contracts.artifacts_vnext import StoryBriefArtifact
from novel_workflow.quality.planning_contracts import project_world_rules


def result(*claims: str) -> ChapterReviewResult:
    return ChapterReviewResult(
        role="prose",
        available=True,
        findings=[
            {"code": "voice_person_mismatch", "severity": "blocking", "claim": claim, "evidence": "林晚坐下", "subject_ids": []}
            for claim in claims
        ],
    )


def projected_rules(*rules: str):
    return project_world_rules(
        StoryBriefArtifact.model_validate(
            {
                "title": "明日来电",
                "premise": "调度员追查未来报警。",
                "promise": "每次干预都会改变旧案。",
                "world_rules": list(rules),
                "theme": "职业伦理",
                "ending_promise": "旧案真相公开。",
                "voice": "第三人称有限视角",
                "length_envelope": {"word_target_soft": 10_000},
            }
        )
    )


def test_a_finding_that_states_the_chapter_complies_is_dropped() -> None:
    kept = drop_compliance_findings(result("章节采用第三人称有限视角，符合 voice 合同，无违规。"))
    assert kept.findings == []


def test_a_real_violation_survives_the_compliance_filter() -> None:
    kept = drop_compliance_findings(result("章节以第一人称叙述，与 voice 合同的第三人称不符合。"))
    assert len(kept.findings) == 1


def test_findings_without_compliance_language_are_untouched() -> None:
    original = result("章节开头跳到三天后，未交代时间过渡。")
    assert drop_compliance_findings(original) is original


def test_unknown_blocking_label_is_advisory_in_v1() -> None:
    review = result("章节节奏略慢，但不影响读者理解。")

    assert hard_review_findings([review]) == []
    assert review_warning_findings([review])[0]["code"] == "voice_person_mismatch"


def test_evidence_backed_llm_continuity_code_remains_advisory() -> None:
    review = ChapterReviewResult(
        role="continuity",
        findings=[
            {
                "code": "continuity.scene_repeat",
                "severity": "blocking",
                "claim": "本场重复了上一场已经完成的进入动作。",
                "evidence": "林晚再次推门进入值班室",
                "subject_ids": ["subject-1"],
            }
        ],
    )

    assert hard_review_findings([review]) == []
    assert review_warning_findings([review])[0]["code"] == "continuity.scene_repeat"


def test_llm_time_rule_conflict_remains_advisory() -> None:
    review = ChapterReviewResult(
        role="continuity",
        findings=[
            {
                "code": "time_rule_conflict",
                "severity": "blocking",
                "claim": "正文把来自24小时后的电话写成了当场来电。",
                "evidence": "电话是在事情发生的同一分钟打来的",
                "subject_ids": ["subject-1"],
            }
        ],
    )

    assert hard_review_findings([review]) == []
    assert review_warning_findings([review])[0]["code"] == "time_rule_conflict"


def test_deterministic_future_call_rule_conflict_remains_a_hard_gate() -> None:
    findings = deterministic_world_rule_findings(
        world_rule_projection=projected_rules(
            "每晚固定时间会接到来自24小时后的报警电话，内容真实且可干预。"
        ),
        content="电话不是提前二十四小时打来的。事情已经发生，电话才响。",
        subject_ids=["subject-1"],
    )

    assert len(findings) == 1
    assert findings[0].code == "time_rule_conflict"
    assert findings[0].severity == "blocking"


def test_future_call_rule_affirmation_is_not_misread_as_a_negation() -> None:
    findings = deterministic_world_rule_findings(
        world_rule_projection=projected_rules(
            "每晚固定时间会接到来自24小时后的报警电话，内容真实且可干预。"
        ),
        content="不是今晚，是二十四小时之后。林远把来电时间重新记了一遍。",
        subject_ids=["subject-1"],
    )

    assert findings == ()


def test_immediate_realization_of_a_24_hour_prediction_is_blocked() -> None:
    findings = deterministic_world_rule_findings(
        world_rule_projection=projected_rules(
            "报警电话来自24小时后的事件，只能提前一天干预。"
        ),
        content=(
            "电话那头喊：马上要出车祸。林远立刻派出救护车。"
            "他盯着同一个路口，几分钟后撞击声响起，黑车撞向护栏。"
        ),
        subject_ids=["subject-1"],
    )

    assert [item.code for item in findings] == ["time_rule_conflict"]


def test_next_day_transition_keeps_the_24_hour_prediction_valid() -> None:
    findings = deterministic_world_rule_findings(
        world_rule_projection=projected_rules(
            "报警电话来自24小时后的事件，只能提前一天干预。"
        ),
        content=(
            "电话那头喊：马上要出车祸。林远记下路口，没有立即派车。"
            "第二天傍晚，他提前联系交警疏导。车祸最终没有发生。"
        ),
        subject_ids=["subject-1"],
    )

    assert findings == ()


def test_namespaced_llm_durable_fact_conflict_remains_advisory() -> None:
    review = ChapterReviewResult(
        role="continuity",
        findings=[
            {
                "code": "continuity.invented_durable_fact",
                "severity": "blocking",
                "claim": "正文新增了未冻结的持久规则。",
                "evidence": "手机在无卡状态下仍然接通",
                "subject_ids": ["subject-1"],
            }
        ],
    )

    assert hard_review_findings([review]) == []
    assert review_warning_findings([review])[0]["code"] == "continuity.invented_durable_fact"
