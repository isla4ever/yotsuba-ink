from __future__ import annotations

"""Bounded planning contracts for the v1.1 long-form hierarchy.

These models intentionally sit beside ``artifacts_vnext`` while the runtime
still speaks the flat Phase 27 contracts.  They make the future migration
boundary explicit: roots carry stable ordered references and child units carry
bounded content.  They are not a compatibility wrapper around the old
ordinal-only artifacts.
"""

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PlanningRefKind = Literal["part", "turn", "volume", "chapter", "window"]
ProgressType = Literal["information", "relationship", "external", "internal"]
MilestoneRef = Literal[
    "inciting",
    "commitment",
    "midpoint_reversal",
    "crisis",
    "climax",
    "aftermath",
]
BOOK_MILESTONES: tuple[MilestoneRef, ...] = (
    "inciting",
    "commitment",
    "midpoint_reversal",
    "crisis",
    "climax",
    "aftermath",
)

_REF_PATTERN = re.compile(
    r"^(?P<kind>part|turn|volume|chapter|window)-(?P<suffix>[A-Za-z0-9][A-Za-z0-9._-]{2,79})$"
)
_SUBJECT_REF_PATTERN = re.compile(
    r"^subject-(?P<suffix>[A-Za-z0-9][A-Za-z0-9._-]{2,79})$"
)


def validate_stable_ref(value: str, kind: PlanningRefKind) -> str:
    """Validate a planning ref without allowing an ordinal-only identity."""

    match = _REF_PATTERN.fullmatch(value.strip())
    if match is None or match.group("kind") != kind:
        raise ValueError(f"{kind} ref must use a stable {kind}-<token> identity")
    suffix = match.group("suffix")
    if suffix.isdigit():
        raise ValueError(f"{kind} ref cannot be ordinal-only")
    return value.strip()


def mint_stable_ref(kind: PlanningRefKind, seed: str) -> str:
    """Mint a deterministic non-ordinal ref from author or import identity."""

    normalized = " ".join(seed.strip().split())
    if not normalized:
        raise ValueError("Stable ref seed must be non-empty")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{kind}-r{digest}"


def _validate_subject_ref(value: str) -> str:
    cleaned = value.strip()
    match = _SUBJECT_REF_PATTERN.fullmatch(cleaned)
    if match is None or match.group("suffix").isdigit():
        raise ValueError("Subject ref must use a stable subject-<token> identity")
    return cleaned


class PlanningArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BookMilestoneBinding(PlanningArtifact):
    milestone: MilestoneRef
    turn_ref: str = Field(min_length=8, max_length=88)

    _turn_ref_validator = field_validator("turn_ref")(
        lambda value: validate_stable_ref(value, "turn")
    )


class StorySpineRootArtifact(PlanningArtifact):
    """Book-level Spine index; it never embeds the full turn list."""

    book_promise: str = Field(min_length=1, max_length=1600)
    book_milestones: list[BookMilestoneBinding] = Field(min_length=6, max_length=6)
    part_refs: list[str] = Field(min_length=1, max_length=200)
    ending: str = Field(min_length=1, max_length=1600)
    open_questions: list[str] = Field(default_factory=list, max_length=32)

    _part_refs_validator = field_validator("part_refs")(
        lambda values: [validate_stable_ref(value, "part") for value in values]
    )

    @model_validator(mode="after")
    def validate_refs(self) -> "StorySpineRootArtifact":
        if len(self.part_refs) != len(set(self.part_refs)):
            raise ValueError("Spine root part refs must be unique")
        if tuple(binding.milestone for binding in self.book_milestones) != BOOK_MILESTONES:
            raise ValueError("Book milestones must bind the six structural roles in order")
        return self


class PartArcArtifact(PlanningArtifact):
    """One bounded Part arc and its ordered local Spine refs."""

    id: str = Field(min_length=8, max_length=88)
    display_ordinal: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=80)
    entry_state: str = Field(min_length=1, max_length=1600)
    promise: str = Field(min_length=1, max_length=1600)
    climax: str = Field(min_length=1, max_length=1800)
    exit_state: str = Field(min_length=1, max_length=1600)
    carried_questions: list[str] = Field(default_factory=list, max_length=24)
    turn_refs: list[str] = Field(min_length=1, max_length=120)

    _id_validator = field_validator("id")(
        lambda value: validate_stable_ref(value, "part")
    )
    _turn_refs_validator = field_validator("turn_refs")(
        lambda values: [validate_stable_ref(value, "turn") for value in values]
    )

    @model_validator(mode="after")
    def validate_refs(self) -> "PartArcArtifact":
        if len(self.turn_refs) != len(set(self.turn_refs)):
            raise ValueError("Part turn refs must be unique and ordered")
        return self


class PartTurnArtifact(PlanningArtifact):
    """A local Spine turn; the 120-item ceiling applies per Part."""

    id: str = Field(min_length=8, max_length=88)
    part_ref: str = Field(min_length=8, max_length=88)
    display_ordinal: int = Field(ge=1)
    cause: str = Field(min_length=1, max_length=1200)
    change: str = Field(min_length=1, max_length=1200)
    progress_type: ProgressType
    milestone_refs: list[MilestoneRef] = Field(default_factory=list, max_length=6)

    _id_validator = field_validator("id")(
        lambda value: validate_stable_ref(value, "turn")
    )
    _part_ref_validator = field_validator("part_ref")(
        lambda value: validate_stable_ref(value, "part")
    )

    @model_validator(mode="after")
    def validate_milestones(self) -> "PartTurnArtifact":
        if len(self.milestone_refs) != len(set(self.milestone_refs)):
            raise ValueError("Part turn milestone refs must be unique")
        return self


class VolumeArchitectureRootArtifact(PlanningArtifact):
    """Ordered Volume index partitioned by Part."""

    part_refs: list[str] = Field(min_length=1, max_length=200)
    volume_refs: list[str] = Field(min_length=1, max_length=500)
    part_volume_order: dict[str, list[str]]

    _part_refs_validator = field_validator("part_refs")(
        lambda values: [validate_stable_ref(value, "part") for value in values]
    )
    _volume_refs_validator = field_validator("volume_refs")(
        lambda values: [validate_stable_ref(value, "volume") for value in values]
    )

    @field_validator("part_volume_order")
    @classmethod
    def validate_partition_refs(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        return {
            validate_stable_ref(part_ref, "part"): [
                validate_stable_ref(volume_ref, "volume") for volume_ref in volume_refs
            ]
            for part_ref, volume_refs in value.items()
        }

    @model_validator(mode="after")
    def validate_order(self) -> "VolumeArchitectureRootArtifact":
        if len(self.part_refs) != len(set(self.part_refs)):
            raise ValueError("Volume root part refs must be unique")
        if len(self.volume_refs) != len(set(self.volume_refs)):
            raise ValueError("Volume root refs must be unique")
        if list(self.part_volume_order) != self.part_refs:
            raise ValueError("Volume partition keys must follow the ordered Part refs")
        flattened = [
            volume_ref
            for part_ref in self.part_refs
            for volume_ref in self.part_volume_order[part_ref]
        ]
        if flattened != self.volume_refs:
            raise ValueError("Volume partition order must cover the ordered volume refs exactly")
        return self


class VolumeUnitArtifact(PlanningArtifact):
    """One Volume unit with bounded local turn coverage."""

    id: str = Field(min_length=8, max_length=88)
    part_ref: str = Field(min_length=8, max_length=88)
    display_ordinal: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=80)
    promise: str = Field(min_length=1, max_length=1000)
    conflict: str = Field(min_length=1, max_length=1000)
    climax: str = Field(min_length=1, max_length=1200)
    climax_turn_ref: str = Field(min_length=8, max_length=88)
    closure: str = Field(min_length=1, max_length=1200)
    turn_refs: list[str] = Field(min_length=1, max_length=120)
    cast_refs: list[str] = Field(default_factory=list, max_length=120)
    length_hint: Literal["short", "medium", "long"]

    _id_validator = field_validator("id")(
        lambda value: validate_stable_ref(value, "volume")
    )
    _part_ref_validator = field_validator("part_ref")(
        lambda value: validate_stable_ref(value, "part")
    )
    _climax_ref_validator = field_validator("climax_turn_ref")(
        lambda value: validate_stable_ref(value, "turn")
    )
    _turn_refs_validator = field_validator("turn_refs")(
        lambda values: [validate_stable_ref(value, "turn") for value in values]
    )
    _cast_refs_validator = field_validator("cast_refs")(
        lambda values: [_validate_subject_ref(value) for value in values]
    )

    @model_validator(mode="after")
    def validate_turns(self) -> "VolumeUnitArtifact":
        if len(self.turn_refs) != len(set(self.turn_refs)):
            raise ValueError("Volume turn refs must be unique")
        if len(self.cast_refs) != len(set(self.cast_refs)):
            raise ValueError("Volume cast refs must be unique")
        if self.climax_turn_ref not in self.turn_refs:
            raise ValueError("Volume climax must reference an owned turn")
        if self.turn_refs.index(self.climax_turn_ref) + 1 < max(
            1, (len(self.turn_refs) * 3 + 4) // 5
        ):
            raise ValueError("Volume climax must land in the final 40 percent of its turns")
        return self


class DetailPlanIndexArtifact(PlanningArtifact):
    """Book-wide chapter/window index without inlining chapter cards."""

    volume_refs: list[str] = Field(min_length=1, max_length=500)
    chapter_order: list[str] = Field(min_length=1, max_length=10_000)
    volume_chapter_order: dict[str, list[str]]
    window_order: list[str] = Field(min_length=1, max_length=500)
    planned_through_ref: str | None = Field(default=None, min_length=8, max_length=88)
    written_through_ref: str | None = Field(default=None, min_length=8, max_length=88)

    _volume_refs_validator = field_validator("volume_refs")(
        lambda values: [validate_stable_ref(value, "volume") for value in values]
    )
    _chapter_order_validator = field_validator("chapter_order")(
        lambda values: [validate_stable_ref(value, "chapter") for value in values]
    )
    _window_order_validator = field_validator("window_order")(
        lambda values: [validate_stable_ref(value, "window") for value in values]
    )

    @field_validator("volume_chapter_order")
    @classmethod
    def validate_volume_chapters(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        return {
            validate_stable_ref(volume_ref, "volume"): [
                validate_stable_ref(chapter_ref, "chapter") for chapter_ref in chapter_refs
            ]
            for volume_ref, chapter_refs in value.items()
        }

    @field_validator("planned_through_ref", "written_through_ref")
    @classmethod
    def validate_progress_ref(cls, value: str | None) -> str | None:
        return None if value is None else validate_stable_ref(value, "chapter")

    @model_validator(mode="after")
    def validate_order(self) -> "DetailPlanIndexArtifact":
        if len(self.volume_refs) != len(set(self.volume_refs)):
            raise ValueError("Detail index volume refs must be unique")
        if len(self.chapter_order) != len(set(self.chapter_order)):
            raise ValueError("Detail index chapter order must be unique")
        if len(self.window_order) != len(set(self.window_order)):
            raise ValueError("Detail index window order must be unique")
        if list(self.volume_chapter_order) != self.volume_refs:
            raise ValueError("Detail volume partitions must follow the ordered volume refs")
        flattened = [
            chapter_ref
            for volume_ref in self.volume_refs
            for chapter_ref in self.volume_chapter_order[volume_ref]
        ]
        if flattened != self.chapter_order:
            raise ValueError("Detail volume partitions must cover chapter order exactly")
        for progress_ref in (self.planned_through_ref, self.written_through_ref):
            if progress_ref is not None and progress_ref not in self.chapter_order:
                raise ValueError("Detail progress ref must be present in chapter order")
        return self


class DetailWindowArtifact(PlanningArtifact):
    """A bounded rolling Detail execution window."""

    id: str = Field(min_length=8, max_length=88)
    start_chapter_ref: str = Field(min_length=8, max_length=88)
    end_chapter_ref: str = Field(min_length=8, max_length=88)
    source_part_refs: list[str] = Field(min_length=1, max_length=50)
    source_volume_refs: list[str] = Field(min_length=1, max_length=50)
    chapter_refs: list[str] = Field(min_length=1, max_length=40)
    entry_handoff: str = Field(min_length=1, max_length=1600)
    exit_handoff: str = Field(min_length=1, max_length=1600)

    _id_validator = field_validator("id")(
        lambda value: validate_stable_ref(value, "window")
    )
    _start_validator = field_validator("start_chapter_ref", "end_chapter_ref")(
        lambda value: validate_stable_ref(value, "chapter")
    )
    _part_refs_validator = field_validator("source_part_refs")(
        lambda values: [validate_stable_ref(value, "part") for value in values]
    )
    _volume_refs_validator = field_validator("source_volume_refs")(
        lambda values: [validate_stable_ref(value, "volume") for value in values]
    )
    _chapter_refs_validator = field_validator("chapter_refs")(
        lambda values: [validate_stable_ref(value, "chapter") for value in values]
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> "DetailWindowArtifact":
        if len(self.chapter_refs) != len(set(self.chapter_refs)):
            raise ValueError("Detail window chapter refs must be unique")
        if len(self.source_part_refs) != len(set(self.source_part_refs)):
            raise ValueError("Detail window source Part refs must be unique")
        if len(self.source_volume_refs) != len(set(self.source_volume_refs)):
            raise ValueError("Detail window source Volume refs must be unique")
        if self.chapter_refs[0] != self.start_chapter_ref:
            raise ValueError("Detail window start ref must match its first chapter")
        if self.chapter_refs[-1] != self.end_chapter_ref:
            raise ValueError("Detail window end ref must match its last chapter")
        return self


class DetailChapterUnitArtifact(PlanningArtifact):
    """One editable chapter card owned by exactly one Detail window."""

    id: str = Field(min_length=8, max_length=88)
    detail_window_ref: str = Field(min_length=8, max_length=88)
    volume_ref: str = Field(min_length=8, max_length=88)
    display_ordinal: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=80)
    target_characters: int | None = Field(default=None, ge=1)
    turn_refs: list[str] = Field(min_length=1, max_length=24)
    purpose: str = Field(min_length=1, max_length=1000)
    pov_ref: str = Field(min_length=1, max_length=88)
    cast_refs: list[str] = Field(min_length=1, max_length=120)
    scene_summaries: list[str] = Field(min_length=1, max_length=12)
    handoff: str = Field(min_length=1, max_length=800)

    _id_validator = field_validator("id")(
        lambda value: validate_stable_ref(value, "chapter")
    )
    _window_validator = field_validator("detail_window_ref")(
        lambda value: validate_stable_ref(value, "window")
    )
    _volume_validator = field_validator("volume_ref")(
        lambda value: validate_stable_ref(value, "volume")
    )
    _turn_refs_validator = field_validator("turn_refs")(
        lambda values: [validate_stable_ref(value, "turn") for value in values]
    )
    _pov_validator = field_validator("pov_ref")(_validate_subject_ref)
    _cast_refs_validator = field_validator("cast_refs")(
        lambda values: [_validate_subject_ref(value) for value in values]
    )

    @model_validator(mode="after")
    def validate_refs(self) -> "DetailChapterUnitArtifact":
        if len(self.turn_refs) != len(set(self.turn_refs)):
            raise ValueError("Detail chapter turn refs must be unique")
        if len(self.cast_refs) != len(set(self.cast_refs)):
            raise ValueError("Detail chapter cast refs must be unique")
        if self.pov_ref not in self.cast_refs:
            raise ValueError("Detail chapter POV must be present in its cast refs")
        return self


__all__ = [
    "BookMilestoneBinding",
    "DetailChapterUnitArtifact",
    "DetailPlanIndexArtifact",
    "DetailWindowArtifact",
    "PartArcArtifact",
    "PartTurnArtifact",
    "StorySpineRootArtifact",
    "VolumeArchitectureRootArtifact",
    "VolumeUnitArtifact",
    "mint_stable_ref",
    "validate_stable_ref",
]
