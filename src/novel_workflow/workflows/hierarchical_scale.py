from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.narrative_scale import (
    MINIMUM_SPINE_TURNS,
    NarrativeCapacityPolicy,
    NarrativeScaleProfile,
    chapter_count_range,
)
from novel_workflow.output_contracts.artifacts_vnext import LengthEnvelope


class HierarchicalScaleOverrides(BaseModel):
    """Author locks for the hierarchical plan, before any prose is accepted."""

    model_config = ConfigDict(extra="forbid")

    chapter_target: Optional[int] = Field(default=None, ge=1)
    volume_target: Optional[int] = Field(default=None, ge=1)
    part_target: Optional[int] = Field(default=None, ge=1)
    part_turn_targets: dict[int, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_part_turn_keys(self) -> "HierarchicalScaleOverrides":
        if any(index < 1 for index in self.part_turn_targets):
            raise ValueError("Part turn override keys must be positive ordinals")
        if any(value < MINIMUM_SPINE_TURNS for value in self.part_turn_targets.values()):
            raise ValueError("Part turn targets must satisfy the minimum Spine grammar")
        return self


class _HierarchicalScaleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_envelope: LengthEnvelope
    scale_overrides: HierarchicalScaleOverrides | None = None


class PartScalePlan(BaseModel):
    """One bounded Part projection; ordinals are display positions, not IDs."""

    model_config = ConfigDict(extra="forbid")

    ordinal: int = Field(ge=1)
    chapter_start: int = Field(ge=1)
    chapter_end: int = Field(ge=1)
    chapter_target: int = Field(ge=1)
    volume_start: int = Field(ge=1)
    volume_end: int = Field(ge=1)
    volume_target: int = Field(ge=1)
    volume_chapter_targets: list[int] = Field(min_length=1, max_length=50)
    turn_min: int = Field(ge=MINIMUM_SPINE_TURNS)
    turn_target: int = Field(ge=MINIMUM_SPINE_TURNS)
    turn_max: int = Field(ge=MINIMUM_SPINE_TURNS, le=120)

    @model_validator(mode="after")
    def validate_projection(self) -> "PartScalePlan":
        if self.chapter_start > self.chapter_end:
            raise ValueError("Part chapter projection must be ordered")
        if self.volume_start > self.volume_end:
            raise ValueError("Part volume projection must be ordered")
        if self.volume_target != len(self.volume_chapter_targets):
            raise ValueError("Part volume target must match its volume projections")
        if self.chapter_target != sum(self.volume_chapter_targets):
            raise ValueError("Part chapter target must equal its volume chapter targets")
        if self.chapter_end - self.chapter_start + 1 != self.chapter_target:
            raise ValueError("Part chapter projection must cover its target exactly")
        if self.volume_end - self.volume_start + 1 != self.volume_target:
            raise ValueError("Part volume projection must cover its target exactly")
        if not self.turn_min <= self.turn_target <= self.turn_max:
            raise ValueError("Part turn target must fit its capacity range")
        return self


class HierarchicalNarrativeScalePlan(BaseModel):
    """Book-level capacity without a flat, book-wide Spine array."""

    model_config = ConfigDict(extra="forbid")

    chapter_min: int = Field(ge=1)
    chapter_target: int = Field(ge=1)
    chapter_max: int = Field(ge=1)
    volume_min: int = Field(ge=1)
    volume_target: int = Field(ge=1)
    volume_max: int = Field(ge=1)
    part_min: int = Field(ge=1)
    part_target: int = Field(ge=1)
    part_max: int = Field(ge=1)
    detail_window_min: int = Field(ge=1)
    detail_window_target: int = Field(ge=1)
    detail_window_max: int = Field(ge=1)
    parts: list[PartScalePlan] = Field(min_length=1, max_length=200)
    user_locked: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_book_projection(self) -> "HierarchicalNarrativeScalePlan":
        for label, low, target, high in (
            ("chapter", self.chapter_min, self.chapter_target, self.chapter_max),
            ("volume", self.volume_min, self.volume_target, self.volume_max),
            ("part", self.part_min, self.part_target, self.part_max),
            (
                "detail window",
                self.detail_window_min,
                self.detail_window_target,
                self.detail_window_max,
            ),
        ):
            if not low <= target <= high:
                raise ValueError(f"Hierarchical {label} target must fit its range")
        if len(self.parts) != self.part_target:
            raise ValueError("Part projections must match the frozen Part target")
        if [part.ordinal for part in self.parts] != list(range(1, self.part_target + 1)):
            raise ValueError("Part projections must use contiguous display ordinals")
        if sum(part.chapter_target for part in self.parts) != self.chapter_target:
            raise ValueError("Part chapter targets must sum to the book target")
        if sum(part.volume_target for part in self.parts) != self.volume_target:
            raise ValueError("Part volume targets must sum to the book target")
        return self

    @property
    def total_turn_target(self) -> int:
        """Diagnostic only; no production Artifact may use this as one Spine."""

        return sum(part.turn_target for part in self.parts)


def plan_hierarchical_narrative_scale(
    profile: NarrativeScaleProfile,
    quality_mode: str = "deep",
    overrides: HierarchicalScaleOverrides | None = None,
) -> HierarchicalNarrativeScalePlan:
    """Derive bounded Part/Volume capacity for long books.

    The result deliberately has no book-wide ``turn_target``. Each Part owns a
    local Spine capacity, so a million-character book never asks one Provider
    response or one Artifact array to carry the entire causal plan.
    """

    overrides = overrides or HierarchicalScaleOverrides()
    if quality_mode != "deep" and overrides.model_dump(exclude_defaults=True):
        raise ValueError("Hierarchical scale overrides are available only in deep mode")

    policy = profile.capacity_policy
    chapter_min, chapter_default, chapter_max = chapter_count_range(profile)
    chapter_target = _locked_target(
        "chapter", chapter_default, (chapter_min, chapter_max), overrides.chapter_target
    )
    volume_min, volume_default, volume_max = _volume_range_for_chapters(
        chapter_target, policy
    )
    volume_target = _locked_target(
        "volume", volume_default, (volume_min, volume_max), overrides.volume_target
    )
    part_min, part_default, part_max = _part_range_for_volumes(volume_target, policy)
    part_target = _locked_target(
        "part", part_default, (part_min, part_max), overrides.part_target
    )
    unknown_part_overrides = sorted(
        set(overrides.part_turn_targets) - set(range(1, part_target + 1))
    )
    if unknown_part_overrides:
        raise ValueError(
            "Part turn overrides reference ordinals outside the frozen Part plan: "
            + ", ".join(str(value) for value in unknown_part_overrides)
        )
    volume_chapter_targets = _balanced_allocation(
        chapter_target,
        volume_target,
        policy.volume_chapters_min,
        policy.volume_chapters_max,
    )
    volume_counts = _balanced_allocation(
        volume_target,
        part_target,
        1 if volume_target < policy.part_volumes_min else policy.part_volumes_min,
        policy.part_volumes_max,
    )

    parts: list[PartScalePlan] = []
    chapter_cursor = 1
    volume_cursor = 1
    volume_offset = 0
    for ordinal, volume_count in enumerate(volume_counts, start=1):
        part_volume_targets = volume_chapter_targets[
            volume_offset : volume_offset + volume_count
        ]
        chapter_count = sum(part_volume_targets)
        turn_min, turn_default, turn_max = _part_turn_range(chapter_count, profile)
        turn_override = overrides.part_turn_targets.get(ordinal)
        turn_target = _locked_target(
            f"part-{ordinal} turns",
            turn_default,
            (turn_min, turn_max),
            turn_override,
        )
        parts.append(
            PartScalePlan(
                ordinal=ordinal,
                chapter_start=chapter_cursor,
                chapter_end=chapter_cursor + chapter_count - 1,
                chapter_target=chapter_count,
                volume_start=volume_cursor,
                volume_end=volume_cursor + volume_count - 1,
                volume_target=volume_count,
                volume_chapter_targets=part_volume_targets,
                turn_min=turn_min,
                turn_target=turn_target,
                turn_max=turn_max,
            )
        )
        chapter_cursor += chapter_count
        volume_cursor += volume_count
        volume_offset += volume_count

    window_min = min(policy.detail_window_chapters_min, chapter_target)
    window_max = min(policy.detail_window_chapters_max, chapter_target)
    window_target = min(
        window_max,
        max(window_min, policy.detail_window_chapters_preferred),
    )
    locked = []
    if overrides.chapter_target is not None:
        locked.append("chapter_target")
    if overrides.volume_target is not None:
        locked.append("volume_target")
    if overrides.part_target is not None:
        locked.append("part_target")
    if overrides.part_turn_targets:
        locked.append("part_turn_targets")
    return HierarchicalNarrativeScalePlan(
        chapter_min=chapter_min,
        chapter_target=chapter_target,
        chapter_max=chapter_max,
        volume_min=volume_min,
        volume_target=volume_target,
        volume_max=volume_max,
        part_min=part_min,
        part_target=part_target,
        part_max=part_max,
        detail_window_min=window_min,
        detail_window_target=window_target,
        detail_window_max=window_max,
        parts=parts,
        user_locked=locked,
    )


def hierarchical_scale_plan_from_inputs(
    inputs: dict[str, Any],
    *,
    quality_mode: str,
) -> HierarchicalNarrativeScalePlan:
    """Freeze the code-owned Book/Part scale contract for a new Run."""

    if not isinstance(inputs, dict):
        raise TypeError("Hierarchical scale inputs must be an object")
    parsed = _HierarchicalScaleInput.model_validate(inputs)
    return plan_hierarchical_narrative_scale(
        NarrativeScaleProfile(
            word_target_soft=parsed.length_envelope.word_target_soft,
        ),
        quality_mode=quality_mode,
        overrides=parsed.scale_overrides,
    )


def _volume_range_for_chapters(
    chapter_target: int,
    profile_policy: NarrativeCapacityPolicy,
) -> tuple[int, int, int]:
    if chapter_target < profile_policy.volume_chapters_min:
        return 1, 1, 1
    minimum = max(1, math.ceil(chapter_target / profile_policy.volume_chapters_max))
    maximum = max(minimum, chapter_target // profile_policy.volume_chapters_min)
    target = min(
        maximum,
        max(minimum, round(chapter_target / profile_policy.volume_chapters_preferred)),
    )
    return minimum, target, maximum


def _part_range_for_volumes(
    volume_target: int,
    policy: NarrativeCapacityPolicy,
) -> tuple[int, int, int]:
    if volume_target <= policy.part_volumes_max:
        minimum = 1
    else:
        minimum = math.ceil(volume_target / policy.part_volumes_max)
    maximum = max(
        minimum,
        1 if volume_target < policy.part_volumes_min else volume_target // policy.part_volumes_min,
    )
    target = min(
        maximum,
        max(minimum, round(volume_target / policy.part_volumes_preferred)),
    )
    return minimum, target, maximum


def _part_turn_range(
    chapter_target: int,
    profile: NarrativeScaleProfile,
) -> tuple[int, int, int]:
    policy = profile.capacity_policy
    minimum = max(
        MINIMUM_SPINE_TURNS,
        math.ceil(chapter_target / policy.spine_chapters_per_turn_max),
    )
    target = max(
        minimum,
        round(chapter_target / policy.spine_chapters_per_turn_preferred),
    )
    maximum = max(
        target,
        math.floor(chapter_target / policy.spine_chapters_per_turn_min),
    )
    if maximum > 120:
        raise ValueError(
            "Part capacity still exceeds the 120-turn unit contract; increase Part count"
        )
    return minimum, target, maximum


def _balanced_allocation(
    total: int,
    units: int,
    minimum: int,
    maximum: int,
) -> list[int]:
    if total < 1 or units < 1:
        raise ValueError("Allocation totals and unit counts must be positive")
    if units == 1:
        return [total]
    if total < units * minimum or total > units * maximum:
        raise ValueError(
            f"Cannot allocate {total} items across {units} units in {minimum}-{maximum}"
        )
    base, remainder = divmod(total, units)
    return [base + (1 if index < remainder else 0) for index in range(units)]


def _locked_target(
    label: str,
    default: int,
    bounds: tuple[int, int],
    override: int | None,
) -> int:
    if override is None:
        return default
    low, high = bounds
    if not low <= override <= high:
        raise ValueError(f"{label} override must fit the derived range {low}-{high}")
    return override


__all__ = [
    "HierarchicalNarrativeScalePlan",
    "HierarchicalScaleOverrides",
    "PartScalePlan",
    "hierarchical_scale_plan_from_inputs",
    "plan_hierarchical_narrative_scale",
]
