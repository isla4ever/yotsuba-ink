from __future__ import annotations

from dataclasses import dataclass

from novel_workflow.output_contracts.planning_hierarchy import (
    DetailChapterUnitArtifact,
    DetailPlanIndexArtifact,
    DetailWindowArtifact,
    PartArcArtifact,
    PartTurnArtifact,
    StorySpineRootArtifact,
    VolumeArchitectureRootArtifact,
    VolumeUnitArtifact,
    mint_stable_ref,
)
from novel_workflow.workflows.hierarchical_scale import HierarchicalNarrativeScalePlan


@dataclass(frozen=True, slots=True)
class HierarchicalPlanningSkeleton:
    spine_root: StorySpineRootArtifact
    parts: list[PartArcArtifact]
    turns: list[PartTurnArtifact]
    volume_root: VolumeArchitectureRootArtifact
    volumes: list[VolumeUnitArtifact]
    detail_index: DetailPlanIndexArtifact
    windows: list[DetailWindowArtifact]
    chapters: list[DetailChapterUnitArtifact]


class FakeHierarchicalPlanningProvider:
    """Deterministic Provider double for the Wave 29.1 planning boundary."""

    def __init__(self, *, seed: str = "wave-29-1") -> None:
        self.seed = seed
        self.calls = 0

    async def generate_planning_skeleton(
        self,
        plan: HierarchicalNarrativeScalePlan,
    ) -> HierarchicalPlanningSkeleton:
        self.calls += 1
        parts: list[PartArcArtifact] = []
        turns: list[PartTurnArtifact] = []
        volume_refs: list[str] = []
        part_volume_order: dict[str, list[str]] = {}
        volumes: list[VolumeUnitArtifact] = []
        volume_chapter_order: dict[str, list[str]] = {}
        all_chapters: list[DetailChapterUnitArtifact] = []

        for part_plan in plan.parts:
            part_ref = mint_stable_ref(self.seed_kind("part"), f"{self.seed}:part:{part_plan.ordinal}")
            part_turn_refs: list[str] = []
            for local_ordinal in range(1, part_plan.turn_target + 1):
                turn_ref = mint_stable_ref(
                    self.seed_kind("turn"),
                    f"{self.seed}:part:{part_plan.ordinal}:turn:{local_ordinal}",
                )
                part_turn_refs.append(turn_ref)
                turns.append(
                    PartTurnArtifact(
                        id=turn_ref,
                        part_ref=part_ref,
                        display_ordinal=local_ordinal,
                        cause=f"Part {part_plan.ordinal} receives pressure {local_ordinal}.",
                        change=f"Part {part_plan.ordinal} changes its available choice {local_ordinal}.",
                        progress_type=("information", "external", "relationship", "internal")[
                            (local_ordinal - 1) % 4
                        ],
                    )
                )
            parts.append(
                PartArcArtifact(
                    id=part_ref,
                    display_ordinal=part_plan.ordinal,
                    title=f"Part {part_plan.ordinal} Arc",
                    entry_state="The Part starts from an unstable family and professional state.",
                    promise="The investigation will force a different responsibility choice.",
                    climax="The local evidence chain makes the cost of action visible.",
                    exit_state="The Part ends with a changed relationship and evidence state.",
                    carried_questions=["Which responsibility can still be repaired?"],
                    turn_refs=part_turn_refs,
                )
            )

            part_volume_refs: list[str] = []
            volume_turn_groups = _balanced_groups(part_turn_refs, part_plan.volume_target)
            chapter_offset = 0
            for local_volume_ordinal, (turn_group, chapter_target) in enumerate(
                zip(volume_turn_groups, part_plan.volume_chapter_targets, strict=True),
                start=1,
            ):
                volume_ref = mint_stable_ref(
                    self.seed_kind("volume"),
                    f"{self.seed}:part:{part_plan.ordinal}:volume:{local_volume_ordinal}",
                )
                part_volume_refs.append(volume_ref)
                volume_refs.append(volume_ref)
                volumes.append(
                    VolumeUnitArtifact(
                        id=volume_ref,
                        part_ref=part_ref,
                        display_ordinal=len(volumes) + 1,
                        title=f"Part {part_plan.ordinal} Volume {local_volume_ordinal}",
                        promise="The volume narrows the next answer.",
                        conflict="The professional choice collides with family evidence.",
                        climax="The final local turn exposes an irreversible cost.",
                        climax_turn_ref=turn_group[-1],
                        closure="The next volume inherits a changed responsibility.",
                        turn_refs=turn_group,
                        cast_refs=["subject-protagonist"],
                        length_hint="long",
                    )
                )
                chapter_refs: list[str] = []
                for local_chapter_ordinal in range(1, chapter_target + 1):
                    chapter_number = part_plan.chapter_start + chapter_offset + local_chapter_ordinal - 1
                    chapter_ref = mint_stable_ref(
                        self.seed_kind("chapter"),
                        f"{self.seed}:chapter:{chapter_number}",
                    )
                    chapter_refs.append(chapter_ref)
                    all_chapters.append(
                        DetailChapterUnitArtifact(
                            id=chapter_ref,
                            detail_window_ref="window-pending",
                            volume_ref=volume_ref,
                            display_ordinal=chapter_number,
                            title=f"Chapter {chapter_number}",
                            target_characters=2_500,
                            turn_refs=[turn_group[(local_chapter_ordinal - 1) % len(turn_group)]],
                            purpose="The chapter turns a concrete decision into a changed state.",
                            pov_ref="subject-protagonist",
                            cast_refs=["subject-protagonist"],
                            scene_summaries=["A visible action changes the immediate evidence state."],
                            handoff="The next chapter inherits the final physical and relational state.",
                        )
                    )
                volume_chapter_order[volume_ref] = chapter_refs
                chapter_offset += chapter_target
            part_volume_order[part_ref] = part_volume_refs

        ordered_turn_refs = [turn.id for turn in turns]
        spine_root = StorySpineRootArtifact(
            book_promise="Professional duty and family loyalty cannot both remain unchanged.",
            book_milestones=[
                {"milestone": milestone, "turn_ref": ordered_turn_refs[min(index, len(ordered_turn_refs) - 1)]}
                for index, milestone in enumerate(
                    ("inciting", "commitment", "midpoint_reversal", "crisis", "climax", "aftermath")
                )
            ],
            part_refs=[part.id for part in parts],
            ending="The central choice is resolved with a public professional cost.",
            open_questions=["What can the family repair after the truth is public?"],
        )
        volume_root = VolumeArchitectureRootArtifact(
            part_refs=[part.id for part in parts],
            volume_refs=volume_refs,
            part_volume_order=part_volume_order,
        )

        windows: list[DetailWindowArtifact] = []
        chapter_order = [chapter_ref for refs in volume_chapter_order.values() for chapter_ref in refs]
        window_order: list[str] = []
        for start in range(0, len(all_chapters), plan.detail_window_target):
            window_chapters = all_chapters[start : start + plan.detail_window_target]
            window_ref = mint_stable_ref(self.seed_kind("window"), f"{self.seed}:window:{start}")
            window_order.append(window_ref)
            chapter_refs = [chapter.id for chapter in window_chapters]
            source_volume_refs = list(dict.fromkeys(chapter.volume_ref for chapter in window_chapters))
            source_part_refs = [
                part.id
                for part in parts
                if any(volume.part_ref == part.id for volume in volumes if volume.id in source_volume_refs)
            ]
            windows.append(
                DetailWindowArtifact(
                    id=window_ref,
                    start_chapter_ref=chapter_refs[0],
                    end_chapter_ref=chapter_refs[-1],
                    source_part_refs=source_part_refs,
                    source_volume_refs=source_volume_refs,
                    chapter_refs=chapter_refs,
                    entry_handoff="The window starts from the previous accepted state.",
                    exit_handoff="The window ends with a verified state handoff.",
                )
            )
            for chapter_index in range(start, start + len(window_chapters)):
                chapter = all_chapters[chapter_index]
                all_chapters[chapter_index] = chapter.model_copy(
                    update={"detail_window_ref": window_ref}
                )

        chapters = all_chapters
        detail_index = DetailPlanIndexArtifact(
            volume_refs=volume_refs,
            chapter_order=chapter_order,
            volume_chapter_order=volume_chapter_order,
            window_order=window_order,
        )
        return HierarchicalPlanningSkeleton(
            spine_root=spine_root,
            parts=parts,
            turns=turns,
            volume_root=volume_root,
            volumes=volumes,
            detail_index=detail_index,
            windows=windows,
            chapters=chapters,
        )

    @staticmethod
    def seed_kind(kind: str):
        return kind  # keep the helper explicit at the fake Provider boundary


def _balanced_groups(values: list[str], groups: int) -> list[list[str]]:
    base, remainder = divmod(len(values), groups)
    result: list[list[str]] = []
    offset = 0
    for index in range(groups):
        size = base + (1 if index < remainder else 0)
        result.append(values[offset : offset + size])
        offset += size
    return result


__all__ = ["FakeHierarchicalPlanningProvider", "HierarchicalPlanningSkeleton"]
