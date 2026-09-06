"""Server-owned assembly and validation of Phase 32 text quality evidence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    ScreenplayDraftArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    DetailPlanIndexArtifact,
)
from novel_workflow.quality.phase32_quality_report import (
    ColdReadOutcome,
    Phase32ColdReadRecord,
    Phase32DeterministicBlocker,
    Phase32LiteraryWarning,
    Phase32ProseEvidenceAnchor,
    Phase32QualityPlanningSourceBinding,
    Phase32QualityReportProjection,
    Phase32QualitySourceBinding,
    Phase32QualitySourceSnapshot,
    Phase32ScreenplayEvidenceAnchor,
    Phase32TextQualityReport,
    ProductionAcceptanceStatus,
    build_phase32_quality_source_snapshot,
    build_phase32_text_quality_report,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_quality_report_store import (
    Phase32QualityReportStore,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.workflows.phase32_scale import (
    ScaleProfile,
    validate_continuity_acceptance_chapter_counts,
)
from novel_workflow.workflows.route_specs import CreationRouteId


class Phase32QualityReviewError(ValueError):
    code = "phase32_quality_review_invalid"


class Phase32QualityReviewCommand(BaseModel):
    """Human-authored findings applied to a server-derived source snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    reviewer_ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
    reviewer_role: str = Field(min_length=1, max_length=120)
    outcome: ColdReadOutcome
    summary: str = Field(min_length=1, max_length=4_000)
    literary_warnings: tuple[Phase32LiteraryWarning, ...] = Field(
        default=(), max_length=256
    )
    production_acceptance_status: ProductionAcceptanceStatus = "not_evaluated"


Clock = Callable[[], str]


class Phase32QualityReviewService:
    """Bind cold-read findings to immutable committed Phase 32 text sources."""

    def __init__(
        self,
        repository: Phase32RunRepository,
        artifacts: Phase32ArtifactStore,
        reports: Phase32QualityReportStore,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.reports = reports
        self.clock = clock or _now

    def record_review(
        self,
        run_id: str,
        command: Phase32QualityReviewCommand,
    ) -> Phase32TextQualityReport:
        record = self.repository.read(run_id)
        scale_profile = _scale_profile(record.definition.scale_profile.payload)
        source_snapshot, source_records = self._source_snapshot(
            record,
            scale_profile,
        )
        evidence_scope = scale_profile.profile_kind
        # Deterministic blockers are server-owned.  Until a trusted evaluator
        # receipt is wired into this service, callers cannot inject or clear them.
        blockers: list[Phase32DeterministicBlocker] = []
        if not source_snapshot.accepted_prefix_complete:
            blockers.insert(
                0,
                Phase32DeterministicBlocker(
                    code="accepted_prefix_incomplete",
                    evidence=(
                        f"accepted {len(source_snapshot.committed_sources)} of "
                        f"{len(source_snapshot.ordered_unit_refs)} frozen units"
                    ),
                    required_action=(
                        "Complete the frozen accepted prefix before production acceptance."
                    ),
                    source_artifact_refs=tuple(
                        item.artifact_ref
                        for item in source_snapshot.committed_sources
                    ),
                ),
            )
        self._validate_blocker_sources(blockers, source_snapshot)
        self._validate_literary_anchors(
            command.literary_warnings,
            record.definition.creation_route_id,
            source_snapshot,
            source_records,
        )
        if evidence_scope != "production" and (
            command.production_acceptance_status != "not_evaluated"
        ):
            scope_label = (
                "Release-smoke"
                if evidence_scope == "release_smoke"
                else "Continuity-acceptance"
            )
            raise Phase32QualityReviewError(
                f"{scope_label} evidence cannot claim production acceptance"
            )
        if command.production_acceptance_status == "accepted":
            if blockers or not source_snapshot.accepted_prefix_complete:
                raise Phase32QualityReviewError(
                    "Production acceptance requires a complete, unblocked text prefix"
                )
            raise Phase32QualityReviewError(
                "Production acceptance requires a trusted code-owned deterministic "
                "gate receipt; no evaluator is configured"
            )
        existing = self.reports.list(run_id)
        predecessor = existing[-1].report_ref if existing else None
        recorded_at = self.clock()
        report = build_phase32_text_quality_report(
            run_id=run_id,
            creation_route_id=record.definition.creation_route_id,
            sequence=len(existing) + 1,
            supersedes_report_ref=predecessor,
            evidence_scope=evidence_scope,
            production_acceptance_status=command.production_acceptance_status,
            source_snapshot=source_snapshot,
            deterministic_blockers=tuple(blockers),
            literary_warnings=command.literary_warnings,
            cold_read=Phase32ColdReadRecord(
                reviewer_ref=command.reviewer_ref,
                reviewer_role=command.reviewer_role,
                outcome=command.outcome,
                summary=command.summary,
                reviewed_at=recorded_at,
            ),
            recorded_at=recorded_at,
        )
        return self.reports.append(report)

    def source_snapshot(self, run_id: str) -> Phase32QualitySourceSnapshot:
        """Return the current server-derived accepted text prefix."""

        record = self.repository.read(run_id)
        snapshot, _records = self._source_snapshot(
            record,
            _scale_profile(record.definition.scale_profile.payload),
        )
        return snapshot

    def projections(self, run_id: str) -> tuple[Phase32QualityReportProjection, ...]:
        """Project immutable history against the current committed source prefix."""

        current = self.source_snapshot(run_id)
        reports = self.reports.list(run_id)
        latest_ref = reports[-1].report_ref if reports else None
        projected: list[Phase32QualityReportProjection] = []
        for report in reports:
            reasons: list[Literal["superseded", "source_changed"]] = []
            if report.report_ref != latest_ref:
                reasons.append("superseded")
            if report.source_snapshot.source_digest != current.source_digest:
                reasons.append("source_changed")
            projected.append(
                Phase32QualityReportProjection(
                    report=report,
                    freshness="stale" if reasons else "current",
                    stale_reasons=tuple(reasons),
                )
            )
        return tuple(projected)

    def _source_snapshot(
        self,
        record: Phase32RunRecord,
        scale_profile: ScaleProfile,
    ) -> tuple[Phase32QualitySourceSnapshot, dict[str, Phase32ArtifactRecord]]:
        run_id = record.definition.run_id
        route_id = record.definition.creation_route_id
        stage_id: Literal["script", "text"] = (
            "script" if route_id == "screenplay_sample" else "text"
        )
        progress = record.read_model.sequential_stage_progress.get(stage_id)
        if progress is None:
            raise Phase32QualityReviewError(
                f"Run has no accepted-prefix projection for {stage_id}"
            )
        planning_source: Phase32QualityPlanningSourceBinding | None = None
        if scale_profile.profile_kind == "continuity_acceptance":
            planning_source = self._validate_continuity_acceptance_source(
                record,
                scale_profile,
                progress.ordered_unit_refs,
            )
        source_bindings: list[Phase32QualitySourceBinding] = []
        source_records: dict[str, Phase32ArtifactRecord] = {}
        for ordinal, (unit_ref, artifact_ref) in enumerate(
            progress.committed_artifact_refs.items(), start=1
        ):
            try:
                artifact = self.artifacts.read(run_id, artifact_ref)
            except Exception as exc:
                raise Phase32QualityReviewError(
                    f"Cannot resolve committed quality source {artifact_ref}"
                ) from exc
            self._validate_source_record(
                artifact,
                route_id=route_id,
                stage_id=stage_id,
                unit_ref=unit_ref,
            )
            source_bindings.append(
                Phase32QualitySourceBinding(
                    ordinal=ordinal,
                    unit_ref=unit_ref,
                    artifact_ref=artifact.artifact_ref,
                    artifact_kind=artifact.artifact_kind,
                    payload_digest=artifact.payload_digest,
                )
            )
            source_records[artifact.artifact_ref] = artifact
        return (
            build_phase32_quality_source_snapshot(
                definition_digest=record.definition.definition_digest,
                stage_id=stage_id,
                ordered_unit_refs=progress.ordered_unit_refs,
                committed_sources=tuple(source_bindings),
                planning_source=planning_source,
            ),
            source_records,
        )

    def _validate_continuity_acceptance_source(
        self,
        record: Phase32RunRecord,
        scale_profile: ScaleProfile,
        ordered_unit_refs: tuple[str, ...],
    ) -> Phase32QualityPlanningSourceBinding:
        """Bind private exact-12 evidence to the current Rolling Detail root."""

        if "rolling_detail" in record.read_model.stale_stage_ids:
            raise Phase32QualityReviewError(
                "Continuity acceptance requires a current Rolling Detail Artifact"
            )
        projection = record.read_model.artifact_refs.get("rolling_detail")
        if projection is None:
            raise Phase32QualityReviewError(
                "Continuity acceptance requires a committed Rolling Detail Artifact"
            )
        try:
            artifact = self.artifacts.read(
                record.definition.run_id,
                projection.artifact_ref,
            )
            if (
                artifact.creation_route_id != "long_novel"
                or artifact.stage_id != "rolling_detail"
                or artifact.artifact_kind != "detail_plan_index"
                or artifact.status != "committed"
                or artifact.artifact_ref != projection.artifact_ref
            ):
                raise ValueError(
                    "Rolling Detail projection does not resolve to its committed root"
                )
            detail = DetailPlanIndexArtifact.model_validate(artifact.payload)
            validate_continuity_acceptance_chapter_counts(
                scale_profile,
                window_chapter_counts=tuple(
                    len(window.chapters) for window in detail.windows
                ),
                window_volume_counts=tuple(
                    len(window.volume_refs) for window in detail.windows
                ),
            )
        except Exception as exc:
            raise Phase32QualityReviewError(
                f"Invalid continuity acceptance Rolling Detail: {exc}"
            ) from exc
        detail_chapter_refs = tuple(
            chapter.chapter_ref
            for window in detail.windows
            for chapter in window.chapters
        )
        if ordered_unit_refs != detail_chapter_refs:
            raise Phase32QualityReviewError(
                "Continuity acceptance ordered text units must exactly match the "
                "current Rolling Detail chapter refs"
            )
        return Phase32QualityPlanningSourceBinding(
            artifact_ref=artifact.artifact_ref,
            payload_digest=artifact.payload_digest,
        )

    @staticmethod
    def _validate_source_record(
        artifact: Phase32ArtifactRecord,
        *,
        route_id: CreationRouteId,
        stage_id: Literal["script", "text"],
        unit_ref: str,
    ) -> None:
        if (
            artifact.creation_route_id != route_id
            or artifact.stage_id != stage_id
            or artifact.status != "committed"
        ):
            raise Phase32QualityReviewError(
                "Quality source must be a committed Artifact from the current route stage"
            )
        if route_id == "screenplay_sample":
            payload_unit_ref = ScreenplayDraftArtifact.model_validate(
                artifact.payload
            ).scene_ref
        elif route_id == "short_novel":
            payload_unit_ref = ShortProseUnitArtifact.model_validate(
                artifact.payload
            ).unit_ref
        else:
            payload_unit_ref = ChapterArtifact.model_validate(artifact.payload).chapter_ref
        if payload_unit_ref != unit_ref:
            raise Phase32QualityReviewError(
                "Quality source payload identity differs from its accepted unit"
            )

    @staticmethod
    def _validate_blocker_sources(
        blockers: list[Phase32DeterministicBlocker],
        snapshot: Phase32QualitySourceSnapshot,
    ) -> None:
        known = {item.artifact_ref for item in snapshot.committed_sources}
        for blocker in blockers:
            unknown = set(blocker.source_artifact_refs) - known
            if unknown:
                raise Phase32QualityReviewError(
                    "Deterministic blocker references sources outside the reviewed prefix"
                )

    def _validate_literary_anchors(
        self,
        warnings: tuple[Phase32LiteraryWarning, ...],
        route_id: CreationRouteId,
        snapshot: Phase32QualitySourceSnapshot,
        source_records: dict[str, Phase32ArtifactRecord],
    ) -> None:
        bindings = {item.artifact_ref: item for item in snapshot.committed_sources}
        for warning in warnings:
            for anchor in warning.anchors:
                binding = bindings.get(anchor.artifact_ref)
                if binding is None or binding.unit_ref != anchor.unit_ref:
                    raise Phase32QualityReviewError(
                        "Literary evidence anchor is outside the reviewed source prefix"
                    )
                source = source_records[anchor.artifact_ref]
                if isinstance(anchor, Phase32ProseEvidenceAnchor):
                    if route_id == "screenplay_sample":
                        raise Phase32QualityReviewError(
                            "Screenplay reviews require screenplay block anchors"
                        )
                    self._validate_prose_anchor(anchor, route_id, source)
                elif isinstance(anchor, Phase32ScreenplayEvidenceAnchor):
                    if route_id != "screenplay_sample":
                        raise Phase32QualityReviewError(
                            "Prose reviews require prose span anchors"
                        )
                    self._validate_screenplay_anchor(anchor, source)

    @staticmethod
    def _validate_prose_anchor(
        anchor: Phase32ProseEvidenceAnchor,
        route_id: CreationRouteId,
        source: Phase32ArtifactRecord,
    ) -> None:
        if route_id == "short_novel":
            content = ShortProseUnitArtifact.model_validate(source.payload).content
        else:
            content = ChapterArtifact.model_validate(source.payload).content
        if anchor.end_offset > len(content) or (
            content[anchor.start_offset : anchor.end_offset] != anchor.exact_text
        ):
            raise Phase32QualityReviewError(
                "Prose evidence anchor does not match the committed source text"
            )

    @staticmethod
    def _validate_screenplay_anchor(
        anchor: Phase32ScreenplayEvidenceAnchor,
        source: Phase32ArtifactRecord,
    ) -> None:
        screenplay = ScreenplayDraftArtifact.model_validate(source.payload)
        if anchor.block_index >= len(screenplay.blocks):
            raise Phase32QualityReviewError(
                "Screenplay evidence block index is outside the committed source"
            )
        block = screenplay.blocks[anchor.block_index]
        if block.kind != anchor.block_kind:
            raise Phase32QualityReviewError(
                "Screenplay evidence block kind does not match the committed source"
            )
        if anchor.end_offset > len(block.text) or (
            block.text[anchor.start_offset : anchor.end_offset] != anchor.exact_text
        ):
            raise Phase32QualityReviewError(
                "Screenplay evidence anchor does not match the committed block text"
            )


def _scale_profile(payload: dict[str, object]) -> ScaleProfile:
    try:
        return ScaleProfile.model_validate(payload)
    except Exception as exc:
        raise Phase32QualityReviewError(
            "Quality evidence requires a typed Phase 32 scale profile"
        ) from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32QualityReviewCommand",
    "Phase32QualityReviewError",
    "Phase32QualityReviewService",
]
