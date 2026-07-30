from novel_workflow.quality.chapter_continuity import (
    build_transition_directive,
    chapter_handoff_findings,
    resolve_volume_context,
)
from novel_workflow.workflows.schemas import ChapterContextPacket


def test_volume_context_uses_confirmed_chapter_ranges_instead_of_fixed_six_chapter_buckets():
    volumes = [
        {"name": "第一卷", "chapter_range": "第1-3章", "goal": "找到母带来源"},
        {"name": "第二卷", "chapter_range": "第4-8章", "goal": "公开证据链"},
    ]
    summaries = [{"chapter": "第3章", "summary": "林拾公开第一段母带，港务会开始追捕。"}]

    volume_end = resolve_volume_context(volumes, summaries, chapter_index=3, total_chapters=8)
    volume_start = resolve_volume_context(volumes, summaries, chapter_index=4, total_chapters=8)

    assert volume_end.chapter_kind == "volume_end"
    assert volume_end.next_goal == "公开证据链"
    assert volume_start.chapter_kind == "volume_start"
    assert volume_start.title == "第二卷"
    assert volume_start.goal == "公开证据链"
    assert volume_start.previous_ending == "林拾公开第一段母带，港务会开始追捕。"


def test_transition_directive_defaults_to_continuation_and_marks_planned_pov_shift():
    detail = {
        "chapters": [
            {"chapter": "第1章", "pov": "林拾", "scene": "档案馆", "hook": "沈决带走母带"},
            {"chapter": "第2章", "pov": "沈决", "scene": "海关码头", "entry_state": "沈决带着母带接受盘查", "continuity_notes": "承接母带被带走的结果"},
        ]
    }

    directive = build_transition_directive(detail, chapter_index=2, chapter_kind="normal", next_volume_goal="")

    assert "视角由林拾转到沈决" in directive
    assert "上一章结果" in directive
    assert "前章钩子：沈决带走母带" in directive
    assert "禁止自行倒叙" in directive


def test_transition_directive_allows_only_explicit_flashback_and_preserves_handoff_anchor():
    detail = {
        "chapters": [
            {"chapter": "第1章", "pov": "林拾", "scene": "码头", "hook": "7A-13 母带在火中发出求救声"},
            {
                "chapter": "第2章",
                "pov": "林拾",
                "scene": "十年前的档案馆",
                "entry_state": "林拾被母带声音触发闪回，回到十年前第一次见到母带的时刻",
                "continuity_notes": "倒叙只用于解释母带来源，回到现在时必须保留火场后果",
            },
        ]
    }

    directive = build_transition_directive(detail, chapter_index=2, chapter_kind="normal", next_volume_goal="")

    assert "细纲明确的倒叙/闪回" in directive
    assert "前章钩子：7A-13 母带在火中发出求救声" in directive
    assert "本章进入状态" in directive


def test_transition_directive_distinguishes_volume_start_and_volume_end_obligations():
    detail = {
        "chapters": [
            {"chapter": "第3章", "hook": "港务会封锁第一批证据"},
            {"chapter": "第4章", "entry_state": "封锁令迫使林拾转入地下调查"},
            {"chapter": "第8章", "entry_state": "林拾取得完整删改日志"},
        ]
    }

    volume_start = build_transition_directive(
        detail, chapter_index=4, chapter_kind="volume_start", next_volume_goal="追查幕后主使"
    )
    volume_end = build_transition_directive(
        detail, chapter_index=8, chapter_kind="volume_end", next_volume_goal="追查幕后主使"
    )

    assert "卷首不是故事重启" in volume_start
    assert "上一卷结局造成的后果" in volume_start
    assert "卷末必须结算本卷阶段目标" in volume_end
    assert "追查幕后主使" in volume_end


def test_handoff_quality_uses_story_anchors_instead_of_literal_previous_chapter_words():
    packet = ChapterContextPacket(
        chapter="第2章",
        chapter_index=2,
        previous_chapter_summary="林拾发现 7A-13 母带，并决定联系沈决。",
        chapter_outline="沈决带着母带进入海关码头。",
        character_state={"lin": {"name": "林拾"}, "shen": {"name": "沈决"}},
    )

    continuous = chapter_handoff_findings("text", "沈决把 7A-13 母带压在证物袋下，盘查队已经封住出口。", packet)
    disconnected = chapter_handoff_findings("text", "陌生城市的清晨，一个无关人物开始了新的日常。", packet)

    assert continuous == []
    assert [finding.dimension for finding in disconnected] == ["chapter_handoff"]
