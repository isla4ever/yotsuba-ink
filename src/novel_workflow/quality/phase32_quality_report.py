"""Phase 32 text quality evidence and human cold-read contracts.

Quality reports are immutable sidecars.  They bind to the exact committed
text/script prefix that was reviewed; they never become core literary
Artifacts or graph control state.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.output_contracts.phase32_artifact_base import ScreenplayBlockKind
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


QualityEvidenceScope = Literal[
    "production",
    "release_smoke",
    "continuity_acceptance",
]
ProductionAcceptanceStatus = Literal["not_evaluated", "accepted", "rejected"]
ColdReadOutcome = Literal[
    "continue_reading",
    "revision_recommended",
    "stop_recommended",
]
LiteraryImpact = Literal["low", "moderate", "high", "critical"]


class Phase32QualitySourceBinding(BaseModel):
    """One accepted unit and the exact immutable Artifact version reviewed."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    ordinal: int = Field(ge=1, le=4_000)
    unit_ref: str = Field(min_length=1, max_length=240)
    artifact_ref: str = Field(
        pattern=r"^p32-(?:script|text)-committed-[a-f0-9]{64}$"
    )
    artifact_kind: ArtifactKind
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class Phase32QualityPlanningSourceBinding(BaseModel):
    """The committed Rolling Detail root that freezes a continuity corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    stage_id: Literal["rolling_detail"] = "rolling_detail"
    artifact_kind: Literal["detail_plan_index"] = "detail_plan_index"
    artifact_ref: str = Field(
        pattern=r"^p32-rolling_detail-committed-[a-f0-9]{64}$"
    )
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class Phase32QualitySourceSnapshot(BaseModel):
    """Content-addressed accepted-prefix projection used by one review."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    stage_id: Literal["script", "text"]
    ordered_unit_refs: tuple[str, ...] = Field(min_length=1, max_length=4_000)
    committed_sources: tuple[Phase32QualitySourceBinding, ...] = Field(
        default=(), max_length=4_000
    )
    planning_source: Phase32QualityPlanningSourceBinding | None = None
    accepted_prefix_complete: bool
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_source_snapshot(self) -> Self:
        if len(self.ordered_unit_refs) != len(set(self.ordered_unit_refs)):
            raise ValueError("Quality source unit refs must be unique")
        source_units = tuple(item.unit_ref for item in self.committed_sources)
        expected_prefix = self.ordered_unit_refs[: len(source_units)]
        if source_units != expected_prefix:
            raise ValueError("Quality sources must be the frozen accepted unit prefix")
        if tuple(item.ordinal for item in self.committed_sources) != tuple(
            range(1, len(self.committed_sources) + 1)
        ):
            raise ValueError("Quality source ordinals must be contiguous")
        if len({item.artifact_ref for item in self.committed_sources}) != len(
            self.committed_sources
        ):
            raise ValueError("Quality source Artifact refs must be unique")
        kinds = {item.artifact_kind for item in self.committed_sources}
        allowed_kinds = (
            {"screenplay_draft"}
            if self.stage_id == "script"
            else {"short_prose_unit", "chapter"}
        )
        if not kinds.issubset(allowed_kinds) or len(kinds) > 1:
            raise ValueError("Quality source kinds must match one text route stage")
        if self.planning_source is not None and self.stage_id != "text":
            raise ValueError("Only prose quality evidence may bind a planning source")
        complete = len(source_units) == len(self.ordered_unit_refs)
        if self.accepted_prefix_complete != complete:
            raise ValueError("Quality source completion must match its accepted prefix")
        expected_digest = canonical_digest(
            self.model_dump(mode="json", exclude={"source_digest"})
        )
        if self.source_digest != expected_digest:
            raise ValueError("Quality source digest does not match its bindings")
        return self


class Phase32ProseEvidenceAnchor(BaseModel):
    """Exact code-point span inside a committed prose unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["prose_span"] = "prose_span"
    artifact_ref: str = Field(pattern=r"^p32-text-committed-[a-f0-9]{64}$")
    unit_ref: str = Field(min_length=1, max_length=240)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    exact_text: str = Field(min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("Prose evidence end offset must follow its start offset")
        if len(self.exact_text) != self.end_offset - self.start_offset:
            raise ValueError("Prose evidence text length must match its exact offsets")
        return self


class Phase32ScreenplayEvidenceAnchor(BaseModel):
    """Exact code-point span inside one committed screenplay block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["screenplay_block_span"] = "screenplay_block_span"
    artifact_ref: str = Field(pattern=r"^p32-script-committed-[a-f0-9]{64}$")
    unit_ref: str = Field(min_length=1, max_length=240)
    block_index: int = Field(ge=0, le=499)
    block_kind: ScreenplayBlockKind
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    exact_text: str = Field(min_length=1, max_length=4_000)

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError("Screenplay evidence end offset must follow its start offset")
        if len(self.exact_text) != self.end_offset - self.start_offset:
            raise ValueError("Screenplay evidence text length must match its exact offsets")
        return self


Phase32QualityEvidenceAnchor = Annotated[
    Phase32ProseEvidenceAnchor | Phase32ScreenplayEvidenceAnchor,
    Field(discriminator="kind"),
]


class Phase32DeterministicBlocker(BaseModel):
    """A code-owned failure.  Only this lane may block acceptance."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    lane: Literal["system"] = "system"
    effect: Literal["block"] = "block"
    code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    evidence: str = Field(min_length=1, max_length=2_000)
    required_action: str = Field(min_length=1, max_length=2_000)
    source_artifact_refs: tuple[str, ...] = Field(default=(), max_length=64)


class Phase32LiteraryWarning(BaseModel):
    """Human literary judgment.  Critical impact remains advisory."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    lane: Literal["advisory"] = "advisory"
    effect: Literal["warning"] = "warning"
    code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    impact: LiteraryImpact
    observation: str = Field(min_length=1, max_length=2_000)
    recommended_action: str = Field(min_length=1, max_length=2_000)
    anchors: tuple[Phase32QualityEvidenceAnchor, ...] = Field(
        min_length=1, max_length=24
    )


class Phase32ColdReadRecord(BaseModel):
    """One explicit human review result; automatic signals cannot create it."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    reviewer_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
    reviewer_role: str = Field(min_length=1, max_length=120)
    outcome: ColdReadOutcome
    summary: str = Field(min_length=1, max_length=4_000)
    reviewed_at: str = Field(min_length=1, max_length=80)


class Phase32TextQualityReport(BaseModel):
    """Immutable quality report for one exact Phase 32 text source snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    report_ref: str = Field(pattern=r"^p32-quality-report-[a-f0-9]{64}$")
    report_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    creation_route_id: CreationRouteId
    sequence: int = Field(ge=1)
    supersedes_report_ref: str | None = Field(
        default=None, pattern=r"^p32-quality-report-[a-f0-9]{64}$"
    )
    evidence_scope: QualityEvidenceScope
    production_acceptance_status: ProductionAcceptanceStatus = "not_evaluated"
    source_snapshot: Phase32QualitySourceSnapshot
    structure_contract: Literal["passed", "blocked"]
    deterministic_blockers: tuple[Phase32DeterministicBlocker, ...] = Field(
        default=(), max_length=128
    )
    literary_warnings: tuple[Phase32LiteraryWarning, ...] = Field(
        default=(), max_length=256
    )
    cold_read: Phase32ColdReadRecord
    recorded_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        expected_stage = (
            "script" if self.creation_route_id == "screenplay_sample" else "text"
        )
        if self.source_snapshot.stage_id != expected_stage:
            raise ValueError("Quality source stage does not match its creation route")
        planning_source = self.source_snapshot.planning_source
        if self.evidence_scope == "continuity_acceptance":
            if self.creation_route_id != "long_novel" or planning_source is None:
                raise ValueError(
                    "Continuity acceptance requires a long_novel Rolling Detail source"
                )
        elif planning_source is not None:
            raise ValueError(
                "Only continuity acceptance may bind a Rolling Detail source"
            )
        expected_kind = {
            "screenplay_sample": "screenplay_draft",
            "short_novel": "short_prose_unit",
            "long_novel": "chapter",
        }[self.creation_route_id]
        if any(
            item.artifact_kind != expected_kind
            for item in self.source_snapshot.committed_sources
        ):
            raise ValueError("Quality source kind does not match its creation route")
        if (self.structure_contract == "blocked") != bool(
            self.deterministic_blockers
        ):
            raise ValueError("Structure status must match deterministic blockers")
        if self.production_acceptance_status == "accepted" and self.deterministic_blockers:
            raise ValueError("A deterministically blocked source cannot be accepted")
        if self.evidence_scope != "production" and (
            self.production_acceptance_status != "not_evaluated"
        ):
            raise ValueError(
                "Private acceptance evidence cannot claim production acceptance"
            )
        if self.sequence == 1 and self.supersedes_report_ref is not None:
            raise ValueError("The first quality report cannot supersede another report")
        if self.sequence > 1 and self.supersedes_report_ref is None:
            raise ValueError("Later quality reports must supersede the previous report")
        bindings = {
            item.artifact_ref: item for item in self.source_snapshot.committed_sources
        }
        for blocker in self.deterministic_blockers:
            if not set(blocker.source_artifact_refs).issubset(bindings):
                raise ValueError("Quality blocker references an unbound source Artifact")
        for warning in self.literary_warnings:
            for anchor in warning.anchors:
                binding = bindings.get(anchor.artifact_ref)
                if binding is None or binding.unit_ref != anchor.unit_ref:
                    raise ValueError("Literary warning anchor is outside its source binding")
                if self.creation_route_id == "screenplay_sample" and not isinstance(
                    anchor, Phase32ScreenplayEvidenceAnchor
                ):
                    raise ValueError("Screenplay warning requires a screenplay anchor")
                if self.creation_route_id != "screenplay_sample" and not isinstance(
                    anchor, Phase32ProseEvidenceAnchor
                ):
                    raise ValueError("Prose warning requires a prose anchor")
        expected_digest = canonical_digest(
            self.model_dump(mode="json", exclude={"report_ref", "report_digest"})
        )
        if self.report_digest != expected_digest:
            raise ValueError("Quality report digest does not match its payload")
        if self.report_ref != f"p32-quality-report-{expected_digest}":
            raise ValueError("Quality report ref does not match its content digest")
        return self


QualityReportStaleReason = Literal["superseded", "source_changed"]


class Phase32QualityReportProjection(BaseModel):
    """Rebuildable current/stale view over append-only quality evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report: Phase32TextQualityReport
    freshness: Literal["current", "stale"]
    stale_reasons: tuple[QualityReportStaleReason, ...] = ()

    @model_validator(mode="after")
    def validate_freshness(self) -> Self:
        if (self.freshness == "stale") != bool(self.stale_reasons):
            raise ValueError("Quality report freshness must match its stale reasons")
        if len(self.stale_reasons) != len(set(self.stale_reasons)):
            raise ValueError("Quality report stale reasons must be unique")
        return self


def build_phase32_quality_source_snapshot(
    *,
    definition_digest: str,
    stage_id: Literal["script", "text"],
    ordered_unit_refs: tuple[str, ...],
    committed_sources: tuple[Phase32QualitySourceBinding, ...],
    planning_source: Phase32QualityPlanningSourceBinding | None = None,
) -> Phase32QualitySourceSnapshot:
    payload = {
        "definition_digest": definition_digest,
        "stage_id": stage_id,
        "ordered_unit_refs": list(ordered_unit_refs),
        "committed_sources": [
            item.model_dump(mode="json") for item in committed_sources
        ],
        "planning_source": (
            planning_source.model_dump(mode="json")
            if planning_source is not None
            else None
        ),
        "accepted_prefix_complete": len(committed_sources) == len(ordered_unit_refs),
    }
    payload["source_digest"] = canonical_digest(payload)
    return Phase32QualitySourceSnapshot.model_validate(payload)


def build_phase32_text_quality_report(
    *,
    run_id: str,
    creation_route_id: CreationRouteId,
    sequence: int,
    supersedes_report_ref: str | None,
    evidence_scope: QualityEvidenceScope,
    production_acceptance_status: ProductionAcceptanceStatus,
    source_snapshot: Phase32QualitySourceSnapshot,
    deterministic_blockers: tuple[Phase32DeterministicBlocker, ...],
    literary_warnings: tuple[Phase32LiteraryWarning, ...],
    cold_read: Phase32ColdReadRecord,
    recorded_at: str,
) -> Phase32TextQualityReport:
    payload = {
        "architecture_version": "phase32-routes-v1",
        "run_id": run_id,
        "creation_route_id": creation_route_id,
        "sequence": sequence,
        "supersedes_report_ref": supersedes_report_ref,
        "evidence_scope": evidence_scope,
        "production_acceptance_status": production_acceptance_status,
        "source_snapshot": source_snapshot.model_dump(mode="json"),
        "structure_contract": "blocked" if deterministic_blockers else "passed",
        "deterministic_blockers": [
            item.model_dump(mode="json") for item in deterministic_blockers
        ],
        "literary_warnings": [
            item.model_dump(mode="json") for item in literary_warnings
        ],
        "cold_read": cold_read.model_dump(mode="json"),
        "recorded_at": recorded_at,
    }
    digest = canonical_digest(payload)
    payload.update(
        report_ref=f"p32-quality-report-{digest}",
        report_digest=digest,
    )
    return Phase32TextQualityReport.model_validate(payload)


__all__ = [
    "ColdReadOutcome",
    "LiteraryImpact",
    "Phase32ColdReadRecord",
    "Phase32DeterministicBlocker",
    "Phase32LiteraryWarning",
    "Phase32ProseEvidenceAnchor",
    "Phase32QualityPlanningSourceBinding",
    "Phase32QualityEvidenceAnchor",
    "Phase32QualityReportProjection",
    "Phase32QualitySourceBinding",
    "Phase32QualitySourceSnapshot",
    "Phase32ScreenplayEvidenceAnchor",
    "Phase32TextQualityReport",
    "ProductionAcceptanceStatus",
    "QualityEvidenceScope",
    "QualityReportStaleReason",
    "build_phase32_quality_source_snapshot",
    "build_phase32_text_quality_report",
]
