from __future__ import annotations

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact, DetailArtifact
from novel_workflow.quality.manuscript_contracts import build_manuscript_quality_report


def _detail() -> DetailArtifact:
    return DetailArtifact.model_validate(
        {
            "chapters": [
                {
                    "ref": f"chapter-{number}",
                    "volume_ref": "volume-1",
                    "title": title,
                    "target_characters": 2200,
                    "turn_refs": [f"turn-{number}"],
                    "purpose": purpose,
                    "pov": "subject-1",
                    "cast_ids": ["subject-1"],
                    "scenes": [
                        {
                            "place": "档案室",
                            "objective": purpose,
                            "conflict": "管理员要求核验来源",
                            "turn": "林默提交材料并说明来源",
                            "result": result,
                        }
                    ],
                    "handoff": handoff,
                }
                for number, title, purpose, result, handoff in (
                    (1, "旧信", "核验匿名信来源", "确认信纸来自档案馆", "次日去银行核验转账"),
                    (2, "账目", "核验转账保管链", "确认原件由警方封存", "警方正式接管材料"),
                )
            ]
        }
    )


def _chapters(*contents: str) -> list[ChapterArtifact]:
    titles = ("旧信", "账目")
    return [
        ChapterArtifact(
            chapter_id=f"chapter-{index}",
            version_id=f"chapter-{index}-v1-accepted",
            title=titles[index - 1],
            content=content,
            author_status="accepted",
        )
        for index, content in enumerate(contents, 1)
    ]


def test_clean_manuscript_passes_with_reviewer_findings_kept_as_warnings() -> None:
    report = build_manuscript_quality_report(
        detail=_detail(),
        chapters=_chapters("林默核对匿名信来源。", "警方接管原件。"),
        review_findings=[
            {
                "code": "voice",
                "claim": "个别句式趋同。",
                "evidence": "林默停了一下。",
                "chapter_id": "chapter-2",
            }
        ],
    )

    assert report.structure_contract == "passed"
    assert report.blockers == []
    assert report.warnings[0].source == "reviewer"


def test_unbalanced_quotes_block_the_cover_handoff() -> None:
    report = build_manuscript_quality_report(
        detail=_detail(),
        chapters=_chapters("林默说：“来源不对。", "警方接管原件。"),
    )

    assert report.structure_contract == "blocked"
    assert report.blockers[0].code == "punctuation_quote_unbalanced"


def test_exact_repeated_paragraph_or_passage_is_a_deterministic_blocker() -> None:
    repeated = "林默把来源编号逐项写在证物袋上，确认保管链没有断裂。"
    report = build_manuscript_quality_report(
        detail=_detail(),
        chapters=_chapters(
            f"{repeated}\n\n他离开档案室。",
            f"警方接管材料。\n\n{repeated}",
        ),
    )

    assert "repeated_paragraph" in {item.code for item in report.blockers}


def test_story_state_conflict_blocks_without_rewriting_accepted_chapters() -> None:
    report = build_manuscript_quality_report(
        detail=_detail(),
        chapters=_chapters("林默核对匿名信来源。", "警方接管原件。"),
        story_state={
            "conflicts": [
                {
                    "subject_id": "story",
                    "property_key": "evidence.ledger.source",
                    "fact_ids": ["fact-1", "fact-2"],
                    "values": ["档案馆", "沈默妻子"],
                }
            ]
        },
    )

    assert [item.code for item in report.blockers] == ["story_state_conflict"]


def test_template_action_overuse_stays_advisory() -> None:
    report = build_manuscript_quality_report(
        detail=_detail(),
        chapters=_chapters(
            "沉默。沉默。沉默。",
            "沉默。警方接管原件。",
        ),
    )

    assert report.blockers == []
    assert "template_action_overuse" in {item.code for item in report.warnings}
