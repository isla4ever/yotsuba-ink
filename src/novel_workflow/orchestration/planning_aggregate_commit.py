from __future__ import annotations

"""Domain boundary for validating and committing planning aggregates."""

from novel_workflow.output_contracts.planning_hierarchy import (
    DetailChapterUnitArtifact,
    DetailPlanIndexArtifact,
    DetailWindowArtifact,
    PartArcArtifact,
    PartTurnArtifact,
    StorySpineRootArtifact,
    VolumeArchitectureRootArtifact,
    VolumeUnitArtifact,
)
from novel_workflow.output_contracts.planning_hierarchy_validation import (
    validate_detail_aggregate,
    validate_spine_aggregate,
    validate_volume_aggregate,
)
from novel_workflow.storage.planning_aggregate_store import (
    PlanningAggregateCandidateManifest,
    PlanningAggregateManifest,
    PlanningAggregateStore,
)


class HierarchicalPlanningCommitter:
    """Validate one complete aggregate before publishing any unit files."""

    def __init__(self, store: PlanningAggregateStore) -> None:
        self.store = store

    def commit_spine(
        self,
        run_id: str,
        root: StorySpineRootArtifact,
        parts: list[PartArcArtifact],
        turns: list[PartTurnArtifact],
        *,
        source: str,
    ) -> PlanningAggregateManifest:
        validate_spine_aggregate(root, parts, turns)
        return self.store.commit(
            run_id,
            "spine",
            root,
            {"parts": parts, "turns": turns},
            source=source,
        )

    def save_spine_candidate(
        self,
        run_id: str,
        root: StorySpineRootArtifact,
        parts: list[PartArcArtifact],
        turns: list[PartTurnArtifact],
        *,
        source: str,
    ) -> PlanningAggregateCandidateManifest:
        validate_spine_aggregate(root, parts, turns)
        return self.store.save_candidate(
            run_id,
            "spine",
            root,
            {"parts": parts, "turns": turns},
            source=source,
        )

    def commit_volumes(
        self,
        run_id: str,
        spine_root: StorySpineRootArtifact,
        volume_root: VolumeArchitectureRootArtifact,
        parts: list[PartArcArtifact],
        volumes: list[VolumeUnitArtifact],
        *,
        source: str,
    ) -> PlanningAggregateManifest:
        validate_volume_aggregate(spine_root, volume_root, parts, volumes)
        return self.store.commit(
            run_id,
            "volumes",
            volume_root,
            {"volumes": volumes},
            source=source,
        )

    def commit_detail(
        self,
        run_id: str,
        index: DetailPlanIndexArtifact,
        windows: list[DetailWindowArtifact],
        chapters: list[DetailChapterUnitArtifact],
        *,
        source: str,
    ) -> PlanningAggregateManifest:
        validate_detail_aggregate(index, windows, chapters)
        return self.store.commit(
            run_id,
            "detail",
            index,
            {"windows": windows, "chapters": chapters},
            source=source,
        )


__all__ = ["HierarchicalPlanningCommitter"]
