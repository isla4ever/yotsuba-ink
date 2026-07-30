from __future__ import annotations

import re
from typing import Any

from novel_workflow.quality.chapter_continuity import (
    build_transition_directive,
    chapter_handoff_findings,
    resolve_volume_context,
)
from novel_workflow.quality.repair_instructions import quality_revision_instruction
from novel_workflow.quality.voice_drift import voice_drift_findings
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

# Phase 10.0 expansion quotas (see docs/architecture/phase-10-workbench-refactor-and-stage-contract.md §3.2).
INFO_MIN_CHARACTERS = 5
INFO_MAX_CHARACTERS = 9
INFO_MAX_HARD_RULES = 12


def artifact_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(artifact_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(artifact_text(item) for item in value)
    return str(value or "")


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
        voice_spec: dict[str, Any] | None = None,
    ) -> QualityReport:
        text = artifact_text(result)
        findings: list[QualityFinding] = []
        findings.extend(self._structure_findings(node, result, text))
        findings.extend(self._continuity_findings(node, text, story_bible, context_packet))
        findings.extend(self._style_findings(node, text, voice_spec))
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
        return content.rstrip()

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
        text = artifact_text(result)
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
            bible.volumes = _extract_volumes(result)
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source="outline"))
        elif node.type == "detail_outline":
            bible.timeline.append({"stage": "detail_outline", "summary": _compact(text, 260)})
            bible.foreshadow_ledger = _merge_foreshadows(bible.foreshadow_ledger, _extract_foreshadows(text, source="detail_outline"))
        elif node.type == "chapter_text":
            bible.chapter_summaries = [item for item in bible.chapter_summaries if item.get("chapter") != chapter]
            bible.chapter_summaries.append({
                "chapter": chapter,
                "summary": _compact(text, 220),
                "context_kind": context_packet.chapter_kind if context_packet else "normal",
            })
            bible.timeline = [item for item in bible.timeline if item.get("chapter") != chapter]
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
        volume = resolve_volume_context(
            state.story_bible.volumes,
            state.story_bible.chapter_summaries,
            chapter_index=chapter_index,
            total_chapters=total_chapters,
        )
        previous = _previous_chapter_summary(state.story_bible, chapter_index)
        transition = build_transition_directive(
            state.artifacts.get("detail_outline"),
            chapter_index=chapter_index,
            chapter_kind=volume.chapter_kind,
            next_volume_goal=volume.next_goal,
        )
        return ChapterContextPacket(
            chapter=chapter,
            chapter_index=chapter_index,
            chapter_kind=volume.chapter_kind,
            story_brief=str(state.story_brief.get("content") or ""),
            summary=str(state.artifacts.get("summary") or ""),
            volume_goal=volume.goal,
            volume_title=volume.title,
            volume_chapter_range=volume.chapter_range,
            next_volume_goal=volume.next_goal,
            chapter_outline=_chapter_outline(state.artifacts.get("detail_outline"), chapter_index),
            previous_chapter_summary=previous,
            previous_volume_ending=volume.previous_ending,
            transition_directive=transition,
            character_state={node.id: node.model_dump() for node in state.character_graph.nodes},
            open_foreshadows=[item for item in state.story_bible.foreshadow_ledger if item.get("status") != "recovered"][:8],
            world_rules=state.story_bible.world_rules,
        )

    def _structure_findings(self, node: WorkflowNode, result: Any, text: str) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        if node.type == "info_recommend" and isinstance(result, dict):
            findings.extend(self._info_quota_findings(node, result))
        if node.type == "summary" and not any(token in text for token in ("结局", "角色弧", "伏笔", "主线")):
            findings.append(_finding(node.id, "structure", "梗概缺少结局承诺、角色弧或伏笔总账。", text[:120]))
        if node.type == "outline":
            if isinstance(result, dict) and result.get("volumes"):
                return findings
            if not re.search(r"第[一二三四五六七八九十\d]+卷", text):
                findings.append(_finding(node.id, "structure", "分卷大纲未识别到明确卷结构。", text[:120]))
        if node.type == "detail_outline":
            if isinstance(result, dict) and isinstance(result.get("chapters"), list) and result["chapters"]:
                return findings
            if not re.search(r"(第\s*\d+\s*章|Chapter\s*\d+)", text, flags=re.IGNORECASE):
                findings.append(_finding(node.id, "structure", "章节细纲未识别到逐章结构。", text[:120], blocking=True))
        if node.type == "chapter_text" and len(text) < 80:
            findings.append(_finding(node.id, "structure", "正文内容过短，无法支撑章节质量。", text[:120]))
        return findings

    def _info_quota_findings(self, node: WorkflowNode, result: dict[str, Any]) -> list[QualityFinding]:
        findings: list[QualityFinding] = []
        characters = result.get("characters") if isinstance(result.get("characters"), list) else []
        if characters and len(characters) < INFO_MIN_CHARACTERS:
            findings.append(
                _finding(
                    node.id,
                    "expansion_quota",
                    f"主要人物仅 {len(characters)} 名，低于立项基线配额（{INFO_MIN_CHARACTERS}-{INFO_MAX_CHARACTERS} 名）；人物阵容不足会迫使后续阶段违规新增关键角色。",
                    "、".join(str(item.get("name") or "") for item in characters if isinstance(item, dict)),
                )
            )
        if len(characters) > INFO_MAX_CHARACTERS:
            findings.append(
                _finding(
                    node.id,
                    "expansion_quota",
                    f"主要人物 {len(characters)} 名，超过立项基线配额（最多 {INFO_MAX_CHARACTERS} 名）；配角与 NPC 应留给分卷大纲和章节细纲按配额引入。",
                )
            )
        detail = str(result.get("worldbuilding_detail") or "")
        hard_rule_count = len([line for line in re.split(r"[\n；;]", detail) if line.strip()])
        if hard_rule_count > INFO_MAX_HARD_RULES:
            findings.append(
                _finding(
                    node.id,
                    "expansion_quota",
                    f"世界观硬设定 {hard_rule_count} 条，超过基线配额（最多 {INFO_MAX_HARD_RULES} 条）；设定过载会挤占后续阶段的上下文预算。",
                )
            )
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
                if "不得" in rule and _violates_hard_world_rule(text):
                    findings.append(_finding(node.id, "worldbuilding_conflict", f"疑似违反世界观硬设定：{rule}", rule, blocking=True))
        if node.type == "chapter_text" and context_packet:
            findings.extend(chapter_handoff_findings(node.id, text, context_packet))
            if context_packet.open_foreshadows and "伏笔" not in text and "线索" not in text:
                findings.append(_finding(node.id, "foreshadowing", "正文未体现未回收伏笔或线索推进。", str(context_packet.open_foreshadows[:2])))
        return findings

    def _style_findings(
        self,
        node: WorkflowNode,
        text: str,
        voice_spec: dict[str, Any] | None = None,
    ) -> list[QualityFinding]:
        if node.type != "chapter_text":
            return []
        findings: list[QualityFinding] = []
        repeated = len(set(text.split())) < max(1, len(text.split()) // 5)
        if repeated:
            findings.append(_finding(node.id, "template_taste", "文本重复度偏高，存在模板味风险。", text[:120]))
        findings.extend(voice_drift_findings(node.id, text, voice_spec))
        return findings

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
        registered_names = [
            str(item.get("name") or "")
            for item in (context_packet.character_state.values() if context_packet else [])
            if isinstance(item, dict)
        ]
        if any(name and name in text for name in registered_names) or any(token in text for token in ("人物", "关系")):
            hits.append("人物状态")
        return hits

    def _instruction(self, finding: QualityFinding) -> str:
        return quality_revision_instruction(finding)


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


def _extract_volumes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("volumes"), list):
        volumes = []
        for index, item in enumerate(value["volumes"], start=1):
            if not isinstance(item, dict):
                continue
            volumes.append(
                {
                    "name": item.get("title") or f"第{index}卷",
                    "chapter_range": item.get("chapter_range") or "",
                    "goal": item.get("volume_goal") or "",
                    "rhythm": item.get("rhythm") or "",
                    "opening": item.get("opening") or "",
                    "development": item.get("development") or "",
                    "midpoint": item.get("midpoint") or "",
                    "climax": item.get("climax") or "",
                    "resolution": item.get("resolution") or "",
                }
            )
        return volumes
    text = artifact_text(value)
    matches = re.findall(r"(第[一二三四五六七八九十\d]+卷)[：:，, ]?([^。；\n]*)", text)
    if not matches:
        return []
    return [{"name": name, "goal": goal.strip() or "卷目标待细化"} for name, goal in matches]


def _chapter_outline(detail_outline: Any, chapter_index: int) -> str:
    if not isinstance(detail_outline, dict) or not isinstance(detail_outline.get("chapters"), list):
        return ""
    chapters = [item for item in detail_outline["chapters"] if isinstance(item, dict)]
    expected = f"第{chapter_index}章"
    chapter = next((item for item in chapters if str(item.get("chapter") or "").replace(" ", "") == expected), None)
    if chapter is None and 0 < chapter_index <= len(chapters):
        chapter = chapters[chapter_index - 1]
    if chapter is None:
        return ""
    shift = chapter.get("character_shift") if isinstance(chapter.get("character_shift"), dict) else {}
    facts = [item for item in chapter.get("fact_reveals", []) if isinstance(item, dict)]
    wiki = [item for item in chapter.get("wiki_candidates", []) if isinstance(item, dict)]
    clues = [item for item in chapter.get("foreshadow", []) if isinstance(item, dict)]
    lines = [
        f"{chapter.get('chapter', expected)}｜POV：{chapter.get('pov', '')}｜场景：{chapter.get('scene', '')}",
        f"目标：{chapter.get('goal', '')}｜进入状态：{chapter.get('entry_state', '')}",
        f"冲突：{chapter.get('conflict', '')}｜风险：{chapter.get('stakes', '')}",
        "事实：" + "；".join(f"{item.get('anchor', '')}：{item.get('fact', '')}（{item.get('impact', '')}）" for item in facts),
        "Wiki：" + "；".join(f"{item.get('title', '')}：{item.get('fact', '')}" for item in wiki),
        "伏笔：" + "；".join(f"{item.get('name', '')}[{item.get('status', '')}] {item.get('note', '')}" for item in clues),
        f"人物变化：{shift.get('character', '')}｜动机：{shift.get('motivation', '')}｜变化：{shift.get('change', '')}｜影响：{shift.get('impact', '')}",
        f"章末钩子：{chapter.get('hook', '')}｜连续性：{chapter.get('continuity_notes', '')}",
    ]
    return _compact("\n".join(lines), 1200)


def _previous_chapter_summary(story_bible: StoryBibleState, chapter_index: int) -> str:
    if chapter_index <= 1:
        return ""
    expected = f"第{chapter_index - 1}章"
    for item in reversed(story_bible.chapter_summaries):
        if str(item.get("chapter") or "").replace(" ", "") == expected:
            return str(item.get("summary") or "")
    return ""


def _violates_hard_world_rule(text: str) -> bool:
    explicit_patterns = [
        "推翻世界观硬设定",
        "违反世界观硬设定",
        "不再遵守世界观硬设定",
        "推翻已定稿世界观",
        "违反已定稿世界观",
        "世界观硬设定被推翻",
        "硬设定被推翻",
    ]
    return any(pattern in text for pattern in explicit_patterns)
