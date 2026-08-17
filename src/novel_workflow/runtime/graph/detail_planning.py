from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    DetailArtifact,
    DetailChapter,
    DetailLayoutProposalBatch,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
    VolumeContract,
)
from novel_workflow.workflows.narrative_scale import (
    ChapterNarrativeLoad,
    NarrativeScaleProfile,
    allocate_chapter_character_targets,
    chapter_count_range_for_spine,
    project_volume_scales,
)


@dataclass(frozen=True, slots=True)
class DetailLayoutVolumeWindow:
    """One volume's exact code-owned chapter allocation."""

    volume_ref: str
    volume_index: int
    volume_count: int
    chapter_min: int
    chapter_target: int
    chapter_max: int
    book_chapter_min: int
    book_chapter_target: int
    book_chapter_max: int
    allocated_chapters: int
    remaining_volume_min: int
    remaining_volume_target: int
    remaining_volume_max: int


def detail_layout_volume_window(
    *,
    architecture: VolumeArchitectureArtifact,
    profile: NarrativeScaleProfile,
    spine_turn_count: int,
    volume_index: int,
    allocated_chapters: int,
) -> DetailLayoutVolumeWindow:
    """Return one frozen volume allocation and reject sequence drift."""

    volumes = list(architecture.volumes)
    if not 0 <= volume_index < len(volumes):
        raise ValueError("Detail layout volume index is outside the architecture")
    if allocated_chapters < 0:
        raise ValueError("Allocated Detail chapter count cannot be negative")

    book_min, book_target, book_max = chapter_count_range_for_spine(
        profile,
        spine_turn_count,
    )
    projections = project_volume_scales(
        architecture,
        profile,
        spine_turn_count=spine_turn_count,
    )
    current = projections[volume_index]
    expected_allocated = sum(
        item.chapter_target for item in projections[:volume_index]
    )
    if allocated_chapters != expected_allocated:
        raise ValueError(
            "Earlier Detail volume output changed the frozen chapter allocation"
        )
    remaining = projections[volume_index + 1 :]
    remaining_target = sum(item.chapter_target for item in remaining)
    return DetailLayoutVolumeWindow(
        volume_ref=current.volume_ref,
        volume_index=volume_index,
        volume_count=len(volumes),
        chapter_min=current.chapter_target,
        chapter_target=current.chapter_target,
        chapter_max=current.chapter_target,
        book_chapter_min=book_min,
        book_chapter_target=book_target,
        book_chapter_max=book_max,
        allocated_chapters=allocated_chapters,
        remaining_volume_min=remaining_target,
        remaining_volume_target=remaining_target,
        remaining_volume_max=remaining_target,
    )


def validate_detail_layout_volume_proposal(
    layout: DetailLayoutProposalBatch,
    *,
    volume: VolumeContract,
    spine: StorySpineArtifact,
    chapter_min: int,
    chapter_target: int,
    chapter_max: int,
) -> None:
    """Validate one sequential Provider result before it affects later windows."""

    if layout.status != "sufficient":
        raise ValueError(
            "Detail narrative capacity is insufficient for the frozen volume: "
            f"{layout.diagnosis.strip()}"
        )
    if [item.volume_ref for item in layout.volumes] != [volume.id]:
        raise ValueError(
            "Detail layout call must return exactly its current volume and no others"
        )
    chapter_count = len(layout.volumes[0].chapters)
    if chapter_count != chapter_target:
        raise ValueError(
            f"Detail layout returned {chapter_count} chapters for {volume.id}; "
            f"the dynamically selected chapter-slot count is {chapter_target}"
        )
    _validate_volume_layout(
        volume=volume,
        volume_layout=layout.volumes[0],
        known_turns={turn.id for turn in spine.turns},
        chapter_min=chapter_min,
        chapter_max=chapter_max,
    )


def validate_detail_layout_proposal(
    layout: DetailLayoutProposalBatch,
    *,
    architecture: VolumeArchitectureArtifact,
    spine: StorySpineArtifact,
    profile: NarrativeScaleProfile,
) -> None:
    """Validate the creative turn-to-slot layout against frozen story capacity."""

    expected_volume_refs = [volume.id for volume in architecture.volumes]
    actual_volume_refs = [volume.volume_ref for volume in layout.volumes]
    if actual_volume_refs != expected_volume_refs:
        raise ValueError(
            "Detail layout must cover committed volumes exactly once and in order"
        )

    projection_by_ref = {
        item.volume_ref: item
        for item in project_volume_scales(
            architecture,
            profile,
            spine_turn_count=len(spine.turns),
        )
    }
    known_turns = {turn.id for turn in spine.turns}
    total_chapters = 0
    for volume, volume_layout in zip(
        architecture.volumes,
        layout.volumes,
        strict=True,
    ):
        projection = projection_by_ref[volume.id]
        _validate_volume_layout(
            volume=volume,
            volume_layout=volume_layout,
            known_turns=known_turns,
            chapter_min=projection.chapter_min,
            chapter_max=projection.chapter_max,
        )
        chapter_count = len(volume_layout.chapters)
        if chapter_count != projection.chapter_target:
            raise ValueError(
                f"Detail layout returned {chapter_count} chapters for {volume.id}; "
                f"the frozen allocation requires exactly {projection.chapter_target}"
            )
        total_chapters += chapter_count

    chapter_min, chapter_target, chapter_max = chapter_count_range_for_spine(
        profile,
        len(spine.turns),
    )
    if total_chapters != chapter_target:
        raise ValueError(
            f"Detail layout returned {total_chapters} chapters; the frozen book "
            f"target is {chapter_target} (feasible capacity {chapter_min}-{chapter_max})"
        )


def _validate_volume_layout(
    *,
    volume: VolumeContract,
    volume_layout: Any,
    known_turns: set[str],
    chapter_min: int,
    chapter_max: int,
) -> None:
    chapter_count = len(volume_layout.chapters)
    if not chapter_min <= chapter_count <= chapter_max:
        raise ValueError(
            f"Detail layout returned {chapter_count} chapters for {volume.id}; "
            f"its current narrative capacity range is {chapter_min}-{chapter_max}"
        )

    expected_turns = list(volume.turn_refs)
    expected_positions = {
        turn_ref: index for index, turn_ref in enumerate(expected_turns)
    }
    encountered: list[str] = []
    previous_position = 0
    dramatic_jobs: list[str] = []
    for chapter in volume_layout.chapters:
        unknown = set(chapter.turn_refs) - known_turns
        outside_volume = set(chapter.turn_refs) - set(expected_turns)
        if unknown or outside_volume:
            raise ValueError(
                f"Detail layout chapter references turns outside {volume.id}: "
                f"{sorted(unknown | outside_volume)}"
            )
        positions = [expected_positions[turn_ref] for turn_ref in chapter.turn_refs]
        if positions != list(range(positions[0], positions[-1] + 1)):
            raise ValueError(
                "Detail layout chapter turn refs must be contiguous and ordered"
            )
        if encountered and positions[0] < previous_position:
            raise ValueError("Detail layout cannot return to an earlier Spine turn")
        previous_position = positions[-1]
        for turn_ref in chapter.turn_refs:
            if turn_ref not in encountered:
                encountered.append(turn_ref)
        dramatic_jobs.append(chapter.dramatic_job.strip().casefold())

    if encountered != expected_turns:
        raise ValueError(
            f"Detail layout must cover every {volume.id} turn in causal order"
        )
    if len(dramatic_jobs) != len(set(dramatic_jobs)):
        raise ValueError(
            f"Detail layout for {volume.id} repeats a dramatic job instead of "
            "adding a chapter change"
        )


def bind_detail_artifact(
    payload: dict[str, Any],
    profile: NarrativeScaleProfile,
    layout: DetailLayoutProposalBatch,
) -> dict[str, Any]:
    """Bind deterministic prose budgets after all chapter scripts exist."""

    raw_chapters = payload.get("chapters")
    if not isinstance(raw_chapters, list):
        raise ValueError("Detail aggregation must return a chapter list")
    layout_chapters = [
        chapter
        for volume in layout.volumes
        for chapter in volume.chapters
    ]
    if len(raw_chapters) != len(layout_chapters):
        raise ValueError("Detail aggregation does not match the frozen chapter layout")

    loads = [
        _chapter_narrative_load(chapter, length_hint=layout_chapters[index].length_hint)
        for index, chapter in enumerate(raw_chapters)
    ]
    targets = allocate_chapter_character_targets(profile, loads)
    chapters = [
        DetailChapter.model_validate(
            {
                **chapter,
                "target_characters": targets[index] if targets else None,
            }
        )
        for index, chapter in enumerate(raw_chapters)
    ]
    return DetailArtifact(chapters=chapters).model_dump(mode="json")


def _chapter_narrative_load(
    chapter: dict[str, Any],
    *,
    length_hint: str,
) -> ChapterNarrativeLoad:
    scenes = chapter.get("scenes") or []
    places = {
        str(scene.get("place") or "").strip().casefold()
        for scene in scenes
        if isinstance(scene, dict) and str(scene.get("place") or "").strip()
    }
    return ChapterNarrativeLoad(
        scene_count=len(scenes),
        active_cast_count=len(chapter.get("cast_ids") or []),
        turn_count=len(chapter.get("turn_refs") or []),
        distinct_place_count=len(places),
        length_hint=length_hint,
    )


__all__ = [
    "DetailLayoutVolumeWindow",
    "bind_detail_artifact",
    "detail_layout_volume_window",
    "validate_detail_layout_proposal",
    "validate_detail_layout_volume_proposal",
]
