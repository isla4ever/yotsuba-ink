from __future__ import annotations

from novel_workflow.quality.chapter_repair_targets import build_chapter_repair_targets


def test_handoff_targets_first_body_paragraph() -> None:
    content = "第2章 潮声\n\n林澈推开档案室的门。\n\n值班册仍停在昨夜。"
    target = _target(content, "chapter_handoff")

    assert target["operation"] == "expand"
    assert target["selected_text"] == "林澈推开档案室的门。"
    assert target["locatable"] is True


def test_foreshadowing_targets_last_body_paragraph() -> None:
    content = "第2章 潮声\n\n林澈推开档案室的门。\n\n值班册仍停在昨夜。"
    target = _target(content, "foreshadowing")

    assert target["operation"] == "expand"
    assert target["selected_text"] == "值班册仍停在昨夜。"


def test_offsets_use_utf16_code_units_and_bind_the_review_version() -> None:
    content = "第2章 😀\n\n🌊潮声之后，林澈打开母带。"
    target = _target(content, "structure")
    expected_start = len("第2章 😀\n\n".encode("utf-16-le")) // 2

    assert target["start"] == expected_start
    assert target["end"] == expected_start + len(target["selected_text"].encode("utf-16-le")) // 2
    assert target["artifact_signature"] == "signed-chapter-v7"
    assert target["chapter_version"] == 7


def test_worldbuilding_conflict_without_matching_evidence_is_direction_only() -> None:
    content = "第2章 潮声\n\n林澈推开档案室的门。"
    target = _target(content, "worldbuilding_conflict", evidence="世界观硬设定")

    assert target["operation"] == "rewrite"
    assert target["locatable"] is False
    assert target["start"] == target["end"] == 0
    assert target["selected_text"] == ""
    assert target["instruction"]


def test_duplicate_engine_finding_ids_receive_stable_unique_target_ids() -> None:
    targets = build_chapter_repair_targets(
        "正文命中规则甲，也命中规则乙。",
        [
            {
                "id": "text-worldbuilding_conflict",
                "dimension": "worldbuilding_conflict",
                "message": "规则甲",
                "evidence": "规则甲",
            },
            {
                "id": "text-worldbuilding_conflict",
                "dimension": "worldbuilding_conflict",
                "message": "规则乙",
                "evidence": "规则乙",
            },
        ],
        chapter_id="chapter-2",
        chapter="第2章",
        artifact_signature="signed-chapter-v7",
        chapter_version=7,
    )

    assert [target["finding_id"] for target in targets] == [
        "text-worldbuilding_conflict",
        "text-worldbuilding_conflict-2",
    ]


def _target(content: str, dimension: str, *, evidence: str = "") -> dict[str, object]:
    return build_chapter_repair_targets(
        content,
        [{"id": f"text-{dimension}", "dimension": dimension, "message": "质量问题", "evidence": evidence}],
        chapter_id="chapter-2",
        chapter="第2章",
        artifact_signature="signed-chapter-v7",
        chapter_version=7,
    )[0]
