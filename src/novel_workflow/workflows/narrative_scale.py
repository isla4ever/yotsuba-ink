from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.output_contracts.artifacts_vnext import (
    LengthEnvelope,
    VolumeArchitectureArtifact,
    VolumeContract,
)


class NarrativeScaleProfile(BaseModel):
    """Deterministic capacity guidance derived from user length intent.

    It never assigns volume boundaries, character quotas, or chapter ids.
    """

    model_config = ConfigDict(extra="forbid")

    word_target_soft: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    chapter_target_soft: Optional[int] = Field(default=None, ge=1, le=10_000)
    chapter_min_reasonable: int = Field(default=1, ge=1, le=10_000)
    chapter_max_reasonable: int = Field(default=200, ge=1, le=10_000)
    chapter_scene_cap: int = Field(default=6, ge=1, le=12)
    detail_segment_char_cap: int = Field(default=30_000, ge=4_000, le=500_000)
    volume_candidate_cap: int = Field(default=12, ge=1, le=50)
    json_item_caps: dict[str, int] = Field(default_factory=dict)
    cast_pressure_budget: int = Field(default=12, ge=1, le=200)
    pov_pressure_budget: int = Field(default=8, ge=1, le=200)
    thread_pressure_budget: int = Field(default=8, ge=1, le=200)
    # Deep-mode user customization. When set, the scale plan honors these
    # exactly instead of deriving suggestions from the length envelope.
    volume_target_override: Optional[int] = Field(default=None, ge=1, le=50)
    turn_target_override: Optional[int] = Field(default=None, ge=3, le=24)
    cast_demand_override: Optional[int] = Field(default=None, ge=1, le=200)

    @model_validator(mode="after")
    def validate_range(self) -> "NarrativeScaleProfile":
        if self.chapter_min_reasonable > self.chapter_max_reasonable:
            raise ValueError("Narrative chapter bounds must be ordered")
        if self.chapter_target_soft is not None and not (
            self.chapter_min_reasonable <= self.chapter_target_soft <= self.chapter_max_reasonable
        ):
            raise ValueError("Soft chapter target must fit the reasonable chapter bounds")
        return self


class _NarrativeScaleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_envelope: LengthEnvelope
    scale_overrides: Optional["ScaleOverrides"] = None


class ScaleOverrides(BaseModel):
    """User-chosen structural values, surfaced only by the deep quality mode."""

    model_config = ConfigDict(extra="forbid")

    volume_target: Optional[int] = Field(default=None, ge=1, le=50)
    turn_target: Optional[int] = Field(default=None, ge=3, le=24)
    cast_demand_target: Optional[int] = Field(default=None, ge=1, le=200)


class NarrativeScalePlan(BaseModel):
    """Deterministic structural suggestions derived from the length intent.

    Every value is craft guidance for proposal prompts, not a hard quota:
    the story keeps the final say inside the suggested range.
    """

    model_config = ConfigDict(extra="forbid")

    chapter_target: int = Field(ge=1)
    words_per_chapter: Optional[int] = Field(default=None, ge=1)
    volume_target: int = Field(ge=1)
    volume_min: int = Field(ge=1)
    volume_max: int = Field(ge=1)
    turn_target: int = Field(ge=3)
    turn_min: int = Field(ge=3)
    turn_max: int = Field(ge=3)
    cast_demand_target: int = Field(ge=1)
    cast_demand_min: int = Field(ge=1)
    cast_demand_max: int = Field(ge=1)
    scenes_per_chapter_min: int = Field(default=2, ge=1)
    scenes_per_chapter_max: int = Field(ge=1)
    user_locked: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges(self) -> "NarrativeScalePlan":
        for label, low, target, high in (
            ("volume", self.volume_min, self.volume_target, self.volume_max),
            ("turn", self.turn_min, self.turn_target, self.turn_max),
            ("cast", self.cast_demand_min, self.cast_demand_target, self.cast_demand_max),
        ):
            if not low <= target <= high:
                raise ValueError(f"Scale plan {label} target must fit its range")
        return self


def plan_narrative_scale(
    profile: NarrativeScaleProfile,
    quality_mode: str = "balanced",
) -> NarrativeScalePlan:
    """Derive volume/turn/cast suggestions from the length envelope.

    fast: ranges collapse to the target so the system decides.
    balanced: soft ranges; the model chooses inside them, humans confirm.
    deep: user overrides (when present) are honored exactly.
    """

    chapters = _plan_chapter_target(profile)
    words_per_chapter = (
        max(1, round(profile.word_target_soft / chapters))
        if profile.word_target_soft
        else None
    )

    volume_min = max(1, chapters // 16)
    volume_max = min(profile.volume_candidate_cap, max(1, math.ceil(chapters / 8)))
    volume_target = min(volume_max, max(volume_min, round(chapters / 12), 1))

    turn_target = min(20, max(5, 4 + round(chapters * 0.5)))
    turn_min = max(4, turn_target - 2)
    turn_max = min(24, turn_target + 3)

    cast_target = min(profile.cast_pressure_budget, max(3, 3 + round(chapters / 4)))
    cast_min = max(2, cast_target - 1)
    cast_max = min(profile.cast_pressure_budget, cast_target + 2)

    user_locked: list[str] = []
    if quality_mode == "deep":
        if profile.volume_target_override is not None:
            volume_target = min(profile.volume_candidate_cap, profile.volume_target_override)
            volume_min = volume_max = volume_target
            user_locked.append("volume_target")
        if profile.turn_target_override is not None:
            turn_target = profile.turn_target_override
            turn_min = turn_max = turn_target
            user_locked.append("turn_target")
        if profile.cast_demand_override is not None:
            cast_target = min(profile.cast_pressure_budget, profile.cast_demand_override)
            cast_min = cast_max = cast_target
            user_locked.append("cast_demand_target")
    if quality_mode == "fast":
        volume_min = volume_max = volume_target
        turn_min = turn_max = turn_target
        cast_min = cast_max = cast_target

    return NarrativeScalePlan(
        chapter_target=chapters,
        words_per_chapter=words_per_chapter,
        volume_target=volume_target,
        volume_min=volume_min,
        volume_max=volume_max,
        turn_target=turn_target,
        turn_min=turn_min,
        turn_max=turn_max,
        cast_demand_target=cast_target,
        cast_demand_min=cast_min,
        cast_demand_max=cast_max,
        scenes_per_chapter_max=profile.chapter_scene_cap,
        user_locked=user_locked,
    )


def _plan_chapter_target(profile: NarrativeScaleProfile) -> int:
    if profile.chapter_target_soft is not None:
        target = profile.chapter_target_soft
    elif profile.word_target_soft is not None:
        target = max(1, round(profile.word_target_soft / 2_500))
    else:
        target = 40
    return min(
        profile.chapter_max_reasonable,
        max(profile.chapter_min_reasonable, target),
    )


class VolumeScaleProjection(BaseModel):
    """Rebuildable chapter guidance for one accepted volume contract."""

    model_config = ConfigDict(extra="forbid")

    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    chapter_target_soft: int = Field(ge=1, le=10_000)
    chapter_min_reasonable: int = Field(ge=1, le=10_000)
    chapter_max_reasonable: int = Field(ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_range(self) -> "VolumeScaleProjection":
        if not (
            self.chapter_min_reasonable
            <= self.chapter_target_soft
            <= self.chapter_max_reasonable
        ):
            raise ValueError("Volume chapter target must fit its reasonable range")
        return self


class DetailScaleProjection(BaseModel):
    """One capacity-safe narrative segment inside a volume projection."""

    model_config = ConfigDict(extra="forbid")

    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    segment_ref: str = Field(pattern=r"^volume-[1-9][0-9]*\.segment-[1-9][0-9]*$")
    segment_index: int = Field(ge=1)
    segment_count: int = Field(ge=1)
    chapter_target_soft: int = Field(ge=1)
    chapter_min_reasonable: int = Field(ge=1)
    chapter_max_reasonable: int = Field(ge=1)
    # Scene guidance travels with the segment because a chapter script written
    # without a word budget produces one-scene and six-scene chapters side by
    # side, which the prose stage then has to pad or cram.
    words_per_chapter_soft: Optional[int] = Field(default=None, ge=1)
    scenes_per_chapter_min: int = Field(default=2, ge=1)
    scenes_per_chapter_max: int = Field(default=6, ge=1)
    is_final_volume: bool = False
    # Absolute position of this segment's first chapter in the book. Without
    # it a segment cannot tell which part of a stage-wide revision note is its
    # own, and every segment rewrites the opening.
    chapter_number_start: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_segment(self) -> "DetailScaleProjection":
        if self.segment_index > self.segment_count:
            raise ValueError("Detail segment index exceeds segment count")
        if self.scenes_per_chapter_min > self.scenes_per_chapter_max:
            raise ValueError("Detail scene minimum must not exceed the maximum")
        if not (
            self.chapter_min_reasonable
            <= self.chapter_target_soft
            <= self.chapter_max_reasonable
        ):
            raise ValueError("Detail segment target must fit its reasonable range")
        return self


def scale_profile_from_inputs(inputs: dict[str, Any]) -> NarrativeScaleProfile:
    if not isinstance(inputs, dict):
        raise TypeError("Narrative scale inputs must be an object")
    parsed = _NarrativeScaleInput.model_validate(inputs)
    envelope = parsed.length_envelope
    overrides = parsed.scale_overrides or ScaleOverrides()
    chapter_target = _derived_chapter_target(envelope)
    return NarrativeScaleProfile(
        word_target_soft=envelope.word_target_soft,
        chapter_target_soft=envelope.chapter_target_soft,
        chapter_min_reasonable=max(1, math.floor(chapter_target * 0.65)),
        chapter_max_reasonable=max(chapter_target, math.ceil(chapter_target * 1.45)),
        volume_target_override=overrides.volume_target,
        turn_target_override=overrides.turn_target,
        cast_demand_override=overrides.cast_demand_target,
    )


def _derived_chapter_target(envelope: LengthEnvelope) -> int:
    if envelope.chapter_target_soft is not None:
        return envelope.chapter_target_soft
    if envelope.word_target_soft is not None:
        return max(1, round(envelope.word_target_soft / 2_500))
    return 40


def project_volume_scales(
    architecture: VolumeArchitectureArtifact,
    profile: NarrativeScaleProfile,
) -> list[VolumeScaleProjection]:
    """Allocate soft chapter guidance after creative volume boundaries exist."""

    volumes = list(architecture.volumes)
    if not volumes:
        raise ValueError("Volume scale projection requires accepted volume contracts")
    total_target = _chapter_target(volumes, profile)
    weights = [_volume_weight(volume) for volume in volumes]
    targets = _largest_remainder(total_target, weights)
    return [
        VolumeScaleProjection(
            volume_ref=volume.id,
            chapter_target_soft=target,
            chapter_min_reasonable=max(1, math.floor(target * 0.65)),
            chapter_max_reasonable=max(target, math.ceil(target * 1.45)),
        )
        for volume, target in zip(volumes, targets, strict=True)
    ]


def _chapter_target(
    volumes: list[VolumeContract],
    profile: NarrativeScaleProfile,
) -> int:
    if profile.chapter_target_soft is not None:
        target = profile.chapter_target_soft
    elif profile.word_target_soft is not None:
        target = max(len(volumes), round(profile.word_target_soft / 2_500))
    else:
        target = sum(max(1, len(volume.turn_refs) * 2) for volume in volumes)
    return min(
        profile.chapter_max_reasonable,
        max(profile.chapter_min_reasonable, target, len(volumes)),
    )


def _volume_weight(volume: VolumeContract) -> float:
    length_factor = {"short": 0.8, "medium": 1.0, "long": 1.35}[volume.length_hint]
    structural_load = (
        len(volume.turn_refs)
        + max(0, len(volume.cast_ids) - 2) * 0.35
        + len(volume.thread_ids) * 0.5
    )
    return max(0.5, structural_load * length_factor)


def _largest_remainder(total: int, weights: list[float]) -> list[int]:
    if total < len(weights):
        raise ValueError("Chapter target cannot assign at least one chapter per volume")
    remaining = total - len(weights)
    weight_total = sum(weights)
    raw = [remaining * weight / weight_total for weight in weights]
    values = [1 + math.floor(value) for value in raw]
    missing = total - sum(values)
    order = sorted(
        range(len(values)),
        key=lambda index: (raw[index] - math.floor(raw[index]), weights[index]),
        reverse=True,
    )
    for index in order[:missing]:
        values[index] += 1
    return values


__all__ = [
    "DetailScaleProjection",
    "NarrativeScalePlan",
    "NarrativeScaleProfile",
    "ScaleOverrides",
    "VolumeScaleProjection",
    "plan_narrative_scale",
    "project_volume_scales",
    "scale_profile_from_inputs",
]
