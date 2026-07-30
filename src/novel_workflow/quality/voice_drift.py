"""Deterministic Voice Spec drift detection (Phase 10.4a, zero provider cost).

Pure functions only: they compare chapter text against the Story Brief voice
spec and emit warning-level findings that flow into the existing revision
loop. Drift never rolls back committed text — findings carry targeted rewrite
semantics via `quality/repair_instructions.py`.
"""
from __future__ import annotations

import re
from typing import Any

from novel_workflow.workflows.schemas import QualityFinding

DIALOGUE_MARKERS = ("「", "」", "“", "”")
DIALOGUE_RATIO_TOLERANCE = 0.25
MIN_LINES_FOR_RATIO = 4
LONG_SENTENCE_CHARS = 60
SHORT_SENTENCE_PREFERENCE_LIMIT = 40
RATIO_PATTERN = re.compile(r"(\d+)\s*[:：]\s*(\d+)")
SENTENCE_LIMIT_PATTERN = re.compile(r"句长[^0-9]{0,8}(\d+)\s*字")


def voice_spec_from_state(state: Any) -> dict[str, Any] | None:
    artifacts = getattr(state, "artifacts", None)
    brief = artifacts.get("info_recommend") if isinstance(artifacts, dict) else None
    spec = brief.get("voice_spec") if isinstance(brief, dict) else None
    if not isinstance(spec, dict):
        return None
    has_content = any(
        spec.get(key) for key in ("narration", "rhythm", "banned_words", "cliche_slots", "per_character")
    )
    return spec if has_content else None


def voice_metrics(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    dialogue_lines = [line for line in lines if any(marker in line for marker in DIALOGUE_MARKERS)]
    sentences = [part.strip() for part in re.split(r"[。！？!?\n]", text) if part.strip()]
    average = round(sum(len(item) for item in sentences) / len(sentences), 1) if sentences else 0.0
    return {
        "total_lines": len(lines),
        "dialogue_lines": len(dialogue_lines),
        "dialogue_ratio": round(len(dialogue_lines) / len(lines), 3) if lines else 0.0,
        "sentence_count": len(sentences),
        "average_sentence_chars": average,
        "long_sentence_count": sum(1 for item in sentences if len(item) > LONG_SENTENCE_CHARS),
    }


def parse_declared_dialogue_ratio(rhythm: str) -> float | None:
    """rhythm is free text; only compare when an explicit `N:M` ratio is present."""
    match = RATIO_PATTERN.search(rhythm or "")
    if not match:
        return None
    dialogue, narration = int(match.group(1)), int(match.group(2))
    total = dialogue + narration
    return dialogue / total if total > 0 else None


def voice_drift_findings(node_id: str, text: str, voice_spec: dict[str, Any] | None) -> list[QualityFinding]:
    if not isinstance(voice_spec, dict) or not text.strip():
        return []
    findings: list[QualityFinding] = []
    findings.extend(_term_findings(node_id, text, voice_spec.get("banned_words"), dimension="voice_banned_word", label="禁用词"))
    findings.extend(_term_findings(node_id, text, voice_spec.get("cliche_slots"), dimension="voice_cliche", label="陈词槽"))
    metrics = voice_metrics(text)
    rhythm = str(voice_spec.get("rhythm") or "")
    findings.extend(_dialogue_ratio_findings(node_id, metrics, rhythm))
    findings.extend(_sentence_length_findings(node_id, metrics, rhythm))
    return findings


def _term_findings(node_id: str, text: str, terms: Any, *, dimension: str, label: str) -> list[QualityFinding]:
    if not isinstance(terms, list):
        return []
    hits = [(term, text.count(term)) for term in (str(item).strip() for item in terms) if term and term in text]
    if not hits:
        return []
    evidence = "、".join(f"{term}×{count}" for term, count in hits)
    return [
        _finding(
            node_id,
            dimension,
            f"正文命中 Voice Spec {label} {len(hits)} 项：{evidence}。",
            evidence,
        )
    ]


def _dialogue_ratio_findings(node_id: str, metrics: dict[str, Any], rhythm: str) -> list[QualityFinding]:
    target = parse_declared_dialogue_ratio(rhythm)
    if target is None or metrics["total_lines"] < MIN_LINES_FOR_RATIO:
        return []
    actual = float(metrics["dialogue_ratio"])
    if abs(actual - target) <= DIALOGUE_RATIO_TOLERANCE:
        return []
    return [
        _finding(
            node_id,
            "voice_dialogue_ratio",
            f"对话叙述比偏离 Voice Spec：声明约 {target:.0%} 对话行，正文实际 {actual:.0%}。",
            f"声明比例 {rhythm[:80]}｜实际对话行 {metrics['dialogue_lines']}/{metrics['total_lines']}",
        )
    ]


def _sentence_length_findings(node_id: str, metrics: dict[str, Any], rhythm: str) -> list[QualityFinding]:
    """Sentence length is report-only unless rhythm declares an explicit preference."""
    if not metrics["sentence_count"]:
        return []
    average = float(metrics["average_sentence_chars"])
    limit_match = SENTENCE_LIMIT_PATTERN.search(rhythm or "")
    limit: float | None = None
    if limit_match:
        limit = float(limit_match.group(1))
    elif "短句" in (rhythm or ""):
        limit = float(SHORT_SENTENCE_PREFERENCE_LIMIT)
    if limit is None or average <= limit:
        return []
    return [
        _finding(
            node_id,
            "voice_sentence_length",
            f"平均句长 {average} 字，超过 Voice Spec 声明的句长偏好（约 {limit:.0f} 字），超长句 {metrics['long_sentence_count']} 句。",
            f"平均句长 {average} 字｜超长句 {metrics['long_sentence_count']} 句",
        )
    ]


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
