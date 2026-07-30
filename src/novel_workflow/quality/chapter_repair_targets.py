from __future__ import annotations

import re
from typing import Any, Iterable

from novel_workflow.quality.repair_instructions import quality_revision_instruction


MAX_REPAIR_SELECTION_UNITS = 1200


def build_chapter_repair_targets(
    content: str,
    findings: Iterable[Any],
    *,
    chapter_id: str,
    chapter: str,
    artifact_signature: str,
    chapter_version: int,
) -> list[dict[str, Any]]:
    paragraphs = _body_paragraphs(content, chapter)
    targets: list[dict[str, Any]] = []
    finding_id_counts: dict[str, int] = {}
    for finding in findings:
        dimension = str(_value(finding, "dimension") or "")
        evidence = str(_value(finding, "evidence") or "")
        span = _repair_span(content, paragraphs, dimension, evidence)
        selected_text = content[span[0] : span[1]] if span else ""
        base_finding_id = str(
            _value(finding, "id") or f"chapter-quality-{dimension or 'finding'}"
        )
        finding_id_counts[base_finding_id] = finding_id_counts.get(base_finding_id, 0) + 1
        finding_id = (
            base_finding_id
            if finding_id_counts[base_finding_id] == 1
            else f"{base_finding_id}-{finding_id_counts[base_finding_id]}"
        )
        targets.append(
            {
                "finding_id": finding_id,
                "chapter_id": chapter_id,
                "chapter": chapter,
                "artifact_signature": artifact_signature,
                "chapter_version": chapter_version,
                "dimension": dimension,
                "message": str(_value(finding, "message") or ""),
                "instruction": quality_revision_instruction(finding),
                "operation": _operation(dimension),
                "start": _utf16_offset(content, span[0]) if span else 0,
                "end": _utf16_offset(content, span[1]) if span else 0,
                "selected_text": selected_text,
                "locatable": span is not None,
            }
        )
    return targets


def _repair_span(
    content: str,
    paragraphs: list[tuple[int, int]],
    dimension: str,
    evidence: str,
) -> tuple[int, int] | None:
    if not content.strip():
        return None
    if dimension in {"chapter_handoff", "structure"}:
        return _limited_span(content, paragraphs[0]) if paragraphs else None
    if dimension == "foreshadowing":
        return _limited_span(content, paragraphs[-1]) if paragraphs else None
    evidence_span = _evidence_span(content, evidence)
    if dimension == "worldbuilding_conflict":
        return _limited_span(content, evidence_span) if evidence_span else None
    if dimension == "template_taste":
        candidate = evidence_span or _repeated_paragraph(content, paragraphs) or _longest(paragraphs)
        return _limited_span(content, candidate) if candidate else None
    return _limited_span(content, evidence_span) if evidence_span else None


def _body_paragraphs(content: str, chapter: str) -> list[tuple[int, int]]:
    paragraphs = [_trim_span(content, match.span()) for match in re.finditer(r"\S.*?(?=(?:\r?\n){2,}|\Z)", content, re.S)]
    paragraphs = [span for span in paragraphs if span[1] > span[0]]
    if len(paragraphs) > 1 and _is_heading(content[paragraphs[0][0] : paragraphs[0][1]], chapter):
        return paragraphs[1:]
    return paragraphs


def _is_heading(paragraph: str, chapter: str) -> bool:
    compact = " ".join(paragraph.split())
    if not compact or len(compact) > 80:
        return False
    return compact == chapter.strip() or bool(re.fullmatch(r"第\s*[一二三四五六七八九十百零〇\d]+\s*章(?:\s+.*)?", compact))


def _evidence_span(content: str, evidence: str) -> tuple[int, int] | None:
    evidence = evidence.strip()
    if len(evidence) < 4:
        return None
    start = content.find(evidence)
    return (start, start + len(evidence)) if start >= 0 else None


def _repeated_paragraph(content: str, paragraphs: list[tuple[int, int]]) -> tuple[int, int] | None:
    seen: dict[str, tuple[int, int]] = {}
    for span in paragraphs:
        normalized = " ".join(content[span[0] : span[1]].split())
        if len(normalized) < 16:
            continue
        if normalized in seen:
            return span
        seen[normalized] = span
    return None


def _longest(paragraphs: list[tuple[int, int]]) -> tuple[int, int] | None:
    return max(paragraphs, key=lambda span: span[1] - span[0], default=None)


def _limited_span(content: str, span: tuple[int, int]) -> tuple[int, int]:
    start, end = _trim_span(content, span)
    units = 0
    limited_end = start
    for index, char in enumerate(content[start:end], start=start):
        char_units = 2 if ord(char) > 0xFFFF else 1
        if units + char_units > MAX_REPAIR_SELECTION_UNITS:
            break
        units += char_units
        limited_end = index + 1
    return start, limited_end


def _trim_span(content: str, span: tuple[int, int]) -> tuple[int, int]:
    start, end = span
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return start, end


def _utf16_offset(content: str, index: int) -> int:
    return len(content[:index].encode("utf-16-le")) // 2


def _operation(dimension: str) -> str:
    return {
        "chapter_handoff": "expand",
        "foreshadowing": "expand",
        "structure": "expand",
        "template_taste": "compress",
        "worldbuilding_conflict": "rewrite",
    }.get(dimension, "rewrite")


def _value(finding: Any, key: str) -> Any:
    if isinstance(finding, dict):
        return finding.get(key)
    return getattr(finding, key, None)
