from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.artifacts_vnext import (
    DetailArtifact,
    StoryBriefArtifact,
    StorySpineArtifact,
)


WorldRuleCategory = Literal[
    "temporal",
    "professional",
    "causal",
    "identity",
    "physical",
    "other",
]
RuleRecurrence = Literal["none", "conditional", "periodic", "loop"]
PromiseKind = Literal[
    "central_mystery",
    "reader_promise",
    "world_rule",
    "relationship",
]
PromiseStatus = Literal["open", "resolved", "deferred_allowed", "missing"]


class WorldRuleProjection(BaseModel):
    """A rebuildable, typed view of one frozen Brief world rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(pattern=r"^world-rule-[1-9][0-9]*$")
    source_text: str = Field(min_length=1, max_length=2000)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    categories: list[WorldRuleCategory] = Field(min_length=1, max_length=6)
    recurrence: RuleRecurrence = "none"
    future_offset_hours: int | None = Field(default=None, ge=1, le=10_000)
    fixed_time: bool = False
    authorizes_repetition: bool = False


class WorldRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[WorldRuleProjection] = Field(min_length=1, max_length=24)


class PromiseLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    promise_id: str = Field(min_length=1, max_length=120)
    kind: PromiseKind
    question_or_promise: str = Field(min_length=1, max_length=2000)
    setup_refs: list[str] = Field(default_factory=list, max_length=24)
    misdirection_refs: list[str] = Field(default_factory=list, max_length=24)
    reveal_ref: str = Field(default="", max_length=120)
    consequence_ref: str = Field(default="", max_length=120)
    status: PromiseStatus
    missing_components: list[str] = Field(default_factory=list, max_length=12)


class MysteryPromiseLedger(BaseModel):
    """A read model derived from frozen Brief, Spine, and optional Detail."""

    model_config = ConfigDict(extra="forbid")

    entries: list[PromiseLedgerEntry] = Field(min_length=1, max_length=48)


_TEMPORAL_TERMS = (
    "时间",
    "小时",
    "分钟",
    "每天",
    "每日",
    "每晚",
    "次日",
    "未来",
    "过去",
    "提前",
)
_PROFESSIONAL_TERMS = (
    "调度",
    "急救",
    "医生",
    "警方",
    "执业",
    "职业",
    "权限",
    "程序",
    "值班",
    "审计",
    "证据",
)
_CAUSAL_TERMS = ("导致", "改变", "代价", "后果", "因此", "只有", "必须")
_IDENTITY_TERMS = ("身份", "化名", "伪装", "假死", "冒名", "记忆")
_PHYSICAL_TERMS = ("地点", "位置", "死亡", "存活", "身体", "物理", "同时")
_LOOP_TERMS = ("循环", "重置", "回放", "重演", "再次经历")
_PERIODIC_TERMS = ("每天", "每日", "每晚", "每周", "每次", "固定时间", "固定时段")
_CONDITIONAL_TERMS = ("只要", "一旦", "每当", "当且仅当")
_MYSTERY_TERMS = (
    "悬疑",
    "谜",
    "真相",
    "秘密",
    "旧案",
    "失踪",
    "死亡",
    "身份",
    "谁",
    "为何",
    "为什么",
    "追查",
)
_CHINESE_HOURS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十二": 12,
    "二十四": 24,
    "四十八": 48,
}


def project_world_rules(brief: StoryBriefArtifact) -> WorldRuleSet:
    """Project natural-language Brief rules once into typed deterministic facts."""

    rules = [
        _project_world_rule(index, source_text)
        for index, source_text in enumerate(brief.world_rules, start=1)
    ]
    return WorldRuleSet(rules=rules)


def build_mystery_promise_ledger(
    brief: StoryBriefArtifact,
    spine: StorySpineArtifact,
    detail: DetailArtifact | None = None,
) -> MysteryPromiseLedger:
    """Map book promises to code-owned structural refs without adding an Artifact."""

    inciting = _milestone_ref(spine, "inciting")
    midpoint = _milestone_ref(spine, "midpoint_reversal")
    climax = _milestone_ref(spine, "climax")
    aftermath = _milestone_ref(spine, "aftermath")
    covered_turns = {
        turn_ref
        for chapter in detail.chapters
        for turn_ref in chapter.turn_refs
    } if detail is not None else set()

    reader_missing = _missing_structural_refs(
        setup_ref=inciting,
        reveal_ref=climax,
        consequence_ref=aftermath,
        detail=detail,
        covered_turns=covered_turns,
    )
    entries = [
        PromiseLedgerEntry(
            promise_id="reader-promise",
            kind="reader_promise",
            question_or_promise=brief.promise,
            setup_refs=[inciting] if inciting else [],
            misdirection_refs=[midpoint] if midpoint else [],
            reveal_ref=climax,
            consequence_ref=aftermath,
            status=_promise_status(reader_missing, detail),
            missing_components=reader_missing,
        )
    ]

    if _is_mystery(brief):
        mystery_missing = _missing_structural_refs(
            setup_ref=inciting,
            reveal_ref=climax,
            consequence_ref=aftermath,
            detail=detail,
            covered_turns=covered_turns,
        )
        entries.append(
            PromiseLedgerEntry(
                promise_id="central-mystery",
                kind="central_mystery",
                question_or_promise=brief.ending_promise,
                # Evidence progression is structural, not a dedicated Spine
                # progress type. External action or relationship change may
                # carry a reveal as long as the frozen milestone refs exist.
                setup_refs=[inciting] if inciting else [],
                misdirection_refs=[midpoint] if midpoint else [],
                reveal_ref=climax,
                consequence_ref=aftermath,
                status=_promise_status(mystery_missing, detail),
                missing_components=mystery_missing,
            )
        )

    entries.extend(
        PromiseLedgerEntry(
            promise_id=f"deferred-question-{index}",
            kind="reader_promise",
            question_or_promise=question,
            setup_refs=[],
            misdirection_refs=[],
            reveal_ref="",
            consequence_ref="",
            status="deferred_allowed",
        )
        for index, question in enumerate(spine.open_questions, start=1)
    )
    return MysteryPromiseLedger(entries=entries)


def _project_world_rule(index: int, source_text: str) -> WorldRuleProjection:
    categories: list[WorldRuleCategory] = []
    for category, terms in (
        ("temporal", _TEMPORAL_TERMS),
        ("professional", _PROFESSIONAL_TERMS),
        ("causal", _CAUSAL_TERMS),
        ("identity", _IDENTITY_TERMS),
        ("physical", _PHYSICAL_TERMS),
    ):
        if any(term in source_text for term in terms):
            categories.append(category)
    if not categories:
        categories.append("other")

    recurrence: RuleRecurrence = "none"
    if any(term in source_text for term in _LOOP_TERMS):
        recurrence = "loop"
    elif any(term in source_text for term in _PERIODIC_TERMS):
        recurrence = "periodic"
    elif any(term in source_text for term in _CONDITIONAL_TERMS):
        recurrence = "conditional"
    return WorldRuleProjection(
        rule_id=f"world-rule-{index}",
        source_text=source_text,
        source_hash=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        categories=categories,
        recurrence=recurrence,
        future_offset_hours=_future_offset_hours(source_text),
        fixed_time=(
            "固定时间" in source_text
            or "固定时段" in source_text
            or bool(re.search(r"每(?:天|日|晚).{0,12}[0-9一二三四五六七八九十]{1,3}时", source_text))
        ),
        authorizes_repetition=recurrence in {"periodic", "loop"},
    )


def _future_offset_hours(source_text: str) -> int | None:
    match = re.search(
        r"([0-9]{1,4}|二十四|四十八|十二|十|[一二三四五六七八九])\s*小时\s*(?:后|之后|未来)",
        source_text,
    )
    if match is None:
        return None
    raw = match.group(1)
    return int(raw) if raw.isdigit() else _CHINESE_HOURS.get(raw)


def _is_mystery(brief: StoryBriefArtifact) -> bool:
    text = " ".join(
        (brief.premise, brief.promise, brief.theme, brief.ending_promise)
    )
    return any(term in text for term in _MYSTERY_TERMS)


def _milestone_ref(spine: StorySpineArtifact, milestone: str) -> str:
    return next(
        (turn.id for turn in spine.turns if milestone in turn.milestones),
        "",
    )


def _missing_structural_refs(
    *,
    setup_ref: str,
    reveal_ref: str,
    consequence_ref: str,
    detail: DetailArtifact | None,
    covered_turns: set[str],
) -> list[str]:
    missing: list[str] = []
    if not setup_ref:
        missing.append("setup")
    if not reveal_ref:
        missing.append("reveal")
    if not consequence_ref:
        missing.append("consequence")
    if detail is not None:
        if reveal_ref and reveal_ref not in covered_turns:
            missing.append("detail_reveal")
        if consequence_ref and consequence_ref not in covered_turns:
            missing.append("detail_consequence")
    return missing


def _promise_status(
    missing_components: list[str],
    detail: DetailArtifact | None,
) -> PromiseStatus:
    if missing_components:
        return "missing"
    return "resolved" if detail is not None else "open"


def _turn_number(turn_ref: str) -> int:
    return int(turn_ref.removeprefix("turn-"))


def _ordered_unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


__all__ = [
    "MysteryPromiseLedger",
    "PromiseLedgerEntry",
    "WorldRuleProjection",
    "WorldRuleSet",
    "build_mystery_promise_ledger",
    "project_world_rules",
]
