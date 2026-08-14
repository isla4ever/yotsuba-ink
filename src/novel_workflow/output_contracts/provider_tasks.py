from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class EvidenceClaimProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["fact", "character", "relationship", "foreshadow", "spine"]
    claim: str = Field(min_length=1, max_length=2000)
    span_ids: list[str] = Field(min_length=1, max_length=3)


class ChapterEvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[EvidenceClaimProposal] = Field(min_length=1, max_length=8)


__all__ = [
    "ChapterEvidenceResult",
    "ChapterReviewResult",
    "EvidenceClaimProposal",
    "ReviewFinding",
]
