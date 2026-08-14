from __future__ import annotations

from novel_workflow.runtime.graph.chapter_review import drop_compliance_findings
from novel_workflow.runtime.graph.provider_gateway import ChapterReviewResult


def result(*claims: str) -> ChapterReviewResult:
    return ChapterReviewResult(
        role="prose",
        available=True,
        findings=[
            {"code": "voice_person_mismatch", "severity": "blocking", "claim": claim, "evidence": "林晚坐下", "subject_ids": []}
            for claim in claims
        ],
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
