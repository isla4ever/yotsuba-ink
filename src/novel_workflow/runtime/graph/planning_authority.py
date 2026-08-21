from __future__ import annotations

"""Runtime authority for hierarchical planning commits and bounded Context reads."""

from dataclasses import dataclass
from typing import Any

from novel_workflow.orchestration.planning_aggregate_commit import (
    HierarchicalPlanningCommitter,
)
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
from novel_workflow.storage.narrative_run_repository import NarrativeRunRepository
from novel_workflow.storage.planning_aggregate_store import (
    PlanningAggregateCandidateManifest,
    PlanningAggregateManifest,
    PlanningAggregateStore,
    PlanningStageId,
)
from novel_workflow.workflows.hierarchical_scale import HierarchicalNarrativeScalePlan


class FlatPlanningArtifactRejected(ValueError):
    """A new executable Run tried to use a retired flat planning reference."""


class PlanningCandidateNotCommitted(ValueError):
    """A hierarchical candidate was presented as committed Context authority."""


@dataclass(frozen=True, slots=True)
class HierarchicalPlanningAuthority:
    runs: NarrativeRunRepository
    store: PlanningAggregateStore

    def save_spine_candidate(
        self,
        run_id: str,
        root: StorySpineRootArtifact,
        parts: list[PartArcArtifact],
        turns: list[PartTurnArtifact],
        *,
        source: str,
    ) -> PlanningAggregateCandidateManifest:
        plan = self._plan(run_id)
        _require_spine_scale(plan, root, parts, turns)
        return self._committer().save_spine_candidate(
            run_id,
            root,
            parts,
            turns,
            source=source,
        )

    def accept_spine_candidate(
        self,
        run_id: str,
        candidate_id: str,
    ) -> PlanningAggregateManifest:
        try:
            accepted = self.store.candidate_acceptance(run_id, "spine", candidate_id)
        except FileNotFoundError:
            accepted = None
        if accepted is not None:
            committed = self.store.manifest(run_id, "spine", accepted.version_id)
            if committed.signature != accepted.signature:
                raise ValueError("Planning candidate acceptance signature mismatch")
            return committed

        candidate = self._spine_candidate(run_id, candidate_id)
        root = StorySpineRootArtifact.model_validate(candidate["root"])
        parts = [PartArcArtifact.model_validate(value) for value in candidate["units"]["parts"]]
        turns = [PartTurnArtifact.model_validate(value) for value in candidate["units"]["turns"]]
        committed = self.commit_spine(
            run_id,
            root,
            parts,
            turns,
            source=str(candidate["manifest"]["source"]),
        )
        self.store.record_acceptance(run_id, "spine", candidate_id, committed.version_id)
        return committed

    def commit_spine(
        self,
        run_id: str,
        root: StorySpineRootArtifact,
        parts: list[PartArcArtifact],
        turns: list[PartTurnArtifact],
        *,
        source: str,
    ) -> PlanningAggregateManifest:
        plan = self._plan(run_id)
        _require_spine_scale(plan, root, parts, turns)
        return self._committer().commit_spine(
            run_id,
            root,
            parts,
            turns,
            source=source,
        )

    def commit_volumes(
        self,
        run_id: str,
        root: VolumeArchitectureRootArtifact,
        volumes: list[VolumeUnitArtifact],
        *,
        spine_version_id: str,
        source: str,
    ) -> PlanningAggregateManifest:
        plan = self._plan(run_id)
        spine_root = StorySpineRootArtifact.model_validate(
            self._root(run_id, "spine", spine_version_id)
        )
        parts = [
            PartArcArtifact.model_validate(value)
            for value in self.store.read_units(
                run_id,
                "spine",
                spine_version_id,
                "parts",
                spine_root.part_refs,
            )
        ]
        _require_volume_scale(plan, spine_root, root, volumes)
        return self._committer().commit_volumes(
            run_id,
            spine_root,
            root,
            parts,
            volumes,
            source=source,
        )

    def commit_detail(
        self,
        run_id: str,
        root: DetailPlanIndexArtifact,
        windows: list[DetailWindowArtifact],
        chapters: list[DetailChapterUnitArtifact],
        *,
        volume_version_id: str,
        source: str,
    ) -> PlanningAggregateManifest:
        plan = self._plan(run_id)
        volume_root = VolumeArchitectureRootArtifact.model_validate(
            self._root(run_id, "volumes", volume_version_id)
        )
        _require_detail_scale(plan, volume_root, root, windows, chapters)
        return self._committer().commit_detail(
            run_id,
            root,
            windows,
            chapters,
            source=source,
        )

    def spine_part_context(
        self,
        run_id: str,
        version_id: str,
        part_ref: str,
    ) -> dict[str, Any]:
        manifest = self._manifest(run_id, "spine", version_id)
        root = StorySpineRootArtifact.model_validate(
            self.store.read_root(run_id, "spine", version_id)
        )
        if part_ref not in root.part_refs:
            raise ValueError("Spine Context requested a Part outside the committed root")
        part = PartArcArtifact.model_validate(
            self.store.read_unit(run_id, "spine", version_id, "parts", part_ref)
        )
        turns = [
            PartTurnArtifact.model_validate(value)
            for value in self.store.read_units(
                run_id,
                "spine",
                version_id,
                "turns",
                part.turn_refs,
            )
        ]
        return {
            "source": _source_ref(manifest),
            "root": root.model_dump(mode="json"),
            "part": part.model_dump(mode="json"),
            "turns": [turn.model_dump(mode="json") for turn in turns],
        }

    def volume_part_context(
        self,
        run_id: str,
        version_id: str,
        part_ref: str,
    ) -> dict[str, Any]:
        manifest = self._manifest(run_id, "volumes", version_id)
        root = VolumeArchitectureRootArtifact.model_validate(
            self.store.read_root(run_id, "volumes", version_id)
        )
        volume_refs = root.part_volume_order.get(part_ref)
        if volume_refs is None:
            raise ValueError("Volume Context requested a Part outside the committed root")
        volumes = [
            VolumeUnitArtifact.model_validate(value)
            for value in self.store.read_units(
                run_id,
                "volumes",
                version_id,
                "volumes",
                volume_refs,
            )
        ]
        return {
            "source": _source_ref(manifest),
            "root": root.model_dump(mode="json"),
            "part_ref": part_ref,
            "volumes": [volume.model_dump(mode="json") for volume in volumes],
        }

    def detail_window_context(
        self,
        run_id: str,
        version_id: str,
        window_ref: str,
    ) -> dict[str, Any]:
        manifest = self._manifest(run_id, "detail", version_id)
        root = DetailPlanIndexArtifact.model_validate(
            self.store.read_root(run_id, "detail", version_id)
        )
        if window_ref not in root.window_order:
            raise ValueError("Detail Context requested a window outside the committed root")
        window = DetailWindowArtifact.model_validate(
            self.store.read_unit(run_id, "detail", version_id, "windows", window_ref)
        )
        chapters = [
            DetailChapterUnitArtifact.model_validate(value)
            for value in self.store.read_units(
                run_id,
                "detail",
                version_id,
                "chapters",
                window.chapter_refs,
            )
        ]
        return {
            "source": _source_ref(manifest),
            "root": root.model_dump(mode="json"),
            "window": window.model_dump(mode="json"),
            "chapters": [chapter.model_dump(mode="json") for chapter in chapters],
        }

    def _plan(self, run_id: str) -> HierarchicalNarrativeScalePlan:
        definition = self.runs.executable_definition(run_id)
        plan = definition.hierarchical_scale_plan
        if plan is None:  # executable_definition owns this invariant.
            raise ValueError("Executable Run is missing its hierarchical scale plan")
        return plan

    def _manifest(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
    ) -> PlanningAggregateManifest:
        self._plan(run_id)
        try:
            manifest = self.store.manifest(run_id, stage_id, version_id)
        except FileNotFoundError as exc:
            if self.store.candidate_exists(run_id, stage_id, version_id):
                raise PlanningCandidateNotCommitted(
                    f"Planning candidate {version_id} is not committed {stage_id} authority"
                ) from exc
            if version_id.startswith(
                (f"{stage_id}-candidate-", f"{stage_id}-committed-")
            ):
                raise FlatPlanningArtifactRejected(
                    f"Executable Run {run_id} cannot read flat {stage_id} Artifact ref "
                    f"{version_id}; a committed hierarchical aggregate version is required"
                ) from exc
            raise FileNotFoundError(
                f"Missing committed hierarchical {stage_id} aggregate {version_id}"
            ) from exc
        if manifest.run_id != run_id or manifest.stage_id != stage_id:
            raise ValueError("Planning aggregate manifest identity mismatch")
        return manifest

    def _spine_candidate(self, run_id: str, candidate_id: str) -> dict[str, Any]:
        self._plan(run_id)
        candidate_exists = self.store.candidate_exists(run_id, "spine", candidate_id)
        try:
            return self.store.read_candidate(run_id, "spine", candidate_id)
        except FileNotFoundError as exc:
            if candidate_exists:
                raise FileNotFoundError(
                    f"Incomplete hierarchical Spine candidate {candidate_id}"
                ) from exc
            if candidate_id.startswith(("spine-candidate-", "spine-committed-")):
                raise FlatPlanningArtifactRejected(
                    f"Executable Run {run_id} cannot accept flat Spine Artifact ref {candidate_id}"
                ) from exc
            raise FileNotFoundError(
                f"Missing hierarchical Spine candidate {candidate_id}"
            ) from exc

    def _root(
        self,
        run_id: str,
        stage_id: PlanningStageId,
        version_id: str,
    ) -> dict[str, Any]:
        self._manifest(run_id, stage_id, version_id)
        return self.store.read_root(run_id, stage_id, version_id)

    def _committer(self) -> HierarchicalPlanningCommitter:
        return HierarchicalPlanningCommitter(self.store)


def _require_spine_scale(
    plan: HierarchicalNarrativeScalePlan,
    root: StorySpineRootArtifact,
    parts: list[PartArcArtifact],
    turns: list[PartTurnArtifact],
) -> None:
    if len(parts) != plan.part_target or root.part_refs != [part.id for part in parts]:
        raise ValueError("Spine aggregate must match the frozen Part target and order")
    turns_by_part = {
        part.id: [turn for turn in turns if turn.part_ref == part.id]
        for part in parts
    }
    for part, part_plan in zip(parts, plan.parts, strict=True):
        owned = turns_by_part[part.id]
        if part.display_ordinal != part_plan.ordinal:
            raise ValueError("Spine Part ordinals must match the frozen scale plan")
        if len(owned) != part_plan.turn_target or part.turn_refs != [turn.id for turn in owned]:
            raise ValueError("Each Spine Part must match its frozen local turn target and order")


def _require_volume_scale(
    plan: HierarchicalNarrativeScalePlan,
    spine_root: StorySpineRootArtifact,
    root: VolumeArchitectureRootArtifact,
    volumes: list[VolumeUnitArtifact],
) -> None:
    if root.part_refs != spine_root.part_refs:
        raise ValueError("Volume aggregate must use the committed Spine Part order")
    if len(volumes) != plan.volume_target or root.volume_refs != [item.id for item in volumes]:
        raise ValueError("Volume aggregate must match the frozen Volume target and order")
    by_part = {
        part_ref: [volume.id for volume in volumes if volume.part_ref == part_ref]
        for part_ref in root.part_refs
    }
    for part_ref, part_plan in zip(root.part_refs, plan.parts, strict=True):
        if len(by_part[part_ref]) != part_plan.volume_target:
            raise ValueError("Each Part must match its frozen local Volume target")


def _require_detail_scale(
    plan: HierarchicalNarrativeScalePlan,
    volume_root: VolumeArchitectureRootArtifact,
    root: DetailPlanIndexArtifact,
    windows: list[DetailWindowArtifact],
    chapters: list[DetailChapterUnitArtifact],
) -> None:
    if root.volume_refs != volume_root.volume_refs:
        raise ValueError("Detail aggregate must use the committed Volume order")
    if len(chapters) != plan.chapter_target or root.chapter_order != [item.id for item in chapters]:
        raise ValueError("Detail aggregate must match the frozen Chapter target and order")
    if root.window_order != [item.id for item in windows]:
        raise ValueError("Detail aggregate must preserve its committed window order")
    if any(len(window.chapter_refs) > plan.detail_window_max for window in windows):
        raise ValueError("Detail window exceeds the frozen bounded Context capacity")


def _source_ref(manifest: PlanningAggregateManifest) -> dict[str, str]:
    return {
        "stage_id": manifest.stage_id,
        "version_id": manifest.version_id,
        "signature": manifest.signature,
    }


__all__ = [
    "FlatPlanningArtifactRejected",
    "HierarchicalPlanningAuthority",
    "PlanningCandidateNotCommitted",
]
