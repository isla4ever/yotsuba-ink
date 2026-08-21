from __future__ import annotations

import math
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.output_contracts.artifacts_vnext import (
    LengthEnvelope,
    VolumeArchitectureArtifact,
)


MINIMUM_SPINE_TURNS = 3


class NarrativeCapacityPolicy(BaseModel):
    """Frozen editorial capacity ranges used to derive book structure."""

    model_config = ConfigDict(extra="forbid")

    chapter_characters_min: int = Field(default=2_000, ge=1)
    chapter_characters_preferred: int = Field(default=2_500, ge=1)
    chapter_characters_max: int = Field(default=3_000, ge=1)
    volume_chapters_min: int = Field(default=8, ge=1)
    volume_chapters_preferred: int = Field(default=14, ge=1)
    volume_chapters_max: int = Field(default=20, ge=1)
    part_volumes_min: int = Field(default=3, ge=1)
    part_volumes_preferred: int = Field(default=5, ge=1)
    part_volumes_max: int = Field(default=8, ge=1)
    detail_window_chapters_min: int = Field(default=12, ge=1)
    detail_window_chapters_preferred: int = Field(default=24, ge=1)
    detail_window_chapters_max: int = Field(default=40, ge=1)
    scene_characters_min: int = Field(default=500, ge=1)
    scene_characters_max: int = Field(default=2_400, ge=1)
    spine_chapters_per_turn_min: float = Field(default=1.50, gt=0, le=10)
    spine_chapters_per_turn_preferred: float = Field(default=2.00, gt=0, le=10)
    spine_chapters_per_turn_max: float = Field(default=2.50, gt=0, le=10)
    cast_chapters_per_subject_min: int = Field(default=4, ge=1)
    cast_chapters_per_subject_preferred: int = Field(default=6, ge=1)
    cast_subjects_recommended_min: int = Field(default=3, ge=1)
    cast_subjects_hard_max: int = Field(default=16, ge=1)
    cast_subject_burst_allowance: int = Field(default=1, ge=0, le=8)
    book_target_tolerance_percent: int = Field(default=10, ge=0, le=50)
    adjacent_chapter_delta_percent: int = Field(default=15, ge=1, le=50)

    @model_validator(mode="after")
    def validate_ranges(self) -> "NarrativeCapacityPolicy":
        if not (
            self.chapter_characters_min
            <= self.chapter_characters_preferred
            <= self.chapter_characters_max
        ):
            raise ValueError("Preferred chapter length must fit the chapter length range")
        if self.scene_characters_min > self.scene_characters_max:
            raise ValueError("Scene length minimum must not exceed the maximum")
        if not (
            self.volume_chapters_min
            <= self.volume_chapters_preferred
            <= self.volume_chapters_max
        ):
            raise ValueError("Preferred volume size must fit the volume chapter range")
        if not (
            self.part_volumes_min
            <= self.part_volumes_preferred
            <= self.part_volumes_max
        ):
            raise ValueError("Preferred Part size must fit the Part volume range")
        if not (
            self.detail_window_chapters_min
            <= self.detail_window_chapters_preferred
            <= self.detail_window_chapters_max
        ):
            raise ValueError("Preferred Detail window size must fit its chapter range")
        if not (
            self.spine_chapters_per_turn_min
            <= self.spine_chapters_per_turn_preferred
            <= self.spine_chapters_per_turn_max
        ):
            raise ValueError("Preferred Spine density must fit the chapters-per-turn range")
        if self.cast_chapters_per_subject_min > self.cast_chapters_per_subject_preferred:
            raise ValueError("Preferred cast density must not exceed the hard cast density")
        if self.cast_subjects_recommended_min > self.cast_subjects_hard_max:
            raise ValueError("Recommended cast minimum must not exceed the hard cast maximum")
        return self


class NarrativeScaleProfile(BaseModel):
    """Deterministic capacity guidance derived from user length intent.

    It never assigns volume boundaries, character quotas, or chapter ids.
    """

    model_config = ConfigDict(extra="forbid")

    word_target_soft: int = Field(ge=1, le=10_000_000)
    detail_segment_char_cap: int = Field(default=30_000, ge=4_000, le=500_000)
    volume_candidate_cap: int = Field(default=12, ge=1, le=50)
    json_item_caps: dict[str, int] = Field(default_factory=dict)
    capacity_policy: NarrativeCapacityPolicy = Field(default_factory=NarrativeCapacityPolicy)
    # Deep-mode user customization. Volume count is intentionally absent:
    # accepted Spine closure, not a numeric override, owns volume boundaries.
    turn_target_override: Optional[int] = Field(
        default=None,
        ge=MINIMUM_SPINE_TURNS,
        le=120,
    )

class _NarrativeScaleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_envelope: LengthEnvelope
    scale_overrides: Optional["ScaleOverrides"] = None


class ScaleOverrides(BaseModel):
    """User-chosen Spine density surfaced only by deep mode."""

    model_config = ConfigDict(extra="forbid")

    turn_target: Optional[int] = Field(
        default=None,
        ge=MINIMUM_SPINE_TURNS,
        le=120,
    )


class NarrativeScalePlan(BaseModel):
    """Code-owned structural scale derived from the user's length intent."""

    model_config = ConfigDict(extra="forbid")

    chapter_target: int = Field(ge=1)
    chapter_min: int = Field(ge=1)
    chapter_max: int = Field(ge=1)
    volume_target: int = Field(ge=1)
    volume_min: int = Field(ge=1)
    volume_max: int = Field(ge=1)
    turn_target: int = Field(ge=MINIMUM_SPINE_TURNS)
    turn_min: int = Field(ge=MINIMUM_SPINE_TURNS)
    turn_max: int = Field(ge=MINIMUM_SPINE_TURNS)
    scenes_per_chapter_min: int = Field(ge=1)
    scenes_per_chapter_max: int = Field(ge=1)
    cast_recommended_min: int = Field(ge=1)
    cast_recommended_max: int = Field(ge=1)
    cast_hard_max: int = Field(ge=1)
    user_locked: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self) -> "NarrativeScalePlan":
        for label, low, target, high in (
            ("chapter", self.chapter_min, self.chapter_target, self.chapter_max),
            ("volume", self.volume_min, self.volume_target, self.volume_max),
            ("turn", self.turn_min, self.turn_target, self.turn_max),
        ):
            if not low <= target <= high:
                raise ValueError(f"Scale plan {label} target must fit its range")
        if self.scenes_per_chapter_min > self.scenes_per_chapter_max:
            raise ValueError("Scale plan scene minimum must not exceed the maximum")
        if not self.cast_recommended_min <= self.cast_recommended_max <= self.cast_hard_max:
            raise ValueError("Scale plan cast guidance must fit its hard capacity")
        return self


def plan_narrative_scale(
    profile: NarrativeScaleProfile,
    quality_mode: str = "balanced",
) -> NarrativeScalePlan:
    """Derive chapter capacity and Spine density from the length envelope.

    Chapter and volume targets are deterministic numeric authority. Providers
    may shape turns, boundaries, titles, and dramatic content, but may not alter
    either target. Only an explicit deep-mode override may lock one turn count
    inside the dynamically derived Spine range.
    """

    chapter_min, chapters, chapter_max = chapter_count_range(profile)
    volume_min, volume_target, volume_max = volume_count_range(profile)
    scenes_per_chapter_min, scenes_per_chapter_max = detail_scene_count_range(profile)

    policy = profile.capacity_policy
    # Chapter count is already frozen by code. The Spine range must therefore
    # carry that exact target, not merely intersect an unused feasible range.
    turn_min = max(
        MINIMUM_SPINE_TURNS,
        math.ceil(chapters / policy.spine_chapters_per_turn_max),
    )
    turn_target = max(
        turn_min,
        round(chapters / policy.spine_chapters_per_turn_preferred),
    )
    turn_max = max(
        turn_target,
        math.floor(chapters / policy.spine_chapters_per_turn_min),
    )
    if turn_max > 120:
        raise ValueError(
            "Book length requires more than the 120-turn Spine contract can carry"
        )

    user_locked: list[str] = []
    if quality_mode == "deep":
        if profile.turn_target_override is not None:
            if not turn_min <= profile.turn_target_override <= turn_max:
                raise ValueError(
                    "Spine turn override must fit the range derived from chapter capacity: "
                    f"{turn_min}-{turn_max}"
                )
            turn_target = profile.turn_target_override
            turn_min = turn_max = turn_target
            user_locked.append("turn_target")
    cast_recommended_min, cast_recommended_max, cast_hard_max = cast_subject_count_range(
        profile
    )
    return NarrativeScalePlan(
        chapter_target=chapters,
        chapter_min=chapter_min,
        chapter_max=chapter_max,
        volume_target=volume_target,
        volume_min=volume_min,
        volume_max=volume_max,
        turn_target=turn_target,
        turn_min=turn_min,
        turn_max=turn_max,
        scenes_per_chapter_min=scenes_per_chapter_min,
        scenes_per_chapter_max=scenes_per_chapter_max,
        cast_recommended_min=cast_recommended_min,
        cast_recommended_max=cast_recommended_max,
        cast_hard_max=cast_hard_max,
        user_locked=user_locked,
    )


def spine_milestone_positions(turn_count: int) -> dict[str, int]:
    """Project code-owned structural anchors onto an exact Spine size."""

    if isinstance(turn_count, bool) or not isinstance(turn_count, int) or turn_count < 1:
        raise ValueError("Spine turn count must be a positive integer")
    if turn_count < 6:
        return {
            "inciting": 1,
            "commitment": 1,
            "midpoint_reversal": min(2, turn_count),
            "crisis": max(1, turn_count - 1),
            "climax": turn_count,
            "aftermath": turn_count,
        }

    def position(start: float, end: float, preferred: float) -> int:
        minimum = math.ceil(turn_count * start)
        maximum = math.floor(turn_count * end)
        return min(maximum, max(minimum, round(turn_count * preferred)))

    return {
        "inciting": 1,
        "commitment": position(0.20, 0.30, 0.25),
        "midpoint_reversal": position(0.40, 0.60, 0.50),
        "crisis": position(0.65, 0.80, 0.72),
        "climax": turn_count - 1,
        "aftermath": turn_count,
    }


def chapter_count_range(profile: NarrativeScaleProfile) -> tuple[int, int, int]:
    """Derive a reasonable chapter-count range from the frozen prose policy."""

    total = profile.word_target_soft
    policy = profile.capacity_policy
    minimum = max(1, math.ceil(total / policy.chapter_characters_max))
    maximum = max(minimum, total // policy.chapter_characters_min)
    target = min(
        maximum,
        max(minimum, round(total / policy.chapter_characters_preferred)),
    )
    return minimum, target, maximum


def volume_count_range(profile: NarrativeScaleProfile) -> tuple[int, int, int]:
    """Derive the exact volume target from the code-owned chapter target."""

    chapter_target = _plan_chapter_target(profile)
    policy = profile.capacity_policy
    if chapter_target < policy.volume_chapters_min:
        return 1, 1, 1
    minimum = max(1, math.ceil(chapter_target / policy.volume_chapters_max))
    maximum = max(minimum, chapter_target // policy.volume_chapters_min)
    target = min(
        maximum,
        max(minimum, round(chapter_target / policy.volume_chapters_preferred)),
    )
    return minimum, target, maximum


def cast_subject_count_range(profile: NarrativeScaleProfile) -> tuple[int, int, int]:
    """Project how many recurring named subjects this book can develop.

    Story semantics still decide the actual role demands. This range only
    prevents a long Spine from personifying every procedure or one-off task.
    """

    chapters = _plan_chapter_target(profile)
    policy = profile.capacity_policy
    hard_max = min(
        policy.cast_subjects_hard_max,
        max(
            1,
            math.ceil(chapters / policy.cast_chapters_per_subject_min)
            + policy.cast_subject_burst_allowance,
        ),
    )
    recommended_min = min(policy.cast_subjects_recommended_min, hard_max)
    recommended_max = min(
        hard_max,
        max(
            recommended_min,
            math.ceil(chapters / policy.cast_chapters_per_subject_preferred),
        ),
    )
    return recommended_min, recommended_max, hard_max


def chapter_count_range_for_spine(
    profile: NarrativeScaleProfile,
    spine_turn_count: int,
) -> tuple[int, int, int]:
    """Check accepted Spine capacity without changing the frozen chapter target."""

    if (
        isinstance(spine_turn_count, bool)
        or not isinstance(spine_turn_count, int)
        or spine_turn_count < 1
    ):
        raise ValueError("Accepted Spine turn count must be a positive integer")
    base_minimum, base_target, base_maximum = chapter_count_range(profile)
    policy = profile.capacity_policy
    minimum_grammar_chapters = math.ceil(
        MINIMUM_SPINE_TURNS * policy.spine_chapters_per_turn_min
    )
    if (
        spine_turn_count == MINIMUM_SPINE_TURNS
        and base_maximum < minimum_grammar_chapters
    ):
        # At micro-fiction scale the three-turn floor is structural grammar,
        # not a long-form density quota. Several turns may share one chapter.
        return base_minimum, base_target, base_maximum
    density_minimum = math.ceil(
        spine_turn_count * policy.spine_chapters_per_turn_min
    )
    density_maximum = math.floor(
        spine_turn_count * policy.spine_chapters_per_turn_max
    )
    minimum = max(base_minimum, density_minimum)
    maximum = min(base_maximum, density_maximum)
    if minimum > maximum:
        raise ValueError(
            "Accepted Spine density cannot carry the frozen book-length capacity; "
            "regenerate Spine instead of padding Detail chapters"
        )
    if not minimum <= base_target <= maximum:
        raise ValueError(
            "Accepted Spine density cannot carry the frozen chapter target; "
            "regenerate Spine instead of changing the book's chapter count"
        )
    return minimum, base_target, maximum


def project_turn_chapter_window(
    *,
    turn_number: int,
    turn_count: int,
    chapter_count: int,
) -> tuple[int, int]:
    """Project one Spine position into a dynamic safe chapter window.

    The role-demand call owns the creative decision about the first turn that
    needs a subject on stage. Once that turn is frozen, its chapter envelope is
    a scale projection rather than another Provider-authored decision.
    """

    if isinstance(turn_number, bool) or not isinstance(turn_number, int):
        raise ValueError("Turn number must be an integer")
    if isinstance(turn_count, bool) or not isinstance(turn_count, int):
        raise ValueError("Turn count must be an integer")
    if isinstance(chapter_count, bool) or not isinstance(chapter_count, int):
        raise ValueError("Chapter count must be an integer")
    if turn_count < 1 or chapter_count < 1 or not 1 <= turn_number <= turn_count:
        raise ValueError("Turn-to-chapter projection inputs are out of range")

    if turn_count == 1:
        center = 1
    else:
        center = round(
            1 + (turn_number - 1) * (chapter_count - 1) / (turn_count - 1)
        )
    slack = max(1, math.ceil(chapter_count / turn_count))
    return max(1, center - slack), min(chapter_count, center + slack)


def _plan_chapter_target(profile: NarrativeScaleProfile) -> int:
    return chapter_count_range(profile)[1]


class VolumeScaleProjection(BaseModel):
    """Rebuildable chapter capacity range for one accepted volume contract."""

    model_config = ConfigDict(extra="forbid")

    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    chapter_min: int = Field(ge=1, le=10_000)
    chapter_target: int = Field(ge=1, le=10_000)
    chapter_max: int = Field(ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_range(self) -> "VolumeScaleProjection":
        if not self.chapter_min <= self.chapter_target <= self.chapter_max:
            raise ValueError("Volume chapter target must fit its capacity range")
        return self


class ChapterTargetBand(BaseModel):
    """Editorial prose capacity shown to Detail before chapter loads are known."""

    model_config = ConfigDict(extra="forbid")

    preferred_characters: int = Field(ge=1)
    min_characters: int = Field(ge=1)
    max_characters: int = Field(ge=1)
    max_adjacent_delta: int = Field(ge=1)
    counting_rule: Literal["non_whitespace_characters"] = "non_whitespace_characters"

    @model_validator(mode="after")
    def validate_band(self) -> "ChapterTargetBand":
        if not self.min_characters <= self.preferred_characters <= self.max_characters:
            raise ValueError("Preferred chapter length must fit its editorial band")
        return self


class DetailChapterBeatSlot(BaseModel):
    """Provider-proposed chapter responsibility frozen before Detail expansion."""

    model_config = ConfigDict(extra="forbid")

    chapter_offset: int = Field(ge=1)
    turn_refs: list[str] = Field(min_length=1)
    dramatic_job: str = Field(min_length=1, max_length=400)
    length_hint: Literal["compact", "standard", "expansive"]


class ChapterNarrativeLoad(BaseModel):
    """Deterministic evidence used to allocate prose without one magic signal."""

    model_config = ConfigDict(extra="forbid")

    scene_count: int = Field(ge=1)
    active_cast_count: int = Field(ge=1)
    turn_count: int = Field(ge=1)
    distinct_place_count: int = Field(ge=1)
    length_hint: Literal["compact", "standard", "expansive"]


class DetailScaleProjection(BaseModel):
    """One capacity-safe narrative segment inside a volume projection."""

    model_config = ConfigDict(extra="forbid")

    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    segment_ref: str = Field(pattern=r"^volume-[1-9][0-9]*\.segment-[1-9][0-9]*$")
    segment_index: int = Field(ge=1)
    segment_count: int = Field(ge=1)
    chapter_target: int = Field(ge=1)
    chapter_beats: list[DetailChapterBeatSlot] = Field(min_length=1)
    # The segment owns an exact chapter count and a shared prose capacity. This
    # prevents one unit from returning two overloaded chapters while another
    # returns six thin chapters for the same volume.
    chapter_target_band: Optional[ChapterTargetBand] = None
    scenes_per_chapter_min: int = Field(ge=1)
    scenes_per_chapter_max: int = Field(ge=1)
    is_final_volume: bool = False
    # Absolute position of this segment's first chapter in the book. Without
    # it a segment cannot tell which part of a stage-wide revision note is its
    # own, and every segment rewrites the opening.
    chapter_number_start: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_segment(self) -> "DetailScaleProjection":
        if self.segment_index > self.segment_count:
            raise ValueError("Detail segment index exceeds segment count")
        if len(self.chapter_beats) != self.chapter_target:
            raise ValueError("Detail chapter beat count must match the segment chapter target")
        if [item.chapter_offset for item in self.chapter_beats] != list(
            range(1, self.chapter_target + 1)
        ):
            raise ValueError("Detail chapter beat offsets must be continuous and ordered")
        if self.scenes_per_chapter_min > self.scenes_per_chapter_max:
            raise ValueError("Detail scene minimum must not exceed the maximum")
        return self


class ChapterLengthContract(BaseModel):
    """Deterministic prose acceptance envelope for one chapter."""

    model_config = ConfigDict(extra="forbid")

    target_characters: int = Field(ge=1)
    min_characters: int = Field(ge=1)
    max_characters: int = Field(ge=1)
    scene_count: int = Field(ge=1)
    characters_per_scene_target: int = Field(ge=1)
    tolerance_percent: int = Field(ge=1, le=50)
    counting_rule: Literal["non_whitespace_characters"] = "non_whitespace_characters"

    @model_validator(mode="after")
    def validate_envelope(self) -> "ChapterLengthContract":
        if not self.min_characters <= self.target_characters <= self.max_characters:
            raise ValueError("Chapter length target must fit its acceptance envelope")
        return self


def scale_profile_from_inputs(inputs: dict[str, Any]) -> NarrativeScaleProfile:
    if not isinstance(inputs, dict):
        raise TypeError("Narrative scale inputs must be an object")
    parsed = _NarrativeScaleInput.model_validate(inputs)
    envelope = parsed.length_envelope
    overrides = parsed.scale_overrides or ScaleOverrides()
    return NarrativeScaleProfile(
        word_target_soft=envelope.word_target_soft,
        turn_target_override=overrides.turn_target,
    )


def project_volume_scales(
    architecture: VolumeArchitectureArtifact,
    profile: NarrativeScaleProfile,
    *,
    spine_turn_count: int,
) -> list[VolumeScaleProjection]:
    """Allocate the exact chapter total across code-approved volume boundaries."""

    volumes = list(architecture.volumes)
    if not volumes:
        raise ValueError("Volume scale projection requires accepted volume contracts")
    plan = plan_narrative_scale(profile)
    if len(volumes) != plan.volume_target:
        raise ValueError(
            f"Volume architecture contains {len(volumes)} volumes; the frozen scale "
            f"requires exactly {plan.volume_target}"
        )
    referenced_turn_count = len(
        {turn_ref for volume in volumes for turn_ref in volume.turn_refs}
    )
    if referenced_turn_count != spine_turn_count:
        raise ValueError("Volume architecture must cover every accepted Spine turn exactly")
    _, total_target, _ = chapter_count_range_for_spine(
        profile,
        spine_turn_count,
    )
    if len(volumes) == 1:
        return [
            VolumeScaleProjection(
                volume_ref=volumes[0].id,
                chapter_min=total_target,
                chapter_target=total_target,
                chapter_max=total_target,
            )
        ]
    policy = profile.capacity_policy
    structural_weights = [float(len(volume.turn_refs)) for volume in volumes]
    minimums = [
        max(
            policy.volume_chapters_min,
            math.ceil(len(volume.turn_refs) * policy.spine_chapters_per_turn_min),
        )
        for volume in volumes
    ]
    maximums = [
        min(
            policy.volume_chapters_max,
            math.floor(len(volume.turn_refs) * policy.spine_chapters_per_turn_max),
        )
        for volume in volumes
    ]
    if any(low > high for low, high in zip(minimums, maximums, strict=True)):
        raise ValueError(
            "Accepted volume boundaries cannot carry the editorial chapter range; "
            "regenerate Volumes with more balanced Spine turn coverage"
        )
    targets = _bounded_weighted_allocation(
        total_target,
        structural_weights,
        minimums=minimums,
        maximums=maximums,
    )
    return [
        VolumeScaleProjection(
            volume_ref=volume.id,
            chapter_min=minimum_value,
            chapter_target=target,
            chapter_max=maximum_value,
        )
        for volume, minimum_value, target, maximum_value in zip(
            volumes,
            minimums,
            targets,
            maximums,
            strict=True,
        )
    ]
def _bounded_weighted_allocation(
    total: int,
    weights: list[float],
    *,
    minimums: list[int],
    maximums: list[int],
) -> list[int]:
    """Allocate an exact total by narrative load without breaking volume capacity."""

    if not weights:
        raise ValueError("Chapter allocation requires at least one volume weight")
    if len(minimums) != len(weights) or len(maximums) != len(weights):
        raise ValueError("Chapter allocation bounds must match the volume count")
    if total < sum(minimums) or total > sum(maximums):
        raise ValueError(
            "Accepted volume count cannot carry the chapter target inside the volume capacity range"
        )

    values = list(minimums)
    remaining = total - sum(values)
    while remaining:
        candidates = [
            index for index, value in enumerate(values) if value < maximums[index]
        ]
        if not candidates:
            raise ValueError("Bounded volume allocation could not preserve the chapter target")
        index = max(
            candidates,
            key=lambda item: (weights[item] / (values[item] + 1), weights[item], -item),
        )
        values[index] += 1
        remaining -= 1
    return values


def chapter_target_band(
    profile: NarrativeScaleProfile,
    chapter_count: int | None = None,
) -> ChapterTargetBand | None:
    """Return the editorial prose band for a proposed or accepted chapter count.

    The chapter count is checked against whole-book capacity, but it never
    redefines what a well-sized chapter is. The preferred/min/max values remain
    the frozen editorial policy; the book target is reconciled only after
    Detail exposes each chapter's actual narrative load.
    """

    if profile.word_target_soft is None:
        return None
    resolved_count = chapter_count or _plan_chapter_target(profile)
    chapter_min, _, chapter_max = chapter_count_range(profile)
    if not chapter_min <= resolved_count <= chapter_max:
        raise ValueError(
            "Detail chapter count must fit the range derived from the book target "
            f"and chapter capacity: {chapter_min}-{chapter_max}"
        )
    policy = profile.capacity_policy
    return ChapterTargetBand(
        preferred_characters=policy.chapter_characters_preferred,
        min_characters=policy.chapter_characters_min,
        max_characters=policy.chapter_characters_max,
        max_adjacent_delta=max(
            1,
            math.ceil(
                policy.chapter_characters_preferred
                * policy.adjacent_chapter_delta_percent
                / 100
            ),
        ),
    )


def detail_scene_count_range(
    profile: NarrativeScaleProfile,
    chapter_count: int | None = None,
) -> tuple[int, int]:
    """Derive scene capacity for the proposed whole-book chapter count.

    The editorial chapter band decides the feasible chapter-count range first.
    Once DetailLayout chooses a count inside that range, the resulting book
    budget center narrows scene capacity so every allowed scene count can still
    carry a viable chapter. The lower bound uses the same 50% incomplete-prose
    floor as the Text gate; it must not turn the preferred chapter length into
    a hidden Detail blocker. This is a feasibility projection, not a fixed scene
    quota and not a new chapter-length policy.
    """

    policy = profile.capacity_policy
    band = chapter_target_band(profile, chapter_count)
    chapter_center = _chapter_allocation_center(profile, chapter_count, band)
    if chapter_center is None:
        chapter_minimum = policy.chapter_characters_min
        chapter_maximum = policy.chapter_characters_max
    else:
        chapter_minimum = chapter_maximum = chapter_center
    viable_chapter_minimum = math.ceil(chapter_minimum * 50 / 100)
    minimum = max(
        1,
        math.ceil(viable_chapter_minimum / policy.scene_characters_max),
    )
    maximum = max(
        minimum,
        math.floor(chapter_maximum / policy.scene_characters_min),
    )
    return minimum, maximum


def allocate_chapter_character_targets(
    profile: NarrativeScaleProfile,
    chapter_loads: list[ChapterNarrativeLoad],
) -> list[int]:
    """Allocate chapter targets after Detail exposes narrative load.

    Layout intent, scenes, active cast, turn coverage, and place changes all
    contribute small bounded adjustments. No single field can inflate a
    chapter. The selected total stays inside the whole-book soft envelope while
    preserving the editorial preferred chapter length whenever possible.
    """

    if profile.word_target_soft is None:
        return []
    chapter_count = len(chapter_loads)
    chapter_min, chapter_target, chapter_max = chapter_count_range(profile)
    if chapter_count != chapter_target:
        raise ValueError(
            f"Detail returned {chapter_count} chapters; the frozen scale requires "
            f"exactly {chapter_target} (feasible capacity {chapter_min}-{chapter_max})"
        )
    band = chapter_target_band(profile, chapter_count)
    if band is None:
        return []
    preferred_book_budget = _book_character_budget(profile, chapter_count, band)
    allocation_minimum, allocation_maximum = _chapter_allocation_bounds(
        profile,
        chapter_count,
        band,
    )

    minimums = [
        max(
            allocation_minimum,
            load.scene_count * profile.capacity_policy.scene_characters_min,
        )
        for load in chapter_loads
    ]
    maximums = [
        min(
            allocation_maximum,
            load.scene_count * profile.capacity_policy.scene_characters_max,
        )
        for load in chapter_loads
    ]
    if any(maximum < allocation_minimum for maximum in maximums):
        raise ValueError(
            "A Detail chapter has too few scenes; scene capacity cannot reach "
            "the balanced chapter length range"
        )
    if any(minimum > maximum for minimum, maximum in zip(minimums, maximums, strict=True)):
        raise ValueError("A Detail chapter scene load cannot fit the chapter length range")
    minimum_capacity = sum(minimums)
    maximum_capacity = sum(maximums)
    if maximum_capacity < minimum_viable_book_characters(profile):
        raise ValueError(
            "Detail scene capacity cannot carry the minimum viable whole-book length"
        )
    book_budget = min(
        maximum_capacity,
        max(minimum_capacity, preferred_book_budget),
    )

    load_weights = _chapter_load_weights(chapter_loads)
    chapter_center = book_budget / chapter_count
    targets = [
        min(
            maximums[index],
            max(
                minimums[index],
                round(chapter_center * (1 + load_weight)),
            ),
        )
        for index, load_weight in enumerate(load_weights)
    ]

    _rebalance_target_sum(
        targets,
        total=book_budget,
        minimums=minimums,
        maximums=maximums,
        load_weights=load_weights,
    )
    return targets


def _chapter_allocation_center(
    profile: NarrativeScaleProfile,
    chapter_count: int | None,
    band: ChapterTargetBand | None,
) -> float | None:
    if profile.word_target_soft is None or band is None:
        return None
    resolved_count = chapter_count or _plan_chapter_target(profile)
    center = _book_character_budget(profile, resolved_count, band) / resolved_count
    if not band.min_characters <= center <= band.max_characters:
        raise ValueError(
            "Selected chapter count cannot carry the whole-book target inside "
            "the editorial chapter-length band"
        )
    return center


def _book_character_budget(
    profile: NarrativeScaleProfile,
    chapter_count: int,
    band: ChapterTargetBand,
) -> int:
    """Choose the nearest book budget that preserves preferred chapter length.

    ``word_target_soft`` defines a book-level envelope, not an equation copied
    into every chapter. The preferred editorial chapter length wins whenever
    its whole-book sum stays inside that envelope; otherwise the nearest edge
    of the envelope is used.
    """

    if profile.word_target_soft is None:
        return chapter_count * band.preferred_characters
    tolerance = profile.capacity_policy.book_target_tolerance_percent
    soft_minimum = math.ceil(profile.word_target_soft * (100 - tolerance) / 100)
    soft_maximum = math.floor(profile.word_target_soft * (100 + tolerance) / 100)
    capacity_minimum = chapter_count * band.min_characters
    capacity_maximum = chapter_count * band.max_characters
    minimum = max(soft_minimum, capacity_minimum)
    maximum = min(soft_maximum, capacity_maximum)
    if minimum > maximum:
        raise ValueError(
            "Selected chapter count cannot carry the whole-book soft target envelope "
            "inside the editorial chapter-length band"
        )
    preferred = chapter_count * band.preferred_characters
    return min(maximum, max(minimum, preferred))


def soft_book_length_bounds(
    profile: NarrativeScaleProfile,
) -> tuple[int, int]:
    """Return the advisory whole-book character envelope."""

    target = profile.word_target_soft
    tolerance = profile.capacity_policy.book_target_tolerance_percent
    soft_minimum = math.ceil(target * (100 - tolerance) / 100)
    soft_maximum = math.floor(target * (100 + tolerance) / 100)
    return soft_minimum, soft_maximum


def minimum_viable_book_characters(profile: NarrativeScaleProfile) -> int:
    """Return the non-negotiable floor below the editorial soft band."""

    return max(1, math.ceil(profile.word_target_soft * 70 / 100))


def _chapter_allocation_bounds(
    profile: NarrativeScaleProfile,
    chapter_count: int,
    band: ChapterTargetBand,
) -> tuple[int, int]:
    """Keep every chapter near the book budget center without equalizing it.

    Normal load weights stay near the budget center. The lower allocation bound
    is the same minimum-viable prose floor used by the Text gate so a lean but
    complete scene plan is not rejected merely because it cannot reach the
    preferred center. Scene capacity narrows these bounds per chapter.
    """

    center = _chapter_allocation_center(profile, chapter_count, band)
    if center is None:
        return band.min_characters, band.max_characters
    half_rhythm = band.max_adjacent_delta / 2
    viable_minimum = math.ceil(center * 50 / 100)
    return (
        viable_minimum,
        min(band.max_characters, math.floor(center + half_rhythm)),
    )


def _rebalance_target_sum(
    targets: list[int],
    *,
    total: int,
    minimums: list[int],
    maximums: list[int],
    load_weights: list[float],
) -> None:
    """Restore the exact book total without concentrating rounding drift."""

    remaining = total - sum(targets)
    while remaining:
        increasing = remaining > 0
        candidates = [
            index
            for index, value in enumerate(targets)
            if (
                value < maximums[index]
                if increasing
                else value > minimums[index]
            )
        ]
        if not candidates:
            raise ValueError("Chapter target band cannot preserve the whole-book target")
        candidates.sort(
            key=lambda index: (load_weights[index], -targets[index]),
            reverse=increasing,
        )
        share = max(1, abs(remaining) // len(candidates))
        for index in candidates:
            if remaining == 0:
                break
            capacity = (
                maximums[index] - targets[index]
                if increasing
                else targets[index] - minimums[index]
            )
            adjustment = min(share, capacity, abs(remaining))
            targets[index] += adjustment if increasing else -adjustment
            remaining += -adjustment if increasing else adjustment


def _chapter_load_weights(chapter_loads: list[ChapterNarrativeLoad]) -> list[float]:
    hint_weight = {"compact": -0.035, "standard": 0.0, "expansive": 0.035}
    means = {
        "scenes": sum(item.scene_count for item in chapter_loads) / len(chapter_loads),
        "cast": sum(item.active_cast_count for item in chapter_loads) / len(chapter_loads),
        "turns": sum(item.turn_count for item in chapter_loads) / len(chapter_loads),
        "places": sum(item.distinct_place_count for item in chapter_loads) / len(chapter_loads),
    }
    values = [
        hint_weight[item.length_hint]
        + (item.scene_count - means["scenes"]) * 0.025
        + (item.active_cast_count - means["cast"]) * 0.01
        + (item.turn_count - means["turns"]) * 0.015
        + (item.distinct_place_count - means["places"]) * 0.01
        for item in chapter_loads
    ]
    centered = sum(values) / len(values)
    return [max(-0.075, min(0.075, value - centered)) for value in values]


def chapter_length_contract(
    target_characters: int | None,
    quality_mode: str,
    *,
    scene_count: int,
) -> ChapterLengthContract | None:
    if target_characters is None:
        return None
    # v1.0 keeps balanced prose inside a useful editorial band without
    # turning a slightly lean chapter into a blocking regeneration loop.
    tolerance = {"fast": 15, "balanced": 18, "deep": 8}.get(quality_mode, 18)
    return ChapterLengthContract(
        target_characters=target_characters,
        min_characters=max(1, round(target_characters * (100 - tolerance) / 100)),
        max_characters=max(1, round(target_characters * (100 + tolerance) / 100)),
        scene_count=scene_count,
        characters_per_scene_target=max(1, round(target_characters / scene_count)),
        tolerance_percent=tolerance,
    )


def minimum_viable_chapter_characters(contract: ChapterLengthContract) -> int:
    """Reject only clearly incomplete prose, not ordinary target drift."""

    # Chapter targets guide structure; only content below half the frozen
    # target is treated as likely incomplete. The whole-book 70% floor still
    # remains authoritative at the terminal aggregate gate.
    return max(1, math.ceil(contract.target_characters * 50 / 100))


def count_prose_characters(content: str) -> int:
    return sum(1 for character in content if not character.isspace())


__all__ = [
    "ChapterNarrativeLoad",
    "ChapterTargetBand",
    "DetailChapterBeatSlot",
    "DetailScaleProjection",
    "ChapterLengthContract",
    "NarrativeScalePlan",
    "NarrativeCapacityPolicy",
    "NarrativeScaleProfile",
    "ScaleOverrides",
    "VolumeScaleProjection",
    "allocate_chapter_character_targets",
    "cast_subject_count_range",
    "chapter_length_contract",
    "chapter_count_range",
    "chapter_count_range_for_spine",
    "chapter_target_band",
    "count_prose_characters",
    "detail_scene_count_range",
    "minimum_viable_book_characters",
    "minimum_viable_chapter_characters",
    "plan_narrative_scale",
    "project_turn_chapter_window",
    "project_volume_scales",
    "soft_book_length_bounds",
    "scale_profile_from_inputs",
    "spine_milestone_positions",
    "volume_count_range",
]
