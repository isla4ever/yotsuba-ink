from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from novel_workflow.workflows.schemas import ChapterContextPacket, QualityFinding


@dataclass(frozen=True)
class VolumeContext:
    title: str
    chapter_range: str
    goal: str
    next_goal: str
    chapter_kind: str
    previous_ending: str


def resolve_volume_context(
    volumes: list[dict[str, Any]],
    chapter_summaries: list[dict[str, Any]],
    *,
    chapter_index: int,
    total_chapters: int,
) -> VolumeContext:
    spans = _volume_spans(volumes, total_chapters)
    current_index = next((index for index, (_, start, end) in enumerate(spans) if start <= chapter_index <= end), 0)
    current, start, end = spans[current_index]
    if chapter_index == 1:
        kind = "first"
    elif chapter_index == total_chapters:
        kind = "finale"
    elif chapter_index == start:
        kind = "volume_start"
    elif chapter_index == end:
        kind = "volume_end"
    else:
        kind = "normal"
    previous_ending = _chapter_summary(chapter_summaries, chapter_index - 1) if kind == "volume_start" else ""
    next_goal = str(spans[current_index + 1][0].get("goal") or "") if current_index + 1 < len(spans) else ""
    return VolumeContext(
        title=str(current.get("name") or current.get("title") or f"第{current_index + 1}卷"),
        chapter_range=str(current.get("chapter_range") or f"第{start}-{end}章"),
        goal=str(current.get("goal") or current.get("volume_goal") or ""),
        next_goal=next_goal,
        chapter_kind=kind,
        previous_ending=previous_ending,
    )


def build_transition_directive(
    detail_outline: Any,
    *,
    chapter_index: int,
    chapter_kind: str,
    next_volume_goal: str,
) -> str:
    current = _detail_chapter(detail_outline, chapter_index)
    previous = _detail_chapter(detail_outline, chapter_index - 1)
    entry_state = str(current.get("entry_state") or "").strip()
    continuity = str(current.get("continuity_notes") or "").strip()
    previous_hook = str(previous.get("hook") or "").strip()
    current_pov = str(current.get("pov") or "").strip()
    previous_pov = str(previous.get("pov") or "").strip()
    shift_source = f"{entry_state}\n{continuity}"

    if any(token in shift_source for token in ("倒叙", "回忆段", "追忆", "闪回")):
        transition = "细纲明确的倒叙/闪回"
    elif any(token in shift_source for token in ("时间跳跃", "时间跳切", "多年后", "数日后", "翌日", "次日")):
        transition = "细纲明确的时间跳切"
    elif current_pov and previous_pov and current_pov != previous_pov:
        transition = f"视角由{previous_pov}转到{current_pov}"
    elif current.get("scene") and previous.get("scene") and current.get("scene") != previous.get("scene"):
        transition = "连续因果下的场景转换"
    else:
        transition = "连续续写"

    if chapter_kind == "first":
        instruction = "首章从细纲进入状态起笔，建立人物当下目标，不虚构前情。"
    elif chapter_kind == "volume_start":
        instruction = "卷首不是故事重启；先呈现上一卷结局造成的后果，再启动本卷目标。"
    elif chapter_kind == "volume_end":
        target = f"，并为下一卷目标“{next_volume_goal}”留下可执行因果" if next_volume_goal else ""
        instruction = f"卷末必须结算本卷阶段目标{target}，不能只用悬念突然截断。"
    elif chapter_kind == "finale":
        instruction = "终章结算主冲突、人物选择与承诺，不再开启无法回收的新主线。"
    else:
        instruction = "默认沿上一章结果向下续写，用因果或人物反应抵达本章进入状态，禁止重新介绍故事。"

    anchors = []
    if previous_hook:
        anchors.append(f"前章钩子：{previous_hook}")
    if entry_state:
        anchors.append(f"本章进入状态：{entry_state}")
    anchor_text = "；".join(anchors)
    shift_rule = "除非细纲明确要求，禁止自行倒叙、跨时段或切换视角。"
    return f"转场类型：{transition}。{instruction}{shift_rule}" + (f"承接锚点：{anchor_text}。" if anchor_text else "")


def chapter_handoff_findings(node_id: str, text: str, packet: ChapterContextPacket) -> list[QualityFinding]:
    if not packet.previous_chapter_summary:
        return []
    opening = text[:900]
    findings: list[QualityFinding] = []
    handoff_source = f"{packet.previous_chapter_summary}\n{packet.transition_directive}"
    anchors = _known_anchors(handoff_source, packet)
    if anchors and not any(anchor in opening for anchor in anchors):
        findings.append(_finding(
            node_id,
            "chapter_handoff",
            "本章开篇未承接上一章的核心人物、物证或线索，存在剧情断层风险。",
            "、".join(anchors[:5]),
        ))
    if packet.chapter_kind == "volume_start" and packet.previous_volume_ending:
        volume_anchors = _known_anchors(
            f"{packet.previous_volume_ending}\n{packet.transition_directive}",
            packet,
        )
        if volume_anchors and not any(anchor in opening for anchor in volume_anchors):
            findings.append(_finding(
                node_id,
                "volume_handoff",
                "卷首未呈现上一卷结局的后果，像重新开始了另一段故事。",
                packet.previous_volume_ending[:140],
            ))
    return findings


def _volume_spans(volumes: list[dict[str, Any]], total: int) -> list[tuple[dict[str, Any], int, int]]:
    usable = [item for item in volumes if isinstance(item, dict)]
    if not usable:
        return [({}, 1, max(1, total))]
    parsed = [_range_bounds(str(item.get("chapter_range") or "")) for item in usable]
    if all(bounds is not None for bounds in parsed):
        return [(item, bounds[0], bounds[1]) for item, bounds in zip(usable, parsed) if bounds is not None]
    width = max(1, math.ceil(total / len(usable)))
    return [(item, index * width + 1, min(total, (index + 1) * width)) for index, item in enumerate(usable)]


def _range_bounds(value: str) -> tuple[int, int] | None:
    numbers = [int(item) for item in re.findall(r"\d+", value)]
    if len(numbers) < 2:
        return None
    start, end = numbers[0], numbers[-1]
    return (start, end) if start > 0 and end >= start else None


def _chapter_summary(items: list[dict[str, Any]], chapter_index: int) -> str:
    expected = f"第{chapter_index}章"
    for item in reversed(items):
        if str(item.get("chapter") or "").replace(" ", "") == expected:
            return str(item.get("summary") or "")
    return ""


def _detail_chapter(detail_outline: Any, chapter_index: int) -> dict[str, Any]:
    if chapter_index < 1 or not isinstance(detail_outline, dict):
        return {}
    chapters = [item for item in detail_outline.get("chapters", []) if isinstance(item, dict)]
    expected = f"第{chapter_index}章"
    return next((item for item in chapters if str(item.get("chapter") or "").replace(" ", "") == expected), chapters[chapter_index - 1] if chapter_index <= len(chapters) else {})


def _known_anchors(source: str, packet: ChapterContextPacket) -> list[str]:
    anchors = []
    for key, value in packet.character_state.items():
        record = value if isinstance(value, dict) else {}
        name = str(record.get("name") or key).strip()
        if name and name in source:
            anchors.append(name)
    anchors.extend(re.findall(r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{3,}", source))
    for item in packet.open_foreshadows:
        name = str(item.get("name") or "").strip()
        if name and name in source:
            anchors.append(name)
    return list(dict.fromkeys(anchors))


def _finding(node_id: str, dimension: str, message: str, evidence: str) -> QualityFinding:
    return QualityFinding(
        id=f"{node_id}-{dimension}",
        dimension=dimension,
        severity="warning",
        message=message,
        evidence=evidence,
        target=node_id,
        blocking=False,
    )
