"""Deterministic impact analysis for Phase 32 planning Artifact amendments."""

from __future__ import annotations

from typing import Any

from novel_workflow.output_contracts.phase32_artifact_amendment import (
    AmendmentBlockedReference,
    AmendmentImpactTarget,
    ArtifactImpactAnalysis,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_run_repository import Phase32RunRecord
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.route_compiler import CompiledRouteStage


_PLANNING_ARTIFACT_KINDS = frozenset(
    {
        "screenplay_brief",
        "novel_brief",
        "character_bible",
        "beat_board",
        "scene_deck",
        "story_map",
        "section_plan",
        "book_architecture",
        "volume_architecture",
        "detail_plan_index",
    }
)
_OWNED_REFERENCE_FIELDS = {
    "brief": frozenset(),
    "cast": frozenset({"subject_ref"}),
    "beat_board": frozenset({"beat_ref", "setup_or_payoff_refs"}),
    "scene_deck": frozenset({"scene_ref"}),
    "story_map": frozenset({"anchor_ref", "promise_refs"}),
    "section_plan": frozenset({"unit_ref"}),
    "book_architecture": frozenset(
        {"part_ref", "promise_refs", "turning_point_refs"}
    ),
    "volumes": frozenset({"volume_ref"}),
    "rolling_detail": frozenset({"window_ref", "chapter_ref", "scene_ref"}),
}


def is_phase32_planning_artifact_kind(artifact_kind: str) -> bool:
    return artifact_kind in _PLANNING_ARTIFACT_KINDS


class Phase32ArtifactImpactAnalyzer:
    """Read current immutable refs and derive one reproducible impact payload."""

    def __init__(self, artifacts: Phase32ArtifactStore) -> None:
        self.artifacts = artifacts

    def analyze(
        self,
        record: Phase32RunRecord,
        *,
        amendment_id: str,
        source: Phase32ArtifactRecord,
        proposed_payload: dict[str, Any],
        proposed_payload_digest: str,
    ) -> ArtifactImpactAnalysis:
        stages = record.definition.route_contract.route_manifest.stages
        source_ordinal = record.definition.stage(source.stage_id).ordinal
        descendants = tuple(stage for stage in stages if stage.ordinal > source_ordinal)
        material_stage_ids = {
            stage.stage_id
            for stage in descendants
            if stage.stage_id in record.read_model.artifact_refs
            or bool(
                record.read_model.sequential_stage_progress.get(stage.stage_id)
                and record.read_model.sequential_stage_progress[
                    stage.stage_id
                ].committed_artifact_refs
            )
            or record.read_model.stage_status.get(stage.stage_id)
            in {"running", "awaiting_decision", "completed", "failed"}
        }
        affected_scope = tuple(
            stage.stage_id for stage in descendants if stage.stage_id in material_stage_ids
        )
        restart_scope = tuple(stage.stage_id for stage in descendants)
        preserved = [
            AmendmentImpactTarget(
                stage_id=source.stage_id,
                artifact_kind=source.artifact_kind,
                artifact_ref=source.artifact_ref,
                reason="source_version_history",
            )
        ]
        for stage in stages[:source_ordinal]:
            projection = record.read_model.artifact_refs.get(stage.stage_id)
            if projection is not None:
                preserved.append(
                    AmendmentImpactTarget(
                        stage_id=stage.stage_id,
                        artifact_kind=stage.artifact_kind,
                        artifact_ref=projection.artifact_ref,
                        reason="upstream_committed",
                    )
                )
        stale = tuple(
            AmendmentImpactTarget(
                stage_id=stage.stage_id,
                artifact_kind=stage.artifact_kind,
                artifact_ref=(
                    record.read_model.artifact_refs[stage.stage_id].artifact_ref
                    if stage.stage_id in record.read_model.artifact_refs
                    else ""
                ),
                reason="transitive_downstream_dependency",
            )
            for stage in descendants
            if stage.stage_id in material_stage_ids
        )
        historical_frozen = self._historical_frozen(record, descendants)
        removed_refs = _owned_refs(source.stage_id, source.payload) - _owned_refs(
            source.stage_id,
            proposed_payload,
        )
        blocked = self._blocked_references(record, descendants, removed_refs)
        base = {
            "amendment_id": amendment_id,
            "run_id": record.definition.run_id,
            "creation_route_id": record.definition.creation_route_id,
            "route_revision": record.definition.route_revision,
            "definition_digest": record.definition.definition_digest,
            "source_stage_id": source.stage_id,
            "source_artifact_ref": source.artifact_ref,
            "source_payload_digest": source.payload_digest,
            "proposed_payload_digest": proposed_payload_digest,
            "source_domain_revision": record.state.domain_revision,
            "preserved": tuple(preserved),
            "stale": stale,
            "historical_frozen": historical_frozen,
            "blocked_references": blocked,
            "affected_only_scope": affected_scope,
            "restart_from_stage_scope": restart_scope,
        }
        digest = canonical_digest(
            ArtifactImpactAnalysis.model_construct(
                impact_id="p32-impact-" + "0" * 32,
                impact_digest="0" * 64,
                **base,
            ).model_dump(mode="json", exclude={"impact_id", "impact_digest"})
        )
        return ArtifactImpactAnalysis(
            impact_id=f"p32-impact-{digest[:32]}",
            impact_digest=digest,
            **base,
        )

    @staticmethod
    def _historical_frozen(
        record: Phase32RunRecord,
        descendants: tuple[CompiledRouteStage, ...],
    ) -> tuple[AmendmentImpactTarget, ...]:
        targets: list[AmendmentImpactTarget] = []
        for stage in descendants:
            if stage.stage_id not in {"script", "text"}:
                continue
            progress = record.read_model.sequential_stage_progress.get(stage.stage_id)
            if progress is None:
                continue
            for unit_ref, artifact_ref in progress.committed_artifact_refs.items():
                targets.append(
                    AmendmentImpactTarget(
                        stage_id=stage.stage_id,
                        artifact_kind=stage.artifact_kind,
                        artifact_ref=artifact_ref,
                        unit_ref=unit_ref,
                        reason="accepted_prefix_immutable",
                    )
                )
        return tuple(targets)

    def _blocked_references(
        self,
        record: Phase32RunRecord,
        descendants: tuple[CompiledRouteStage, ...],
        removed_refs: set[str],
    ) -> tuple[AmendmentBlockedReference, ...]:
        if not removed_refs:
            return ()
        blocked: list[AmendmentBlockedReference] = []
        for stage in descendants:
            targets: list[tuple[str, str]] = []
            projection = record.read_model.artifact_refs.get(stage.stage_id)
            if projection is not None:
                targets.append(("", projection.artifact_ref))
            progress = record.read_model.sequential_stage_progress.get(stage.stage_id)
            if progress is not None:
                targets.extend(progress.committed_artifact_refs.items())
            seen_artifacts: set[str] = set()
            for unit_ref, artifact_ref in targets:
                if artifact_ref in seen_artifacts:
                    continue
                seen_artifacts.add(artifact_ref)
                artifact = self.artifacts.read(record.definition.run_id, artifact_ref)
                referenced = _referenced_refs(artifact.payload)
                for reference in sorted(removed_refs & referenced):
                    blocked.append(
                        AmendmentBlockedReference(
                            reference=reference,
                            referenced_stage_id=stage.stage_id,
                            referenced_artifact_ref=artifact_ref,
                            unit_ref=unit_ref,
                        )
                    )
        return tuple(
            sorted(
                blocked,
                key=lambda item: (
                    record.definition.stage(item.referenced_stage_id).ordinal,
                    item.unit_ref,
                    item.reference,
                    item.referenced_artifact_ref,
                ),
            )
        )


def _owned_refs(stage_id: str, payload: dict[str, Any]) -> set[str]:
    fields = _OWNED_REFERENCE_FIELDS.get(stage_id, frozenset())
    return _collect_refs(payload, lambda key: key in fields)


def _referenced_refs(payload: dict[str, Any]) -> set[str]:
    return _collect_refs(
        payload,
        lambda key: key.endswith("_ref") or key.endswith("_refs"),
    )


def _collect_refs(value: Any, field_matches, *, key: str = "") -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            refs.update(_collect_refs(child, field_matches, key=str(child_key)))
        return refs
    if isinstance(value, (list, tuple)):
        for child in value:
            refs.update(_collect_refs(child, field_matches, key=key))
        return refs
    if isinstance(value, str) and key and field_matches(key) and value:
        refs.add(value)
    return refs


__all__ = [
    "Phase32ArtifactImpactAnalyzer",
    "is_phase32_planning_artifact_kind",
]
