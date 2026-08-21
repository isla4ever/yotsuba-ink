from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_turn_refs(value: list[str], *, label: str) -> list[str]:
    if len(value) != len(set(value)):
        raise ValueError(f"{label} turn refs must be unique")
    if any(re.fullmatch(r"turn-[1-9][0-9]*", item) is None for item in value):
        raise ValueError(f"{label} refs must use turn-N ids")
    return sorted(value, key=lambda item: int(item.removeprefix("turn-")))


class SpineSemanticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "consequence_ownership",
        "motivation_bridge",
        "agency_ownership",
        "world_rule_feasibility",
        "causal_handoff",
        "redundant_progress",
        "premature_resolution",
        "ending_derivation",
    ]
    turn_refs: list[str] = Field(min_length=1, max_length=6)
    claim: str = Field(min_length=1, max_length=800)
    required_fix: str = Field(min_length=1, max_length=800)

    @field_validator("turn_refs")
    @classmethod
    def require_ordered_turn_refs(cls, value: list[str]) -> list[str]:
        return _normalize_turn_refs(value, label="Spine semantic finding")


class SpineSemanticReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "revise"]
    findings: list[SpineSemanticFinding] = Field(max_length=5)

    @model_validator(mode="after")
    def verdict_matches_findings(self) -> "SpineSemanticReviewResult":
        if self.verdict == "pass" and self.findings:
            raise ValueError("A passing Spine semantic review cannot contain findings")
        if self.verdict == "revise" and not self.findings:
            raise ValueError("A Spine revision verdict requires at least one finding")
        return self


class RoleDemandSemanticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "unsupported_demand",
        "mergeable_demand",
        "missing_turn_agency",
        "arc_without_spine_basis",
        "capacity_padding",
        "historical_subject_misuse",
    ]
    demand_refs: list[str] = Field(max_length=6)
    turn_refs: list[str] = Field(min_length=1, max_length=8)
    claim: str = Field(min_length=1, max_length=800)
    required_fix: str = Field(min_length=1, max_length=800)

    @field_validator("demand_refs")
    @classmethod
    def require_demand_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Role Demand semantic finding refs must be unique")
        if any(re.fullmatch(r"demand-[A-Za-z0-9][A-Za-z0-9._-]{0,79}", item) is None for item in value):
            raise ValueError("Role Demand semantic finding refs must use demand keys")
        return value

    @field_validator("turn_refs")
    @classmethod
    def require_ordered_turn_refs(cls, value: list[str]) -> list[str]:
        return _normalize_turn_refs(value, label="Role Demand semantic finding")


class RoleDemandSemanticReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "revise"]
    findings: list[RoleDemandSemanticFinding] = Field(max_length=8)

    @model_validator(mode="after")
    def verdict_matches_findings(self) -> "RoleDemandSemanticReviewResult":
        if self.verdict == "pass" and self.findings:
            raise ValueError("A passing Role Demand review cannot contain findings")
        if self.verdict == "revise" and not self.findings:
            raise ValueError("A Role Demand revision verdict requires at least one finding")
        return self


class CastDossierSemanticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "demand_misalignment",
        "background_contradiction",
        "stakes_ownership",
        "motivation_bridge",
        "performance_ambiguity",
        "historical_subject_misuse",
    ]
    subject_refs: list[str] = Field(min_length=1, max_length=6)
    demand_refs: list[str] = Field(min_length=1, max_length=6)
    turn_refs: list[str] = Field(max_length=8)
    claim: str = Field(min_length=1, max_length=800)
    required_fix: str = Field(min_length=1, max_length=800)

    @field_validator("subject_refs")
    @classmethod
    def require_subject_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Cast semantic finding subject refs must be unique")
        if any(re.fullmatch(r"subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}", item) is None for item in value):
            raise ValueError("Cast semantic finding refs must use subject ids")
        return value

    @field_validator("demand_refs")
    @classmethod
    def require_demand_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Cast semantic finding demand refs must be unique")
        if any(re.fullmatch(r"demand-[A-Za-z0-9][A-Za-z0-9._-]{0,79}", item) is None for item in value):
            raise ValueError("Cast semantic finding demand refs must use demand keys")
        return value

    @field_validator("turn_refs")
    @classmethod
    def require_ordered_turn_refs(cls, value: list[str]) -> list[str]:
        return _normalize_turn_refs(value, label="Cast semantic finding")


class CastDossierSemanticReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "revise"]
    findings: list[CastDossierSemanticFinding] = Field(max_length=8)

    @model_validator(mode="after")
    def verdict_matches_findings(self) -> "CastDossierSemanticReviewResult":
        if self.verdict == "pass" and self.findings:
            raise ValueError("A passing Cast dossier review cannot contain findings")
        if self.verdict == "revise" and not self.findings:
            raise ValueError("A Cast dossier revision verdict requires at least one finding")
        return self


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    severity: Literal["warning", "blocking"]
    claim: str = Field(min_length=1, max_length=2000)
    evidence: str = Field(min_length=1, max_length=2000)
    subject_ids: list[str] = Field(max_length=12)


class ChapterReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    available: bool = True
    findings: list[ReviewFinding] = Field(default_factory=list)


class EvidenceStoryScopeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["story"]
    epistemic_status: Literal[
        "fact", "rumour", "belief", "reveal", "refutation"
    ]


class EvidenceStateAssertionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["assertion"]
    subject_id: str = Field(min_length=1, max_length=160)
    property_key: str = Field(min_length=1, max_length=240)
    value: str = Field(min_length=1, max_length=2000)
    epistemic_status: Literal[
        "fact", "rumour", "belief", "reveal", "refutation"
    ]


class EvidenceStateTransitionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["transition"]
    source_fact_id: str = Field(min_length=1, max_length=240)
    action: Literal["supersedes", "resolves"]
    value: str = Field(min_length=1, max_length=2000)
    epistemic_status: Literal[
        "fact", "rumour", "belief", "reveal", "refutation"
    ]


EvidenceStateProposal = (
    EvidenceStoryScopeProposal
    | EvidenceStateAssertionProposal
    | EvidenceStateTransitionProposal
)


class EvidenceClaimProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["fact", "character", "relationship", "foreshadow", "spine"]
    claim: str = Field(min_length=1, max_length=2000)
    span_ids: list[str] = Field(min_length=1, max_length=3)
    state: EvidenceStateProposal


class ChapterEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[EvidenceClaimProposal] = Field(min_length=1, max_length=8)


__all__ = [
    "CastDossierSemanticFinding",
    "CastDossierSemanticReviewResult",
    "ChapterEvidenceResult",
    "ChapterReviewResult",
    "EvidenceClaimProposal",
    "EvidenceStateAssertionProposal",
    "EvidenceStateTransitionProposal",
    "EvidenceStoryScopeProposal",
    "ReviewFinding",
    "RoleDemandSemanticFinding",
    "RoleDemandSemanticReviewResult",
    "SpineSemanticFinding",
    "SpineSemanticReviewResult",
]
