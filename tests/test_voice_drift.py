from __future__ import annotations

from novel_workflow.quality.engine import QualityEngine
from novel_workflow.quality.repair_instructions import quality_revision_instruction
from novel_workflow.quality.voice_drift import (
    parse_declared_dialogue_ratio,
    voice_drift_findings,
    voice_metrics,
    voice_spec_from_state,
)
from novel_workflow.workflows.schemas import NovelRunState, QualityReport, StoryBibleState
from novel_workflow.workflows.templates import default_workflow


NODE_ID = "text"


def _text_node():
    return next(node for node in default_workflow().nodes if node.id == "text")


def test_banned_word_hits_reported_with_counts() -> None:
    spec = {"banned_words": ["竟然", "不由得"], "cliche_slots": []}
    text = "他竟然停住了脚步。她不由得后退，竟然又向前一步。"
    findings = voice_drift_findings(NODE_ID, text, spec)
    banned = [item for item in findings if item.dimension == "voice_banned_word"]
    assert len(banned) == 1
    assert "竟然×2" in banned[0].evidence
    assert "不由得×1" in banned[0].evidence
    assert banned[0].severity == "warning"
    assert banned[0].blocking is False


def test_cliche_slot_hits_reported() -> None:
    spec = {"cliche_slots": ["嘴角勾起一抹微笑"]}
    text = "他嘴角勾起一抹微笑，转身离开了码头。"
    findings = voice_drift_findings(NODE_ID, text, spec)
    assert [item.dimension for item in findings if item.dimension == "voice_cliche"] == ["voice_cliche"]


def test_dialogue_ratio_deviation_flagged_when_rhythm_declares_ratio() -> None:
    spec = {"rhythm": "对话叙述比 6:4，整体紧凑"}
    text = "\n".join(["他沿着堤岸走了很久。"] * 8)
    findings = voice_drift_findings(NODE_ID, text, spec)
    ratio = [item for item in findings if item.dimension == "voice_dialogue_ratio"]
    assert len(ratio) == 1
    assert "60%" in ratio[0].message


def test_dialogue_ratio_skipped_when_rhythm_unparsable() -> None:
    spec = {"rhythm": "以对话推动节奏，叙述保持克制"}
    text = "\n".join(["他沿着堤岸走了很久。"] * 8)
    findings = voice_drift_findings(NODE_ID, text, spec)
    assert not [item for item in findings if item.dimension == "voice_dialogue_ratio"]
    assert parse_declared_dialogue_ratio("以对话推动节奏") is None


def test_dialogue_ratio_within_tolerance_not_flagged() -> None:
    spec = {"rhythm": "对话叙述比 5:5"}
    lines = ["「你听见了吗？」她问。"] * 4 + ["雾从堤岸漫上来。"] * 4
    findings = voice_drift_findings(NODE_ID, "\n".join(lines), spec)
    assert not [item for item in findings if item.dimension == "voice_dialogue_ratio"]


def test_sentence_length_is_report_only_without_rhythm_preference() -> None:
    long_sentence = "他在浓雾里沿着旧港的堤岸一路向北走了很久很久也没有停下来回头看一眼那些渐渐熄灭的灯火和码头。"
    metrics = voice_metrics(long_sentence * 3)
    assert metrics["average_sentence_chars"] > 40
    assert metrics["sentence_count"] == 3
    assert "long_sentence_count" in metrics
    findings = voice_drift_findings(NODE_ID, long_sentence * 3, {"rhythm": "整体紧凑"})
    assert not [item for item in findings if item.dimension == "voice_sentence_length"]


def test_sentence_length_flagged_when_rhythm_declares_short_preference() -> None:
    long_sentence = "他在浓雾里沿着旧港的堤岸一路向北走了很久很久也没有停下来回头看一眼那些渐渐熄灭的灯火和码头。"
    findings = voice_drift_findings(NODE_ID, long_sentence * 3, {"rhythm": "以短句为主"})
    flagged = [item for item in findings if item.dimension == "voice_sentence_length"]
    assert len(flagged) == 1
    assert "平均句长" in flagged[0].message


def test_no_voice_spec_produces_no_findings() -> None:
    assert voice_drift_findings(NODE_ID, "任意正文内容。", None) == []
    state = NovelRunState(run_id="r", project_id="p", workflow_id="w")
    assert voice_spec_from_state(state) is None
    state.artifacts["info_recommend"] = {"selected_title": "无规格"}
    assert voice_spec_from_state(state) is None


def test_engine_style_findings_include_voice_drift_and_targeted_instruction() -> None:
    engine = QualityEngine()
    node = _text_node()
    spec = {"banned_words": ["竟然"], "cliche_slots": [], "rhythm": ""}
    content = "第1章 正文。他竟然回头，承接上一章的线索走进档案馆。" + "雾气在他身后聚拢，脚步声与旧日的伏笔一起沉进走廊深处。" * 4
    report: QualityReport = engine.check_stage(
        node,
        content,
        story_bible=StoryBibleState(),
        mode="balanced",
        chapter="第1章",
        voice_spec=spec,
    )
    voice_findings = [item for item in report.findings if item.dimension == "voice_banned_word"]
    assert len(voice_findings) == 1
    directive = engine.directive_for(report)
    assert directive is not None
    assert directive.instruction.startswith("定向修写")
    assert "竟然" in directive.instruction
    assert quality_revision_instruction(voice_findings[0]).startswith("定向修写")
