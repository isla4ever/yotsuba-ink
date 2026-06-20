from __future__ import annotations

import re
from typing import Any

from novel_workflow.workflows.schemas import (
    ChapterContextPacket,
    QualityFinding,
    QualityMode,
    QualityReport,
    RevisionDirective,
    StoryBibleState,
    WorkflowNode,
)


CORE_TEXT_TYPES = {"summary", "outline", "detail_outline", "chapter_text"}


class QualityEngine:
    """Deterministic v1 quality loop for production reliability.

    This is intentionally conservative: it catches continuity and structure risks
    without pretending to be a full literary judge.
    """

    def check_stage(
        self,
        node: WorkflowNode,
        result: Any,
        *,
        story_bible: StoryBibleState,
        mode: QualityMode,
        chapter: str = "",
        context_packet: ChapterContextPacket | None = None,
    ) -> QualityReport:
        text = str(result or "")
        findings: list[QualityFinding] = []
        findings.extend(self._structure_findings(node, text))
        findings.extend(self._continuity_findings(node, text, story_bible, context_packet))
        findings.extend(self._style_findings(node, text))
        blocking = any(item.blocking for item in findings)
        warning_count = sum(1 for item in findings if item.severity == "warning")
        score = max(0.2, round(0.92 - warning_count * 0.06 - (0.28 if blocking else 0), 2))
        return QualityReport(
            node_id=node.id,
            node_type=node.type,
            label=node.label,
            chapter=chapter,
            score=score,
            passed=not blocking and score >= node.quality_policy.min_score,
            mode=mode,
            findings=findings,
            constraint_hits=self._constraint_hits(node, text, story_bible, context_packet),
            revision_required=not blocking and bool(findings) and mode in {"balanced", "deep"},
        )

    def directive_for(self, report: QualityReport) -> RevisionDirective | None:
        fixable = [item for item in report.findings if not item.blocking]
        if not fixable:
            return None
        primary = fixable[0]
        return RevisionDirective(
            id=f"rev-{report.node_id}-{report.chapter or 'stage'}-{len(report.findings)}",
            node_id=report.node_id,
            chapter=report.chapter,
            severity=primary.severity,
            issue=primary.message,
            evidence=primary.evidence,
            target=primary.target or report.chapter or report.node_id,
            instruction=self._instruction(primary),
        )

    def apply_directive(self, content: str, directive: RevisionDirective) -> str:
        directive.status = "applied"
        directive.attempts += 1
        note = (
            f"\n\n[质量修订]\n"
            f"- 问题：{directive.issue}\n"
            f"- 修订动作：{directive.instruction}\n"
            f"- 处理范围：{directive.target or '当前产物'}\n"
        )
        return f"{content.rstrip()}{note}"

    def update_story_bible(
        self,
        story_bible: StoryBibleState,
        node: WorkflowNode,
        result: Any,
        *,
        chapter: str = "",
        context_packet: ChapterContextPacket | None = None,
    ) -> StoryBibleState:
        bible = story_bible.model_copy(deep=True)
        text = str(result or "")
        if node.type == "info_recommend":
            bible.world_rules = _unique([*bible.world_rules, "世界观硬设定不得被后续阶段推翻", "人物关系变化必须有事件触发", "伏笔需记录投放与回收状态"])
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source="story_brief"))
            if not bible.foreshadow_ledger:
                bible.foreshadow_ledger = _merge_foreshadows(
                    bible.foreshadow_ledger,
                    [{"id": "fs-story-brief-core", "source": "story_brief", "summary": "创作立项阶段保留一条核心长线伏笔，后续细纲和正文必须投放、推进或回收。", "status": "open"}],
                )
        elif node.type == "summary":
            bible.timeline.append({"stage": "summary", "summary": _compact(text, 260)})
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source="summary"))
        elif node.type == "outline":
            bible.volumes = _extract_volumes(text)
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source="outline"))
        elif node.type == "detail_outline":
            bible.timeline.append({"stage": "detail_outline", "summary": _compact(text, 260)})
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source="detail_outline"))
        elif node.type == "chapter_text":
            bible.chapter_summaries.append({
                "chapter": chapter,
                "summary": _compact(text, 220),
                "context_kind": context_packet.chapter_kind if context_packet else "normal",
            })
            bible.timeline.append({"chapter": chapter, "event": _compact(text, 160)})
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source=chapter or "chapter_text"))
        bible.updated_by = f"{node.id}:{chapter}" if chapter else node.id
        return bible

    def build_chapter_context(
        self,
        *,
        chapter_index: int,
        total_chapters: int,
        state: Any,
    ) -> ChapterContextPacket:
        chapter = f"第{chapter_index}章"
        kind = "first" if chapter_index == 1 else "finale" if chapter_index == total_chapters else "normal"
        if chapter_index > 1 and (chapter_index - 1) % 6 == 0:
            kind = "volume_start"
        if chapter_index % 6 == 0 and chapter_index != total_chapters:
            kind = "volume_end"
        previous = state.story_bible.chapter_summaries[-1]["summary"] if state.story_bible.chapter_summaries else ""
        return ChapterContextPacket(
            chapter=chapter,
            chapter_index=chapter_index,
            chapter_kind=kind,
            story_brief=str(state.story_brief.get("content") or ""),
            summary=str(state.artifacts.get("summary") or ""),
            volume_goal=_volume_goal(state.story_bible, chapter_index),
            chapter_outline=_chapter_outline(str(state.artifacts.get("detail_outline") or ""), chapter_index),
            previous_chapter_summary=previous,
            previous_volume_ending=_previous_volume_ending(state.story_bible),
            character_state={node.id: node.model_dump() for node in state.character_graph.nodes},
            open_foreshadows=[item for item in state.story_bible.foreshadow_ledger if item.get("status") != "recovered"][:8],
            world_rules=state.story_bible.world_rules,
        )

    def _structure_findings(self, node: WorkflowNode, text: str) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        if node.type == "summary" and not any(token in text for token in ("结局", "角色弧", "伏笔", "主线")):
            findings.append(_finding(node.id, "structure", "梗概缺少结局承诺、角色弧或伏笔总账。", text[:120]))
        if node.type == "outline" and not re.search(r"第[一二三四五六七八九十\d]+卷", text):
            findings.append(_finding(node.id, "structure", "分卷大纲未识别到明确卷结构。", text[:120]))
        if node.type == "detail_outline" and not re.search(r"第\s*\d+\s*章", text):
            findings.append(_finding(node.id, "structure", "章节细纲未识别到逐章结构。", text[:120], blocking=True))
        if node.type == "chapter_text" and len(text) < 80:
            findings.append(_finding(node.id, "structure", "正文内容过短，无法支撑章节质量。", text[:120]))
        return findings

    def _continuity_findings(
        self,
        node: WorkflowNode,
        text: str,
        story_bible: StoryBibleState,
        context_packet: ChapterContextPacket | None,
    ) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        if node.type in CORE_TEXT_TYPES:
            for rule in story_bible.world_rules:
                if "不得" in rule and _contradiction_token(rule) in text:
                    findings.append(_finding(node.id, "worldbuilding_conflict", f"疑似违反世界观硬设定：{rule}", rule, blocking=True))
        if node.type == "chapter_text" and context_packet:
            if context_packet.previous_chapter_summary and not any(token in text for token in ("承接", "继续", "上一", "此前", "旧")):
                findings.append(_finding(node.id, "chapter_handoff", "正文缺少上一章承接信号。", context_packet.previous_chapter_summary[:120]))
            if context_packet.open_foreshadows and "伏笔" not in text and "线索" not in text:
                findings.append(_finding(node.id, "foreshadowing", "正文未体现未回收伏笔或线索推进。", str(context_packet.open_foreshadows[:2])))
        return findings

    def _style_findings(self, node: WorkflowNode, text: str) -> list[QualityFinding]:
        if node.type != "chapter_text":
            return []
        repeated = len(set(text.split())) < max(1, len(text.split()) // 5)
        if repeated:
            return [_finding(node.id, "template_taste", "文本重复度偏高，存在模板味风险。", text[:120])]
        return []

    def _constraint_hits(
        self,
        node: WorkflowNode,
        text: str,
        story_bible: StoryBibleState,
        context_packet: ChapterContextPacket | None,
    ) -> list[str]:
        hits = []
        if story_bible.world_rules:
            hits.append("世界观硬设定")
        if story_bible.foreshadow_ledger:
            hits.append("伏笔账本")
        if context_packet and context_packet.previous_chapter_summary:
            hits.append("上一章摘要")
        if any(token in text for token in ("人物", "关系", "林", "沈", "周")):
            hits.append("人物状态")
        return hits

    def _instruction(self, finding: QualityFinding) -> str:
        instructions = {
            "chapter_handoff": "在当前章节开头或关键转折处补足上一章事件承接，不改变章节主目标。",
            "foreshadowing": "加入一个与未回收伏笔相关的动作、线索或人物反应，避免直接揭底。",
            "template_taste": "压缩重复表达，增加具体感官、动作和人物动机。",
            "structure": "补齐缺失结构字段，保持与上游 Story Brief 和 Wiki 约束一致。",
        }
        return instructions.get(finding.dimension, "局部修订该问题，保持主线、人物状态和世界观硬设定不变。")


def _finding(node_id: str, dimension: str, message: str, evidence: str = "", *, blocking: bool = False) -> QualityFinding:
    return QualityFinding(
        id=f"{node_id}-{dimension}",
        dimension=dimension,
        severity="blocking" if blocking else "warning",
        message=message,
        evidence=evidence,
        target=node_id,
        blocking=blocking,
    )


def _compact(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else f"{clean[:limit]}..."


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _extract_foreshadows(text: str, *, source: str) -> list[dict[str, Any]]:
    if "伏笔" not in text and "线索" not in text:
        return []
    return [{"id": f"fs-{abs(hash(source + text[:80])) % 100000}", "source": source, "summary": _compact(text, 160), "status": "open"}]


def _merge_foreshadows(current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("id")): item for item in current}
    for item in incoming:
        by_id.setdefault(str(item.get("id")), item)
    return list(by_id.values())[-30:]


def _extract_volumes(text: str) -> list[dict[str, Any]]:
    matches = re.findall(r"(第[一二三四五六七八九十\d]+卷)[：:，, ]?([^。；\n]*)", text)
    if not matches:
        return []
    return [{"name": name, "goal": goal.strip() or "卷目标待细化"} for name, goal in matches]


def _volume_goal(story_bible: StoryBibleState, chapter_index: int) -> str:
    if not story_bible.volumes:
        return ""
    volume_index = min(len(story_bible.volumes) - 1, max(0, (chapter_index - 1) // 6))
    return str(story_bible.volumes[volume_index].get("goal") or "")


def _chapter_outline(detail_outline: str, chapter_index: int) -> str:
    pattern = rf"第\s*{chapter_index}\s*章[：: ]?(.*?)(?=第\s*{chapter_index + 1}\s*章|$)"
    match = re.search(pattern, detail_outline, flags=re.S)
    return _compact(match.group(0), 420) if match else ""


def _previous_volume_ending(story_bible: StoryBibleState) -> str:
    for item in reversed(story_bible.chapter_summaries):
        if item.get("context_kind") == "volume_end":
            return str(item.get("summary") or "")
    return ""


def _contradiction_token(rule: str) -> str:
    if "不得" in rule:
        return "推翻"
    return "冲突"
