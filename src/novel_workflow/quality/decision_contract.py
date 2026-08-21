from __future__ import annotations

from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QualitySubjectRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1, max_length=240)
    label: str = Field(min_length=1, max_length=240)


class ContractBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    claim: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    subjects: list[QualitySubjectRef] = Field(default_factory=list, max_length=12)
    property_key: str = Field(min_length=1, max_length=240)
    time_scope: str = Field(min_length=1, max_length=500)
    revision_direction: str = Field(min_length=1, max_length=2000)
    resolution: Literal["regenerate", "manual"] = "regenerate"


class ReviewWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    claim: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    subjects: list[QualitySubjectRef] = Field(default_factory=list, max_length=12)
    reviewer_role: str = Field(min_length=1, max_length=120)
    source_severity: Literal["warning", "blocking"]
    confidence_note: str = Field(min_length=1, max_length=500)


class RegenerationRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["required", "suggested"]
    direction: str = Field(min_length=1, max_length=2000)
    finding_codes: list[str] = Field(min_length=1, max_length=8)


class QualityDecision(BaseModel):
    """One typed author-facing projection; reviewer self-ratings never own gates."""

    model_config = ConfigDict(extra="forbid")

    structure_contract: Literal["passed", "blocked"]
    contract_blockers: list[ContractBlocker] = Field(default_factory=list, max_length=8)
    review_warnings: list[ReviewWarning] = Field(default_factory=list, max_length=24)
    evidence_status: Literal["pending", "succeeded", "needs_action"] = "pending"
    evidence_degraded: bool = False
    regeneration_recommendation: RegenerationRecommendation | None = None
    regeneration_used: Literal[0, 1] = 0
    regeneration_limit: Literal[1] = 1
    accepted: bool = False

    @model_validator(mode="after")
    def validate_semantics(self) -> "QualityDecision":
        blocked = bool(self.contract_blockers)
        if (self.structure_contract == "blocked") != blocked:
            raise ValueError("Structure contract status must match deterministic blockers")
        if self.evidence_degraded != (self.evidence_status == "needs_action"):
            raise ValueError("Evidence degradation must match needs_action status")
        if self.accepted and blocked:
            raise ValueError("A deterministically blocked chapter cannot be accepted")
        return self

    def allowed_actions(self) -> list[str]:
        if self.evidence_degraded:
            return ["retry_evidence", "cancel"]
        if any(item.resolution == "manual" for item in self.contract_blockers):
            return ["cancel"]
        actions: list[str] = []
        if not self.contract_blockers:
            actions.append("accept")
        if self.regeneration_used < self.regeneration_limit:
            actions.append("regenerate")
        actions.append("cancel")
        return actions


def contract_blocker(
    finding: dict[str, Any],
    *,
    subject_labels: dict[str, str],
) -> ContractBlocker:
    code = _text(finding.get("code"), "contract_conflict")
    claim = _text(finding.get("claim"), "正文违反确定性合同")
    evidence = _text(finding.get("evidence"), "未提供可定位证据")
    return ContractBlocker(
        code=code,
        claim=claim,
        evidence=evidence,
        subjects=_subjects(finding.get("subject_ids"), subject_labels),
        property_key=(
            "world_rule.call_time"
            if code == "time_rule_conflict"
            else "review.required_roles"
            if code == "required_review_unavailable"
            else f"chapter_contract.{code}"
        ),
        time_scope=(
            "当前章节的必需审稿阶段"
            if code == "required_review_unavailable"
            else "当前章节的同一叙事时段"
        ),
        revision_direction=quality_revision_direction([finding]),
        resolution=(
            "manual" if code == "required_review_unavailable" else "regenerate"
        ),
    )


def review_warning(
    finding: dict[str, Any],
    *,
    reviewer_role: str,
    subject_labels: dict[str, str],
) -> ReviewWarning:
    severity = str(finding.get("severity") or "warning")
    return ReviewWarning(
        code=_text(finding.get("code"), "review_warning"),
        claim=_text(finding.get("claim"), "审稿模型提出一项建议"),
        evidence=_text(finding.get("evidence"), "未提供可定位证据"),
        subjects=_subjects(finding.get("subject_ids"), subject_labels),
        reviewer_role=reviewer_role or "reviewer",
        source_severity="blocking" if severity == "blocking" else "warning",
        confidence_note="模型审稿意见，仅供作者判断；不参与系统阻断。",
    )


def build_quality_decision(
    *,
    contract_blockers: Iterable[ContractBlocker] = (),
    review_warnings: Iterable[ReviewWarning] = (),
    regeneration_used: int = 0,
    accepted: bool = False,
    evidence_status: Literal["pending", "succeeded", "needs_action"] = "pending",
) -> QualityDecision:
    blockers = list(contract_blockers)
    warnings = list(review_warnings)
    if regeneration_used not in {0, 1}:
        raise ValueError("Chapter regeneration usage must be 0 or 1")
    recommendation = _recommendation(blockers, warnings)
    return QualityDecision(
        structure_contract="blocked" if blockers else "passed",
        contract_blockers=blockers,
        review_warnings=warnings,
        evidence_status=evidence_status,
        evidence_degraded=evidence_status == "needs_action",
        regeneration_recommendation=recommendation,
        regeneration_used=regeneration_used,
        accepted=accepted,
    )


def quality_revision_direction(findings: Iterable[dict[str, Any]]) -> str:
    items: list[str] = []
    for index, finding in enumerate(findings, start=1):
        if index > 3:
            break
        claim = _text(finding.get("claim") or finding.get("code"), "审校问题")
        evidence = _text(finding.get("evidence"))[:80]
        items.append(f"{index}. {claim}" + (f"；证据：{evidence}" if evidence else ""))
    if not items:
        return ""
    return (
        "只修复以下审校问题，不改变冻结章名、细纲场景顺序、主体职责或未点名情节："
        + " ".join(items)
        + "。修改后核对本章结尾与下一章 handoff。"
    )


def _recommendation(
    blockers: list[ContractBlocker],
    warnings: list[ReviewWarning],
) -> RegenerationRecommendation | None:
    findings: list[ContractBlocker | ReviewWarning] = blockers or warnings
    if not findings:
        return None
    if blockers:
        direction = blockers[0].revision_direction
    else:
        direction = quality_revision_direction(
            [item.model_dump(mode="json") for item in warnings]
        )
    return RegenerationRecommendation(
        kind="required" if blockers else "suggested",
        direction=direction,
        finding_codes=list(dict.fromkeys(item.code for item in findings))[:8],
    )


def _subjects(value: Any, labels: dict[str, str]) -> list[QualitySubjectRef]:
    if not isinstance(value, list):
        return []
    subject_ids = list(dict.fromkeys(str(item) for item in value if str(item)))[:12]
    return [
        QualitySubjectRef(subject_id=subject_id, label=labels.get(subject_id, subject_id))
        for subject_id in subject_ids
    ]


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


__all__ = [
    "ContractBlocker",
    "QualityDecision",
    "QualitySubjectRef",
    "RegenerationRecommendation",
    "ReviewWarning",
    "build_quality_decision",
    "contract_blocker",
    "quality_revision_direction",
    "review_warning",
]
