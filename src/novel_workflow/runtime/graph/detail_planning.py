from __future__ import annotations

from dataclasses import dataclass
import math
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


@dataclass(frozen=True, slots=True)
class DetailLayoutTurnWindow:
    """A deterministic contiguous Spine slice and its chapter slots."""

    volume_ref: str
    volume_index: int
    volume_count: int
    window_index: int
    window_count: int
    turn_refs: tuple[str, ...]
    chapter_offset: int
    chapter_min: int
    chapter_target: int
    chapter_max: int
    volume_chapter_target: int
    book_chapter_min: int
    book_chapter_target: int
    book_chapter_max: int
    allocated_chapters: int
    remaining_volume_min: int
    remaining_volume_target: int
    remaining_volume_max: int

    @property
    def scope_ref(self) -> str:
        return f"{self.volume_ref}:turn-window-{self.window_index}"


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


def detail_layout_turn_windows(
    *,
    architecture: VolumeArchitectureArtifact,
    profile: NarrativeScaleProfile,
    spine_turn_count: int,
    volume_index: int,
    allocated_chapters: int,
    max_turns: int = 3,
) -> list[DetailLayoutTurnWindow]:
    """Partition one frozen volume into ordered, bounded Provider windows.

    The runtime owns both the turn boundaries and the number of chapter slots
    in each window. A Provider can only dramatize the supplied contiguous slice;
    it cannot move a chapter to an earlier or later Spine turn.
    """

    if max_turns < 1:
        raise ValueError("Detail layout turn window size must be positive")
    volume_window = detail_layout_volume_window(
        architecture=architecture,
        profile=profile,
        spine_turn_count=spine_turn_count,
        volume_index=volume_index,
        allocated_chapters=allocated_chapters,
    )
    volume = architecture.volumes[volume_index]
    turn_refs = list(volume.turn_refs)
    if not turn_refs:
        raise ValueError(f"Detail layout volume {volume.id} has no Spine turns")
    window_count = min(
        volume_window.chapter_target,
        max(1, math.ceil(len(turn_refs) / max_turns)),
    )
    turn_sizes = _partition_ordered(len(turn_refs), window_count)
    chapter_sizes = _allocate_window_chapters(
        volume_window.chapter_target,
        turn_sizes,
    )
    windows: list[DetailLayoutTurnWindow] = []
    turn_offset = 0
    chapter_offset = 0
    for index, (turn_size, chapter_size) in enumerate(
        zip(turn_sizes, chapter_sizes, strict=True),
        start=1,
    ):
        current_turns = tuple(turn_refs[turn_offset : turn_offset + turn_size])
        windows.append(
            DetailLayoutTurnWindow(
                volume_ref=volume_window.volume_ref,
                volume_index=volume_window.volume_index,
                volume_count=volume_window.volume_count,
                window_index=index,
                window_count=window_count,
                turn_refs=current_turns,
                chapter_offset=chapter_offset,
                chapter_min=chapter_size,
                chapter_target=chapter_size,
                chapter_max=chapter_size,
                volume_chapter_target=volume_window.chapter_target,
                book_chapter_min=volume_window.book_chapter_min,
                book_chapter_target=volume_window.book_chapter_target,
                book_chapter_max=volume_window.book_chapter_max,
                allocated_chapters=allocated_chapters + chapter_offset,
                remaining_volume_min=volume_window.remaining_volume_min,
                remaining_volume_target=volume_window.remaining_volume_target,
                remaining_volume_max=volume_window.remaining_volume_max,
            )
        )
        turn_offset += turn_size
        chapter_offset += chapter_size
    return windows


def _partition_ordered(total: int, parts: int) -> list[int]:
    if total < 1 or parts < 1 or parts > total:
        raise ValueError("Ordered partition must contain at least one item per part")
    base, remainder = divmod(total, parts)
    return [base + (1 if index < remainder else 0) for index in range(parts)]


def _allocate_window_chapters(total: int, turn_sizes: list[int]) -> list[int]:
    if total < len(turn_sizes):
        raise ValueError("Detail chapter target cannot cover its turn windows")
    base, remainder = divmod(total, len(turn_sizes))
    return [base + (1 if index < remainder else 0) for index in range(len(turn_sizes))]


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


def validate_detail_layout_turn_window_proposal(
    layout: DetailLayoutProposalBatch,
    *,
    volume: VolumeContract,
    spine: StorySpineArtifact,
    window: DetailLayoutTurnWindow,
) -> None:
    """Validate one bounded window before the next window is requested."""

    if layout.status != "sufficient":
        raise ValueError(
            "Detail narrative capacity is insufficient for the frozen turn window: "
            f"{layout.diagnosis.strip()}"
        )
    if [item.volume_ref for item in layout.volumes] != [volume.id]:
        raise ValueError(
            "Detail layout window must return exactly its current volume and no others"
        )
    volume_layout = layout.volumes[0]
    if len(volume_layout.chapters) != window.chapter_target:
        raise ValueError(
            f"Detail layout returned {len(volume_layout.chapters)} chapters for "
            f"{window.scope_ref}; the frozen window requires exactly "
            f"{window.chapter_target}"
        )
    _validate_chapter_sequence(
        chapters=volume_layout.chapters,
        expected_turns=list(window.turn_refs),
        known_turns={turn.id for turn in spine.turns},
        label=window.scope_ref,
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
    _validate_chapter_sequence(
        chapters=volume_layout.chapters,
        expected_turns=expected_turns,
        known_turns=known_turns,
        label=volume.id,
    )


def _validate_chapter_sequence(
    *,
    chapters: list[Any],
    expected_turns: list[str],
    known_turns: set[str],
    label: str,
) -> None:
    expected_positions = {
        turn_ref: index for index, turn_ref in enumerate(expected_turns)
    }
    encountered: list[str] = []
    previous_position = 0
    dramatic_jobs: list[str] = []
    for chapter in chapters:
        unknown = set(chapter.turn_refs) - known_turns
        outside_volume = set(chapter.turn_refs) - set(expected_turns)
        if unknown or outside_volume:
            raise ValueError(
                f"Detail layout chapter references turns outside {label}: "
                f"{sorted(unknown | outside_volume)}"
            )
        positions = [expected_positions[turn_ref] for turn_ref in chapter.turn_refs]
        if positions != list(range(positions[0], positions[-1] + 1)):
            raise ValueError("Detail layout chapter turn refs must be contiguous and ordered")
        if encountered and positions[0] < previous_position:
            raise ValueError("Detail layout cannot return to an earlier Spine turn")
        previous_position = positions[-1]
        for turn_ref in chapter.turn_refs:
            if turn_ref not in encountered:
                encountered.append(turn_ref)
        dramatic_jobs.append(chapter.dramatic_job.strip().casefold())

    if encountered != expected_turns:
        raise ValueError(
            f"Detail layout must cover every {label} turn in causal order"
        )
    if len(dramatic_jobs) != len(set(dramatic_jobs)):
        raise ValueError(
            f"Detail layout for {label} repeats a dramatic job instead of "
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
    "DetailLayoutTurnWindow",
    "DetailLayoutVolumeWindow",
    "bind_detail_artifact",
    "detail_layout_turn_windows",
    "detail_layout_volume_window",
    "validate_detail_layout_proposal",
    "validate_detail_layout_turn_window_proposal",
    "validate_detail_layout_volume_proposal",
]
