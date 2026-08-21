from __future__ import annotations

"""Cross-unit invariants for hierarchical planning aggregates."""

from collections.abc import Iterable, Sequence

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


def _unique(values: Iterable[str], label: str) -> list[str]:
    result = list(values)
    if len(result) != len(set(result)):
        raise ValueError(f"{label} refs must be unique")
    return result


def validate_spine_aggregate(
    root: StorySpineRootArtifact,
    parts: Sequence[PartArcArtifact],
    turns: Sequence[PartTurnArtifact],
) -> None:
    """Validate Part and local-turn coverage for the Spine aggregate."""

    part_ids = _unique((part.id for part in parts), "Part")
    if part_ids != root.part_refs:
        raise ValueError("Spine Part units must match the root Part order exactly")
    if [part.display_ordinal for part in parts] != list(range(1, len(parts) + 1)):
        raise ValueError("Spine Part display ordinals must project the root order")
    turn_by_id: dict[str, PartTurnArtifact] = {}
    for turn in turns:
        if turn.id in turn_by_id:
            raise ValueError("Spine turn units must be unique")
        turn_by_id[turn.id] = turn
    if any(binding.turn_ref not in turn_by_id for binding in root.book_milestones):
        raise ValueError("Book milestone references a missing turn unit")
    referenced_turns: list[str] = []
    for part in parts:
        for turn_ref in part.turn_refs:
            turn = turn_by_id.get(turn_ref)
            if turn is None:
                raise ValueError("Spine Part references a missing turn unit")
            if turn.part_ref != part.id:
                raise ValueError("Spine turn belongs to a different Part")
            referenced_turns.append(turn_ref)
        part_turns = sorted(
            (turn for turn in turns if turn.part_ref == part.id),
            key=lambda turn: turn.display_ordinal,
        )
        actual = [turn.id for turn in part_turns]
        ordinals = [turn.display_ordinal for turn in part_turns]
        if ordinals != list(range(1, len(part_turns) + 1)):
            raise ValueError("Spine Part turn display ordinals must project local order")
        if actual != part.turn_refs:
            raise ValueError("Spine Part turn coverage is missing, duplicated, or out of order")
    if set(referenced_turns) != set(turn_by_id) or len(referenced_turns) != len(turn_by_id):
        raise ValueError("Spine turn units contain an unreferenced or duplicated turn")


def validate_volume_aggregate(
    spine_root: StorySpineRootArtifact,
    root: VolumeArchitectureRootArtifact,
    parts: Sequence[PartArcArtifact],
    volumes: Sequence[VolumeUnitArtifact],
) -> None:
    """Validate volume partitioning and exact Part-turn coverage."""

    if root.part_refs != spine_root.part_refs:
        raise ValueError("Volume root must use the Spine Part order")
    part_ids = _unique((part.id for part in parts), "Part")
    if part_ids != root.part_refs:
        raise ValueError("Volume root references a missing, duplicate, or out-of-order Part")
    part_by_id = {part.id: part for part in parts}
    volume_ids = _unique((volume.id for volume in volumes), "Volume")
    if volume_ids != root.volume_refs:
        raise ValueError("Volume units must match the root volume order exactly")
    if [volume.display_ordinal for volume in volumes] != list(
        range(1, len(volumes) + 1)
    ):
        raise ValueError("Volume display ordinals must project the root order")
    volume_by_id = {volume.id: volume for volume in volumes}
    for part_ref in root.part_refs:
        ordered_volume_refs = root.part_volume_order[part_ref]
        for volume_ref in ordered_volume_refs:
            volume = volume_by_id[volume_ref]
            if volume.part_ref != part_ref:
                raise ValueError("Volume is assigned to a different Part")
        covered_turns = [
            turn_ref
            for volume_ref in ordered_volume_refs
            for turn_ref in volume_by_id[volume_ref].turn_refs
        ]
        if covered_turns != part_by_id[part_ref].turn_refs:
            raise ValueError("Volume turn coverage must match each Part turn order exactly")


def validate_detail_aggregate(
    index: DetailPlanIndexArtifact,
    windows: Sequence[DetailWindowArtifact],
    chapters: Sequence[DetailChapterUnitArtifact],
) -> None:
    """Validate rolling windows, chapter order, and known Volume ownership."""

    window_ids = _unique((window.id for window in windows), "Detail window")
    if window_ids != index.window_order:
        raise ValueError("Detail windows must match the index window order exactly")
    chapter_ids = _unique((chapter.id for chapter in chapters), "Detail chapter")
    if chapter_ids != index.chapter_order:
        raise ValueError("Detail chapters must match the index chapter order exactly")
    if [chapter.display_ordinal for chapter in chapters] != list(
        range(1, len(chapters) + 1)
    ):
        raise ValueError("Detail chapter display ordinals must project index order")
    window_by_id = {window.id: window for window in windows}
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    flattened = [chapter_ref for window in windows for chapter_ref in window.chapter_refs]
    if flattened != index.chapter_order:
        raise ValueError("Detail windows contain a gap, overlap, or out-of-order chapter")
    known_volumes = set(index.volume_refs)
    for window in windows:
        if any(volume_ref not in known_volumes for volume_ref in window.source_volume_refs):
            raise ValueError("Detail window references an unknown Volume")
        if any(chapter_ref not in chapter_by_id for chapter_ref in window.chapter_refs):
            raise ValueError("Detail window references a missing chapter unit")
    for chapter in chapters:
        if chapter.detail_window_ref not in window_by_id:
            raise ValueError("Detail chapter references an unknown window")
        if chapter.volume_ref not in known_volumes:
            raise ValueError("Detail chapter references an unknown Volume")
    for volume_ref in index.volume_refs:
        expected = index.volume_chapter_order[volume_ref]
        actual = [chapter.id for chapter in chapters if chapter.volume_ref == volume_ref]
        if actual != expected:
            raise ValueError("Detail chapter Volume coverage must match the index order")


__all__ = [
    "validate_detail_aggregate",
    "validate_spine_aggregate",
    "validate_volume_aggregate",
]
