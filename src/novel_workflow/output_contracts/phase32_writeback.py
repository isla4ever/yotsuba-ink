"""Phase 32 source-bound Evidence and Canon writeback contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.route_specs import CreationRouteId


EpistemicStatus = Literal["fact", "rumour", "belief", "reveal", "refutation"]
EvidenceKind = Literal["fact", "character", "relationship", "foreshadow", "structure"]


class Phase32StoryFactProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["story"]
    epistemic_status: EpistemicStatus = "fact"


class Phase32StateAssertionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    type: Literal["assertion"]
    subject_ref: str = Field(min_length=1, max_length=240)
    property_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,239}$")
    value: str = Field(min_length=1, max_length=2_000)
    epistemic_status: EpistemicStatus = "fact"


class Phase32StateTransitionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    type: Literal["transition"]
    source_fact_ref: str = Field(min_length=1, max_length=500)
    action: Literal["supersedes", "resolves"]
    value: str = Field(min_length=1, max_length=2_000)
    epistemic_status: EpistemicStatus = "fact"


Phase32FactStateProposal = Annotated[
    Phase32StoryFactProposal
    | Phase32StateAssertionProposal
    | Phase32StateTransitionProposal,
    Field(discriminator="type"),
]


class Phase32EvidenceClaimProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    kind: EvidenceKind
    claim: str = Field(min_length=1, max_length=2_000)
    span_ids: tuple[str, ...] = Field(min_length=1, max_length=3)
    state: Phase32FactStateProposal

    @model_validator(mode="after")
    def validate_unique_spans(self) -> "Phase32EvidenceClaimProposal":
        if len(self.span_ids) != len(set(self.span_ids)):
            raise ValueError("Evidence claim span ids must be unique")
        return self


class Phase32EvidenceProposalBundle(BaseModel):
    """Provider-authored proposals; an empty bundle is valid and non-authoritative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claims: tuple[Phase32EvidenceClaimProposal, ...] = Field(max_length=8)


class Phase32EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=8_000)

    @model_validator(mode="after")
    def validate_range(self) -> "Phase32EvidenceSpan":
        if self.end <= self.start:
            raise ValueError("Evidence span end must follow start")
        return self


class Phase32EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    evidence_ref: str = Field(pattern=r"^p32-evidence-[a-f0-9]{64}$")
    run_id: str
    creation_route_id: CreationRouteId
    stage_id: Literal["script", "text"]
    unit_ref: str = Field(min_length=1, max_length=500)
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    source_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_text_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: EvidenceKind
    claim: str = Field(min_length=1, max_length=2_000)
    spans: tuple[Phase32EvidenceSpan, ...] = Field(min_length=1, max_length=3)
    subject_ref: str = Field(default="", max_length=240)
    property_key: str = Field(default="", max_length=240)
    value: str = Field(default="", max_length=2_000)
    epistemic_status: EpistemicStatus = "fact"
    lifecycle: Literal["active", "supersedes", "resolves"] = "active"
    source_fact_refs: tuple[str, ...] = Field(default=(), max_length=16)
    effective_ordinal: int = Field(ge=1)
    created_at: str = Field(min_length=1, max_length=80)


class Phase32CanonFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    fact_ref: str = Field(pattern=r"^p32-fact-[a-f0-9]{64}$")
    claim: str = Field(min_length=1, max_length=2_000)
    evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=8)
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    stage_id: Literal["script", "text"]
    unit_ref: str = Field(min_length=1, max_length=500)
    subject_ref: str = Field(default="", max_length=240)
    property_key: str = Field(default="", max_length=240)
    value: str = Field(default="", max_length=2_000)
    epistemic_status: EpistemicStatus = "fact"
    lifecycle: Literal["active", "supersedes", "resolves"] = "active"
    source_fact_refs: tuple[str, ...] = Field(default=(), max_length=16)
    effective_ordinal: int = Field(ge=1)


class Phase32CanonTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_ref: str = Field(pattern=r"^p32-canon-[a-f0-9]{64}$")
    run_id: str
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    facts: tuple[Phase32CanonFact, ...] = Field(default=(), max_length=8)
    committed_at: str = Field(min_length=1, max_length=80)


class Phase32WritebackReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    receipt_ref: str = Field(pattern=r"^p32-writeback-[a-f0-9]{64}$")
    run_id: str
    creation_route_id: CreationRouteId
    stage_id: Literal["script", "text"]
    unit_ref: str = Field(min_length=1, max_length=500)
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    source_payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_text_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal[
        "pending_evidence",
        "queued",
        "canon_committed",
        "committed",
        "needs_action",
        "cancelled",
    ]
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=8)
    fact_refs: tuple[str, ...] = Field(default=(), max_length=8)
    transaction_ref: str = Field(default="", max_length=500)
    provider_operation_refs: tuple[str, ...] = Field(default=(), max_length=64)
    recovery_count: int = Field(default=0, ge=0)
    error_code: str = Field(default="", max_length=160)
    error_message: str = Field(default="", max_length=2_000)
    created_at: str = Field(min_length=1, max_length=80)
    updated_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_status_payload(self) -> "Phase32WritebackReceipt":
        if self.status == "committed" and not self.transaction_ref:
            raise ValueError("Committed writeback requires a Canon transaction")
        if self.status == "needs_action" and not self.error_code:
            raise ValueError("Writeback recovery requires a visible error code")
        if self.status not in {"needs_action", "cancelled"} and self.error_code:
            raise ValueError("Only interrupted writeback may retain a visible error")
        return self


__all__ = [
    "Phase32CanonFact",
    "Phase32CanonTransaction",
    "Phase32EvidenceClaimProposal",
    "Phase32EvidenceProposalBundle",
    "Phase32EvidenceRecord",
    "Phase32EvidenceSpan",
    "Phase32StateAssertionProposal",
    "Phase32StateTransitionProposal",
    "Phase32StoryFactProposal",
    "Phase32WritebackReceipt",
]
