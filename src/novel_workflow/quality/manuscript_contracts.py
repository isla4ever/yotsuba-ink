from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.output_contracts.artifacts_vnext import ChapterArtifact, DetailArtifact


class ManuscriptFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    severity: Literal["blocking", "warning"]
    chapter_refs: list[str] = Field(default_factory=list, max_length=48)
    evidence: str = Field(min_length=1, max_length=2000)
    required_action: str = Field(min_length=1, max_length=2000)
    source: Literal["deterministic", "reviewer"] = "deterministic"


class ManuscriptQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(pattern=r"^manuscript-quality-[a-f0-9]{20}$")
    chapter_count: int = Field(ge=1)
    structure_contract: Literal["passed", "blocked"]
    blockers: list[ManuscriptFinding] = Field(default_factory=list, max_length=128)
    warnings: list[ManuscriptFinding] = Field(default_factory=list, max_length=256)
    template_action_counts: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_status(self) -> "ManuscriptQualityReport":
        if (self.structure_contract == "blocked") != bool(self.blockers):
            raise ValueError("Manuscript structure status must match deterministic blockers")
        if any(item.severity != "blocking" for item in self.blockers):
            raise ValueError("Manuscript blockers must use blocking severity")
        if any(item.severity != "warning" for item in self.warnings):
            raise ValueError("Manuscript warnings must use warning severity")
        return self


_TEMPLATE_ACTIONS = (
    "沉默",
    "没有说话",
    "没有回答",
    "停了一下",
    "指节泛白",
    "声音压低",
    "手指收紧",
)
_CHINESE_QUOTE_PAIRS = {"“": "”", "‘": "’", "《": "》"}


def build_manuscript_quality_report(
    *,
    detail: DetailArtifact,
    chapters: Iterable[ChapterArtifact],
    story_state: dict[str, Any] | None = None,
    review_findings: Iterable[dict[str, Any]] = (),
) -> ManuscriptQualityReport:
    accepted = list(chapters)
    blockers: list[ManuscriptFinding] = []
    warnings: list[ManuscriptFinding] = []
    blockers.extend(_chapter_set_findings(detail, accepted))
    blockers.extend(_quote_findings(accepted))
    blockers.extend(_repeated_text_findings(accepted))
    blockers.extend(_story_state_conflict_findings(story_state or {}))
    warnings.extend(_review_warnings(review_findings))
    template_counts = _template_action_counts(accepted)
    warnings.extend(_template_action_findings(template_counts, len(accepted)))
    blockers = _deduplicate(blockers)
    warnings = _deduplicate(warnings)
    body = {
        "chapter_refs": [chapter.chapter_id for chapter in accepted],
        "chapter_versions": [chapter.version_id for chapter in accepted],
        "blockers": [item.model_dump(mode="json") for item in blockers],
        "warnings": [item.model_dump(mode="json") for item in warnings],
        "template_action_counts": template_counts,
    }
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return ManuscriptQualityReport(
        report_id=f"manuscript-quality-{digest[:20]}",
        chapter_count=len(accepted),
        structure_contract="blocked" if blockers else "passed",
        blockers=blockers,
        warnings=warnings,
        template_action_counts=template_counts,
    )


def _chapter_set_findings(
    detail: DetailArtifact,
    chapters: list[ChapterArtifact],
) -> list[ManuscriptFinding]:
    planned = [chapter.ref for chapter in detail.chapters]
    actual = [chapter.chapter_id for chapter in chapters]
    findings: list[ManuscriptFinding] = []
    if actual != planned:
        findings.append(
            ManuscriptFinding(
                code="manuscript_chapter_set_mismatch",
                severity="blocking",
                chapter_refs=list(dict.fromkeys([*planned, *actual]))[:48],
                evidence=f"Detail chapters={planned}; accepted chapters={actual}",
                required_action="补齐并按冻结顺序提交每一章 accepted 版本。",
            )
        )
    for planned_chapter, accepted in zip(detail.chapters, chapters):
        if accepted.author_status != "accepted" or accepted.title != planned_chapter.title:
            findings.append(
                ManuscriptFinding(
                    code="manuscript_chapter_identity_mismatch",
                    severity="blocking",
                    chapter_refs=[planned_chapter.ref],
                    evidence=(
                        f"planned title={planned_chapter.title}; accepted title={accepted.title}; "
                        f"status={accepted.author_status}"
                    ),
                    required_action="使用与冻结 Detail 章号和章题一致的 accepted 版本。",
                )
            )
    return findings


def _quote_findings(chapters: list[ChapterArtifact]) -> list[ManuscriptFinding]:
    findings: list[ManuscriptFinding] = []
    for chapter in chapters:
        stack: list[tuple[str, int]] = []
        mismatch = ""
        for index, character in enumerate(chapter.content):
            if character in _CHINESE_QUOTE_PAIRS:
                stack.append((character, index))
            elif character in _CHINESE_QUOTE_PAIRS.values():
                if not stack or _CHINESE_QUOTE_PAIRS[stack[-1][0]] != character:
                    mismatch = f"unexpected {character} at offset {index}"
                    break
                stack.pop()
        if not mismatch and stack:
            mismatch = f"unclosed {stack[-1][0]} at offset {stack[-1][1]}"
        if not mismatch and _unescaped_ascii_quote_count(chapter.content) % 2:
            mismatch = "odd number of ASCII double quotes"
        if mismatch:
            findings.append(
                ManuscriptFinding(
                    code="punctuation_quote_unbalanced",
                    severity="blocking",
                    chapter_refs=[chapter.chapter_id],
                    evidence=mismatch,
                    required_action="修复引号嵌套或缺失的闭合符号后重新提交当前章节版本。",
                )
            )
    return findings


def _repeated_text_findings(chapters: list[ChapterArtifact]) -> list[ManuscriptFinding]:
    paragraphs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    windows: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for chapter in chapters:
        for paragraph in re.split(r"\n\s*\n+", chapter.content):
            normalized = _normalized_prose(paragraph)
            if len(normalized) >= 20:
                paragraphs[normalized].append((chapter.chapter_id, paragraph.strip()))
        sentences = [
            item.strip()
            for item in re.split(r"(?<=[。！？!?])", chapter.content)
            if item.strip()
        ]
        for index in range(max(0, len(sentences) - 1)):
            text = "".join(sentences[index : index + 2])
            normalized = _normalized_prose(text)
            if len(normalized) >= 30:
                windows[normalized].append((chapter.chapter_id, text))
    findings: list[ManuscriptFinding] = []
    for code, groups in (
        ("repeated_paragraph", paragraphs),
        ("repeated_passage", windows),
    ):
        for occurrences in groups.values():
            refs = [chapter_ref for chapter_ref, _ in occurrences]
            if len(occurrences) < 2:
                continue
            findings.append(
                ManuscriptFinding(
                    code=code,
                    severity="blocking",
                    chapter_refs=list(dict.fromkeys(refs))[:48],
                    evidence=occurrences[0][1][:240],
                    required_action="删除机械复制的正文，只保留承担独立戏剧任务的一处。",
                )
            )
    return findings


def _story_state_conflict_findings(state: dict[str, Any]) -> list[ManuscriptFinding]:
    return [
        ManuscriptFinding(
            code="story_state_conflict",
            severity="blocking",
            chapter_refs=[],
            evidence=(
                f"{conflict.get('subject_id')}.{conflict.get('property_key')} has competing "
                f"values {conflict.get('values')} from {conflict.get('fact_ids')}"
            ),
            required_action="显式 supersede/refute 冲突事实，或从对应章节 checkpoint 创建修订分支。",
        )
        for conflict in state.get("conflicts") or []
        if isinstance(conflict, dict)
    ]


def _review_warnings(findings: Iterable[dict[str, Any]]) -> list[ManuscriptFinding]:
    result: list[ManuscriptFinding] = []
    for finding in findings:
        evidence = str(finding.get("evidence") or "").strip()
        claim = str(finding.get("claim") or finding.get("code") or "审稿建议").strip()
        result.append(
            ManuscriptFinding(
                code=str(finding.get("code") or "review_warning")[:120],
                severity="warning",
                chapter_refs=[str(finding.get("chapter_id"))]
                if finding.get("chapter_id")
                else [],
                evidence=f"{claim}" + (f"；证据：{evidence[:240]}" if evidence else ""),
                required_action="由作者判断是否从对应 checkpoint 创建修订分支；系统不自动改写历史章节。",
                source="reviewer",
            )
        )
    return result


def _template_action_counts(chapters: list[ChapterArtifact]) -> dict[str, int]:
    content = "\n".join(chapter.content for chapter in chapters)
    return {phrase: content.count(phrase) for phrase in _TEMPLATE_ACTIONS if phrase in content}


def _template_action_findings(
    counts: dict[str, int],
    chapter_count: int,
) -> list[ManuscriptFinding]:
    threshold = max(4, (chapter_count + 1) // 2)
    return [
        ManuscriptFinding(
            code="template_action_overuse",
            severity="warning",
            chapter_refs=[],
            evidence=f"‘{phrase}’出现 {count} 次（提示阈值 {threshold}）。",
            required_action="结合各人物 speech_style 与 temperament 检查动作词库是否同质化。",
        )
        for phrase, count in counts.items()
        if count >= threshold
    ]


def _unescaped_ascii_quote_count(content: str) -> int:
    return sum(
        1
        for index, character in enumerate(content)
        if character == '"' and (index == 0 or content[index - 1] != "\\")
    )


def _normalized_prose(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def _deduplicate(findings: list[ManuscriptFinding]) -> list[ManuscriptFinding]:
    result: list[ManuscriptFinding] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for finding in findings:
        key = (finding.code, tuple(finding.chapter_refs), finding.evidence)
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result


__all__ = [
    "ManuscriptFinding",
    "ManuscriptQualityReport",
    "build_manuscript_quality_report",
]
