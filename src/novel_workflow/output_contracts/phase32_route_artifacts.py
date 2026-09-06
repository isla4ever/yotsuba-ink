"""Dormant Phase 32 planning Artifact contracts.

These models intentionally contain only author-facing creative content and
stable domain references. Runtime metadata, Provider receipts, review state,
versions and UI projections remain outside the core Artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Self, TypeAlias, TypeVar

from pydantic import Field, field_validator, model_validator

from novel_workflow.output_contracts.phase32_artifact_base import (
    DeliveryFormat,
    NonEmptyText,
    Phase32Artifact,
    PromiseRef,
    Ref,
    ScreenplayBlockKind,
    ShortText,
)
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    BookDeliveryArtifact,
    ChapterArtifact,
    CoverArtifact,
    CoverBrief,
    CoverCandidate,
    ScreenplayBlock,
    ScreenplayDraftArtifact,
    ScriptDeliveryArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.workflows.route_specs import ArtifactKind, CreationRouteId


class ScreenplayBriefArtifact(Phase32Artifact):
    title: ShortText = Field(
        description="正式样片名；必须对应核心冲突，不得使用路线、阶段或待定占位。"
    )
    sample_type: ShortText = Field(
        description=(
            "面向作者的样片创作类型，例如‘当代调查悬疑样片’；"
            "不得填写 screenplay_sample、brief 等路线或阶段内部标识。"
        )
    )
    target_minutes: int = Field(
        ge=3,
        le=30,
        description="冻结规模合同中的目标可拍摄分钟数。",
    )
    premise: NonEmptyText = Field(
        description="一句话说明主角处境、具体目标、阻碍和故事成立的独特条件。"
    )
    audience_promise: NonEmptyText = Field(
        description=(
            "本故事独有的观众体验：观众会持续追问什么、如何参与判断，"
            "以及结尾将获得何种认知或情绪兑现；不能只写类型标签。"
        )
    )
    visible_conflict: NonEmptyText = Field(
        description=(
            "台面可见的核心对抗，必须交代行动目标、具体对抗者或阻力、期限、"
            "失败后果以及主角必须作出的不可逆选择。"
        )
    )
    ending_effect: NonEmptyText = Field(
        description=(
            "样片结尾的可见揭示与交换：说明主角向谁交付、暴露或保留了什么，"
            "失去何种控制权或关系，换来什么，并留下哪个可继续追查的问题。"
        )
    )
    tone: ShortText = Field(
        description="可执行的视听语气与表达约束，不使用空泛市场形容词。"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _validated_formal_title(value)


class NovelBriefArtifact(Phase32Artifact):
    title: ShortText = Field(
        description="正式作品名；必须对应故事承诺，不得使用路线、阶段或待定占位。"
    )
    premise: NonEmptyText
    audience_promise: NonEmptyText
    theme_question: NonEmptyText
    world_rules: tuple[NonEmptyText, ...] = Field(min_length=1, max_length=32)
    ending_direction: NonEmptyText
    narrative_voice: ShortText
    target_characters: int = Field(ge=2_000, le=1_000_000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _validated_formal_title(value)

    def validate_for_route(self, route_id: CreationRouteId) -> Self:
        if route_id == "short_novel" and not 2_000 <= self.target_characters <= 130_000:
            raise ValueError("Short novel target characters must be between 2,000 and 130,000")
        if route_id == "long_novel" and not 100_000 <= self.target_characters <= 1_000_000:
            raise ValueError("Long novel target characters must be between 100,000 and 1,000,000")
        if route_id == "screenplay_sample":
            raise ValueError("Novel brief cannot bind to screenplay route")
        return self


def _validated_formal_title(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    if (
        "待定" in value
        or value.startswith("未命名")
        or normalized
        in {
            "brief",
            "export",
            "screenplay_sample",
            "short_novel",
            "long_novel",
        }
    ):
        raise ValueError("Brief title must be a formal work title, not a placeholder or route id")
    return value


class CharacterRecord(Phase32Artifact):
    subject_ref: Ref = Field(description="Code-stable subject identifier for this Cast.")
    display_name: ShortText = Field(description="Author-facing character name.")
    role: NonEmptyText = Field(
        description=(
            "Current dramatic function in the accepted plan; a role must not assert hidden guilt, "
            "culpability, or an unresolved identity as fact."
        )
    )
    desire: NonEmptyText = Field(
        description=(
            "Observable or explicitly established goal; do not invent a concealed motive from an "
            "open question or suspected allegation."
        )
    )
    stakes: NonEmptyText = Field(
        description=(
            "Perceived or projected consequences under the accepted plan; distinguish risks from "
            "guaranteed death, guilt, punishment, or legal outcome."
        )
    )
    constraints: tuple[NonEmptyText, ...] = Field(
        min_length=1,
        max_length=16,
        description=(
            "Observable, author-constrained, or explicitly perceived limitations; unresolved claims "
            "must stay qualified rather than becoming biography or fact."
        ),
    )
    voice: NonEmptyText = Field(
        description="Distinct speaking and expression pattern, without adding unsupported biography."
    )
    arc_scope: NonEmptyText = Field(
        description=(
            "Planned range of change, not a completed future outcome and not proof that an open "
            "question has one answer."
        )
    )


class CharacterRelationship(Phase32Artifact):
    from_subject_ref: Ref
    to_subject_ref: Ref
    pressure: NonEmptyText = Field(
        description=(
            "Observable or mutually perceived relationship pressure; do not establish suspected "
            "culpability or hidden motive as truth."
        )
    )
    change_trigger: NonEmptyText = Field(
        description=(
            "A future observable condition that may change the relationship; do not write the "
            "planned revelation as already proven."
        )
    )


class CharacterBibleArtifact(Phase32Artifact):
    characters: tuple[CharacterRecord, ...] = Field(min_length=1, max_length=120)
    relationships: tuple[CharacterRelationship, ...] = Field(default=(), max_length=360)

    @model_validator(mode="after")
    def validate_subject_registry(self) -> Self:
        refs = tuple(character.subject_ref for character in self.characters)
        if len(set(refs)) != len(refs):
            raise ValueError("Character subject refs must be unique")
        known = set(refs)
        seen_edges: set[tuple[str, str]] = set()
        for relation in self.relationships:
            edge = (relation.from_subject_ref, relation.to_subject_ref)
            if relation.from_subject_ref not in known or relation.to_subject_ref not in known:
                raise ValueError("Character relationship references an unknown subject")
            if relation.from_subject_ref == relation.to_subject_ref:
                raise ValueError("Character relationship cannot point to itself")
            if edge in seen_edges:
                raise ValueError("Character relationships must be unique")
            seen_edges.add(edge)
        return self


class BeatBoardBeat(Phase32Artifact):
    beat_ref: Ref
    dramatic_job: NonEmptyText = Field(
        description="使用简体中文描述本节拍在剧本中的戏剧任务。"
    )
    visible_pressure: NonEmptyText = Field(
        description="使用简体中文描述屏幕上可见的外部压力，不写内心解释。"
    )
    character_decision: NonEmptyText = Field(
        description=(
            "使用简体中文描述角色在台面上作出的具体决定；不得用‘无决定’或 "
            "'No decision' 占位。"
        )
    )
    outcome: NonEmptyText = Field(
        description="使用简体中文描述该决定造成的可见结果或新的局面。"
    )
    setup_or_payoff_refs: tuple[PromiseRef, ...] = Field(
        default=(),
        max_length=24,
        description=(
            "Stable ASCII setup/payoff identifiers matching ^[a-z][a-z0-9_-]{1,63}$, "
            "for example setup_abnormal_signal or payoff_chen_mo_arrival. "
            "Do not use labels with colons, Chinese prose, or explanatory text."
        ),
    )
    timing_hint: ShortText = Field(
        description="使用简体中文或数字时间范围给出柔性节奏提示。"
    )


class BeatBoardArtifact(Phase32Artifact):
    beats: tuple[BeatBoardBeat, ...] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_beat_refs(self) -> Self:
        refs = tuple(beat.beat_ref for beat in self.beats)
        if len(set(refs)) != len(refs):
            raise ValueError("Beat refs must be unique")
        return self


class SceneDeckScene(Phase32Artifact):
    scene_ref: Ref
    heading: ShortText
    location_and_time: ShortText
    cast_subject_refs: tuple[Ref, ...] = Field(min_length=1, max_length=32)
    visible_goal: NonEmptyText
    opposition: NonEmptyText
    outcome: NonEmptyText
    soft_page_target: float = Field(ge=0.5, le=50)

    @model_validator(mode="after")
    def validate_cast_scope(self) -> Self:
        if len(set(self.cast_subject_refs)) != len(self.cast_subject_refs):
            raise ValueError("Scene Deck cast subject refs must be unique")
        return self


class SceneDeckArtifact(Phase32Artifact):
    scenes: tuple[SceneDeckScene, ...] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_scene_refs(self) -> Self:
        refs = tuple(scene.scene_ref for scene in self.scenes)
        if len(set(refs)) != len(refs):
            raise ValueError("Scene refs must be unique")
        return self


class StoryMapAnchor(Phase32Artifact):
    anchor_ref: Ref
    dramatic_job: NonEmptyText
    pressure: NonEmptyText
    choice_or_revelation: NonEmptyText
    consequence_or_open_effect: NonEmptyText
    promise_refs: tuple[PromiseRef, ...] = Field(
        default=(),
        max_length=24,
        description=(
            "Stable ASCII promise refs advanced by this anchor. New candidates "
            "must provide at least one; the optional schema shape preserves old runs."
        ),
    )


class StoryMapArtifact(Phase32Artifact):
    opening_state: NonEmptyText
    story_question: NonEmptyText
    anchors: tuple[StoryMapAnchor, ...] = Field(min_length=1, max_length=120)
    ending_state: NonEmptyText
    open_questions: tuple[NonEmptyText, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def validate_anchor_refs(self) -> Self:
        refs = tuple(anchor.anchor_ref for anchor in self.anchors)
        if len(set(refs)) != len(refs):
            raise ValueError("Story map anchor refs must be unique")
        return self


class SectionPlanUnit(Phase32Artifact):
    unit_ref: Ref
    ordinal: int = Field(ge=1, le=400)
    title: ShortText
    dramatic_job: NonEmptyText
    pov_subject_ref: Ref
    scene_load: NonEmptyText
    handoff: NonEmptyText
    soft_character_budget: int = Field(ge=100, le=100_000)
    promise_refs: tuple[PromiseRef, ...] = Field(
        default=(),
        max_length=24,
        description=(
            "Accepted Story Map promise refs carried by this unit. New candidates "
            "must provide at least one; the optional schema shape preserves old runs."
        ),
    )


class SectionPlanArtifact(Phase32Artifact):
    units: tuple[SectionPlanUnit, ...] = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def validate_unit_order(self) -> Self:
        refs = tuple(unit.unit_ref for unit in self.units)
        ordinals = tuple(unit.ordinal for unit in self.units)
        if len(set(refs)) != len(refs):
            raise ValueError("Section plan unit refs must be unique")
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("Section plan unit ordinals must be contiguous")
        return self


class PartContract(Phase32Artifact):
    part_ref: Ref
    ordinal: int = Field(ge=1, le=24)
    entry_state: NonEmptyText
    dramatic_question: NonEmptyText
    promise_refs: tuple[PromiseRef, ...] = Field(min_length=1, max_length=32)
    turning_point_refs: tuple[Ref, ...] = Field(min_length=1, max_length=32)
    exit_state: NonEmptyText
    unresolved_obligations: tuple[NonEmptyText, ...] = Field(default=(), max_length=32)


class BookArchitectureArtifact(Phase32Artifact):
    book_promise: NonEmptyText
    ending_conditions: tuple[NonEmptyText, ...] = Field(min_length=1, max_length=32)
    parts: tuple[PartContract, ...] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_part_order(self) -> Self:
        refs = tuple(part.part_ref for part in self.parts)
        ordinals = tuple(part.ordinal for part in self.parts)
        if len(set(refs)) != len(refs):
            raise ValueError("Book part refs must be unique")
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("Book part ordinals must be contiguous")
        return self


class VolumeContract(Phase32Artifact):
    volume_ref: Ref
    ordinal: int = Field(ge=1, le=24)
    part_ref: Ref
    promise: NonEmptyText
    conflict: NonEmptyText
    climax: NonEmptyText
    closure: NonEmptyText
    cast_subject_refs: tuple[Ref, ...] = Field(min_length=1, max_length=120)
    length_hint: int = Field(ge=2_000, le=300_000)

    @model_validator(mode="after")
    def validate_cast_scope(self) -> Self:
        if len(set(self.cast_subject_refs)) != len(self.cast_subject_refs):
            raise ValueError("Volume cast subject refs must be unique")
        return self


class VolumeArchitectureArtifact(Phase32Artifact):
    volumes: tuple[VolumeContract, ...] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_volume_order(self) -> Self:
        refs = tuple(volume.volume_ref for volume in self.volumes)
        ordinals = tuple(volume.ordinal for volume in self.volumes)
        if len(set(refs)) != len(refs):
            raise ValueError("Volume refs must be unique")
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("Volume ordinals must be contiguous")
        return self


class DetailScenePlan(Phase32Artifact):
    scene_ref: Ref
    ordinal: int = Field(ge=1, le=64)
    location: ShortText
    time_context: ShortText
    cast_subject_refs: tuple[Ref, ...] = Field(min_length=1, max_length=32)
    goal: NonEmptyText
    opposition: NonEmptyText
    outcome: NonEmptyText

    @model_validator(mode="after")
    def validate_cast_scope(self) -> Self:
        if len(set(self.cast_subject_refs)) != len(self.cast_subject_refs):
            raise ValueError("Detail Scene cast subject refs must be unique")
        return self


class DetailChapterPlan(Phase32Artifact):
    chapter_ref: Ref
    ordinal: int = Field(ge=1, le=500)
    volume_ref: Ref
    title: ShortText
    pov_subject_ref: Ref
    cast_subject_refs: tuple[Ref, ...] = Field(min_length=1, max_length=64)
    dramatic_job: NonEmptyText
    entry_state: NonEmptyText
    scenes: tuple[DetailScenePlan, ...] = Field(min_length=1, max_length=32)
    conflict: NonEmptyText
    stakes: NonEmptyText
    exit_state: NonEmptyText
    hook: NonEmptyText
    handoff: NonEmptyText
    length_hint: int = Field(ge=100, le=100_000)

    @model_validator(mode="after")
    def validate_scene_plan(self) -> Self:
        if len(set(self.cast_subject_refs)) != len(self.cast_subject_refs):
            raise ValueError("Detail Chapter cast subject refs must be unique")
        if self.pov_subject_ref not in self.cast_subject_refs:
            raise ValueError("Detail Chapter POV must belong to its Cast scope")
        scene_refs = tuple(scene.scene_ref for scene in self.scenes)
        scene_ordinals = tuple(scene.ordinal for scene in self.scenes)
        if len(set(scene_refs)) != len(scene_refs):
            raise ValueError("Detail Scene refs must be unique within a Chapter")
        if scene_ordinals != tuple(range(1, len(scene_ordinals) + 1)):
            raise ValueError("Detail Scene ordinals must be contiguous")
        chapter_subjects = set(self.cast_subject_refs)
        unknown_scene_subjects = sorted(
            {
                subject_ref
                for scene in self.scenes
                for subject_ref in scene.cast_subject_refs
            }
            - chapter_subjects
        )
        if unknown_scene_subjects:
            raise ValueError(
                "Detail Scene references subjects outside its Chapter Cast scope: "
                f"{unknown_scene_subjects}"
            )
        return self


class DetailWindow(Phase32Artifact):
    window_ref: Ref
    ordinal: int = Field(ge=1, le=24)
    volume_refs: tuple[Ref, ...] = Field(min_length=1, max_length=3)
    chapters: tuple[DetailChapterPlan, ...] = Field(min_length=1, max_length=40)
    entry_state: NonEmptyText
    handoff: NonEmptyText
    next_window_entry_state: NonEmptyText

    @model_validator(mode="after")
    def validate_chapter_window(self) -> Self:
        if len(set(self.volume_refs)) != len(self.volume_refs):
            raise ValueError("Detail Window Volume refs must be unique")
        chapter_refs = tuple(chapter.chapter_ref for chapter in self.chapters)
        chapter_ordinals = tuple(chapter.ordinal for chapter in self.chapters)
        if len(set(chapter_refs)) != len(chapter_refs):
            raise ValueError("Detail Chapter refs must be unique within a Window")
        first_ordinal = chapter_ordinals[0]
        if chapter_ordinals != tuple(
            range(first_ordinal, first_ordinal + len(chapter_ordinals))
        ):
            raise ValueError("Detail Chapter ordinals must be contiguous within a Window")
        chapter_volumes = {chapter.volume_ref for chapter in self.chapters}
        if chapter_volumes != set(self.volume_refs):
            raise ValueError(
                "Detail Chapter volume refs must match the Window Volume scope"
            )
        return self


class DetailPlanIndexArtifact(Phase32Artifact):
    windows: tuple[DetailWindow, ...] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_window_order_and_coverage(self) -> Self:
        refs = tuple(window.window_ref for window in self.windows)
        ordinals = tuple(window.ordinal for window in self.windows)
        chapters = tuple(chapter for window in self.windows for chapter in window.chapters)
        chapter_refs = tuple(chapter.chapter_ref for chapter in chapters)
        chapter_ordinals = tuple(chapter.ordinal for chapter in chapters)
        scene_refs = tuple(
            scene.scene_ref
            for chapter in chapters
            for scene in chapter.scenes
        )
        if len(set(refs)) != len(refs):
            raise ValueError("Detail window refs must be unique")
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("Detail window ordinals must be contiguous")
        if len(set(chapter_refs)) != len(chapter_refs):
            raise ValueError("Detail chapter refs must be unique across windows")
        if chapter_ordinals != tuple(range(1, len(chapter_ordinals) + 1)):
            raise ValueError("Detail chapter ordinals must be contiguous across windows")
        if len(set(scene_refs)) != len(scene_refs):
            raise ValueError("Detail Scene refs must be unique across Chapters")
        return self


Phase32PlanningArtifact: TypeAlias = (
    ScreenplayBriefArtifact
    | NovelBriefArtifact
    | CharacterBibleArtifact
    | BeatBoardArtifact
    | SceneDeckArtifact
    | StoryMapArtifact
    | SectionPlanArtifact
    | BookArchitectureArtifact
    | VolumeArchitectureArtifact
    | DetailPlanIndexArtifact
)

Phase32CoreArtifact: TypeAlias = (
    Phase32PlanningArtifact
    | ScreenplayDraftArtifact
    | ShortProseUnitArtifact
    | ChapterArtifact
    | CoverArtifact
    | ScriptDeliveryArtifact
    | BookDeliveryArtifact
)


@dataclass(frozen=True, slots=True)
class RouteArtifactBinding:
    route_id: CreationRouteId
    stage_id: str
    artifact_kind: ArtifactKind
    model_type: type[Phase32CoreArtifact]


_BINDINGS: dict[tuple[CreationRouteId, str], RouteArtifactBinding] = {
    ("screenplay_sample", "brief"): RouteArtifactBinding(
        "screenplay_sample", "brief", "screenplay_brief", ScreenplayBriefArtifact
    ),
    ("screenplay_sample", "cast"): RouteArtifactBinding(
        "screenplay_sample", "cast", "character_bible", CharacterBibleArtifact
    ),
    ("screenplay_sample", "beat_board"): RouteArtifactBinding(
        "screenplay_sample", "beat_board", "beat_board", BeatBoardArtifact
    ),
    ("screenplay_sample", "scene_deck"): RouteArtifactBinding(
        "screenplay_sample", "scene_deck", "scene_deck", SceneDeckArtifact
    ),
    ("screenplay_sample", "script"): RouteArtifactBinding(
        "screenplay_sample", "script", "screenplay_draft", ScreenplayDraftArtifact
    ),
    ("screenplay_sample", "export"): RouteArtifactBinding(
        "screenplay_sample", "export", "script_delivery", ScriptDeliveryArtifact
    ),
    ("short_novel", "brief"): RouteArtifactBinding(
        "short_novel", "brief", "novel_brief", NovelBriefArtifact
    ),
    ("short_novel", "story_map"): RouteArtifactBinding(
        "short_novel", "story_map", "story_map", StoryMapArtifact
    ),
    ("short_novel", "cast"): RouteArtifactBinding(
        "short_novel", "cast", "character_bible", CharacterBibleArtifact
    ),
    ("short_novel", "section_plan"): RouteArtifactBinding(
        "short_novel", "section_plan", "section_plan", SectionPlanArtifact
    ),
    ("short_novel", "text"): RouteArtifactBinding(
        "short_novel", "text", "short_prose_unit", ShortProseUnitArtifact
    ),
    ("short_novel", "cover"): RouteArtifactBinding(
        "short_novel", "cover", "cover", CoverArtifact
    ),
    ("short_novel", "export"): RouteArtifactBinding(
        "short_novel", "export", "book_delivery", BookDeliveryArtifact
    ),
    ("long_novel", "brief"): RouteArtifactBinding(
        "long_novel", "brief", "novel_brief", NovelBriefArtifact
    ),
    ("long_novel", "book_architecture"): RouteArtifactBinding(
        "long_novel", "book_architecture", "book_architecture", BookArchitectureArtifact
    ),
    ("long_novel", "cast"): RouteArtifactBinding(
        "long_novel", "cast", "character_bible", CharacterBibleArtifact
    ),
    ("long_novel", "volumes"): RouteArtifactBinding(
        "long_novel", "volumes", "volume_architecture", VolumeArchitectureArtifact
    ),
    ("long_novel", "rolling_detail"): RouteArtifactBinding(
        "long_novel", "rolling_detail", "detail_plan_index", DetailPlanIndexArtifact
    ),
    ("long_novel", "text"): RouteArtifactBinding(
        "long_novel", "text", "chapter", ChapterArtifact
    ),
    ("long_novel", "cover"): RouteArtifactBinding(
        "long_novel", "cover", "cover", CoverArtifact
    ),
    ("long_novel", "export"): RouteArtifactBinding(
        "long_novel", "export", "book_delivery", BookDeliveryArtifact
    ),
}


ArtifactT = TypeVar("ArtifactT", bound=Phase32CoreArtifact)


def bind_phase32_artifact(
    route_id: CreationRouteId,
    stage_id: str,
    artifact: ArtifactT,
) -> ArtifactT:
    """Validate that an Artifact belongs to the frozen route/stage contract."""

    try:
        binding = _BINDINGS[(route_id, stage_id)]
    except KeyError as exc:
        raise ValueError(
            f"No Phase 32 Artifact contract for {route_id}/{stage_id}"
        ) from exc
    if not isinstance(artifact, binding.model_type):
        raise ValueError(
            f"Artifact type {type(artifact).__name__} does not match "
            f"{route_id}/{stage_id} ({binding.artifact_kind})"
        )
    if isinstance(artifact, NovelBriefArtifact):
        artifact.validate_for_route(route_id)
    return artifact


def validate_long_novel_hierarchy(
    architecture: BookArchitectureArtifact,
    volumes: VolumeArchitectureArtifact,
    detail_index: DetailPlanIndexArtifact,
    cast: CharacterBibleArtifact | None = None,
) -> None:
    """Validate source-bound Part -> Volume -> rolling Window references."""

    validate_volume_architecture_references(architecture, volumes, cast)
    validate_rolling_detail_references(volumes, detail_index, cast)


def validate_section_plan_references(
    story_map: StoryMapArtifact,
    section_plan: SectionPlanArtifact,
    cast: CharacterBibleArtifact,
) -> None:
    """Validate one Section Plan against committed Story Map and Cast registries."""

    validate_story_map_promise_references(story_map)

    subject_refs = {character.subject_ref for character in cast.characters}
    unknown_subjects = sorted(
        {unit.pov_subject_ref for unit in section_plan.units} - subject_refs
    )
    if unknown_subjects:
        raise ValueError(
            f"Section Plan references unknown Cast subjects: {unknown_subjects}"
        )

    units_without_promises = [
        unit.unit_ref for unit in section_plan.units if not unit.promise_refs
    ]
    if units_without_promises:
        raise ValueError(
            "Section Plan units must carry at least one Story Map promise ref: "
            f"{units_without_promises}"
        )

    story_promise_refs = {
        promise_ref
        for anchor in story_map.anchors
        for promise_ref in anchor.promise_refs
    }
    unknown_promises = sorted(
        {
            promise_ref
            for unit in section_plan.units
            for promise_ref in unit.promise_refs
        }
        - story_promise_refs
    )
    if unknown_promises:
        raise ValueError(
            f"Section Plan references unknown Story Map promises: {unknown_promises}"
        )

    covered_promises = {
        promise_ref
        for unit in section_plan.units
        for promise_ref in unit.promise_refs
    }
    uncovered_promises = sorted(story_promise_refs - covered_promises)
    if uncovered_promises:
        raise ValueError(
            "Section Plan does not cover committed Story Map promises: "
            f"{uncovered_promises}"
        )


def validate_story_map_promise_references(story_map: StoryMapArtifact) -> None:
    """Require new Story Maps to expose the promise spine used by later context projection.

    The Pydantic fields remain optional so persisted pre-gate runs can still be read.
    Candidate and author-edit validation call this explicit production boundary.
    """

    anchors_without_promises = [
        anchor.anchor_ref for anchor in story_map.anchors if not anchor.promise_refs
    ]
    if anchors_without_promises:
        raise ValueError(
            "Story Map anchors must carry at least one stable promise ref: "
            f"{anchors_without_promises}"
        )


def validate_scene_deck_references(
    scene_deck: SceneDeckArtifact,
    cast: CharacterBibleArtifact,
) -> None:
    """Validate Scene Deck Cast references against the committed registry."""

    subject_refs = {character.subject_ref for character in cast.characters}
    unknown_subjects = sorted(
        {
            subject_ref
            for scene in scene_deck.scenes
            for subject_ref in scene.cast_subject_refs
        }
        - subject_refs
    )
    if unknown_subjects:
        raise ValueError(
            f"Scene Deck references unknown Cast subjects: {unknown_subjects}"
        )
    for scene in scene_deck.scenes:
        validate_scene_contiguous_boundary(scene)


_SCENE_TRANSITION_MARKERS = re.compile(r"[/／;；]|随后|然后|转至|切到")


def validate_scene_contiguous_boundary(scene: SceneDeckScene) -> None:
    """Keep each Scene Deck row atomic for the sequential Script cursor."""

    if _SCENE_TRANSITION_MARKERS.search(scene.heading) or _SCENE_TRANSITION_MARKERS.search(
        scene.location_and_time
    ):
        raise ValueError(
            "Scene Deck scene must describe one contiguous location and time; "
            "split transitions into separate scenes"
        )


def validate_rolling_detail_references(
    volumes: VolumeArchitectureArtifact,
    detail_index: DetailPlanIndexArtifact,
    cast: CharacterBibleArtifact | None = None,
) -> None:
    """Validate one Detail aggregate against committed Volume and Cast registries."""

    volume_refs = {volume.volume_ref for volume in volumes.volumes}
    unknown_window_volumes = sorted(
        {
            volume_ref
            for window in detail_index.windows
            for volume_ref in window.volume_refs
        }
        - volume_refs
    )
    if unknown_window_volumes:
        raise ValueError(
            f"Detail Window references unknown Volumes: {unknown_window_volumes}"
        )
    unknown_chapter_volumes = sorted(
        {
            chapter.volume_ref
            for window in detail_index.windows
            for chapter in window.chapters
        }
        - volume_refs
    )
    if unknown_chapter_volumes:
        raise ValueError(
            f"Detail Chapter references unknown Volumes: {unknown_chapter_volumes}"
        )
    if cast is None:
        return
    subject_refs = {character.subject_ref for character in cast.characters}
    detail_subject_refs = {
        subject_ref
        for window in detail_index.windows
        for chapter in window.chapters
        for subject_ref in (chapter.pov_subject_ref, *chapter.cast_subject_refs)
    }
    unknown_subjects = sorted(detail_subject_refs - subject_refs)
    if unknown_subjects:
        raise ValueError(
            f"Detail Chapter references unknown Cast subjects: {unknown_subjects}"
        )
    volume_cast = {
        volume.volume_ref: set(volume.cast_subject_refs)
        for volume in volumes.volumes
    }
    out_of_scope = sorted(
        {
            subject_ref
            for window in detail_index.windows
            for chapter in window.chapters
            for subject_ref in chapter.cast_subject_refs
            if subject_ref not in volume_cast[chapter.volume_ref]
        }
    )
    if out_of_scope:
        raise ValueError(
            "Detail Chapter references subjects outside committed Volume Cast scope: "
            f"{out_of_scope}"
        )


def validate_volume_architecture_references(
    architecture: BookArchitectureArtifact,
    volumes: VolumeArchitectureArtifact,
    cast: CharacterBibleArtifact | None = None,
) -> None:
    """Validate one Volume aggregate against committed Part and Cast registries."""

    part_refs = {part.part_ref for part in architecture.parts}
    unknown_parts = sorted(
        {volume.part_ref for volume in volumes.volumes} - part_refs
    )
    if unknown_parts:
        raise ValueError(f"Volume references unknown Parts: {unknown_parts}")
    covered_parts = {volume.part_ref for volume in volumes.volumes}
    missing_parts = sorted(part_refs - covered_parts)
    if missing_parts:
        raise ValueError(f"Book Parts have no Volume coverage: {missing_parts}")
    if cast is None:
        return
    subject_refs = {character.subject_ref for character in cast.characters}
    unknown_subjects = sorted(
        {
            subject_ref
            for volume in volumes.volumes
            for subject_ref in volume.cast_subject_refs
        }
        - subject_refs
    )
    if unknown_subjects:
        raise ValueError(f"Volume references unknown Cast subjects: {unknown_subjects}")


def phase32_artifact_binding(
    route_id: CreationRouteId,
    stage_id: str,
) -> RouteArtifactBinding:
    try:
        return _BINDINGS[(route_id, stage_id)]
    except KeyError as exc:
        raise ValueError(
            f"No Phase 32 Artifact contract for {route_id}/{stage_id}"
        ) from exc


__all__ = [
    "BeatBoardArtifact",
    "BeatBoardBeat",
    "BookDeliveryArtifact",
    "BookArchitectureArtifact",
    "ChapterArtifact",
    "CharacterBibleArtifact",
    "CharacterRecord",
    "CharacterRelationship",
    "CoverArtifact",
    "CoverBrief",
    "CoverCandidate",
    "DetailChapterPlan",
    "DetailPlanIndexArtifact",
    "DetailScenePlan",
    "DetailWindow",
    "NovelBriefArtifact",
    "PartContract",
    "Phase32Artifact",
    "Phase32CoreArtifact",
    "Phase32PlanningArtifact",
    "RouteArtifactBinding",
    "ScreenplayBlock",
    "ScreenplayBlockKind",
    "ScreenplayDraftArtifact",
    "SceneDeckArtifact",
    "SceneDeckScene",
    "ScreenplayBriefArtifact",
    "ScriptDeliveryArtifact",
    "SectionPlanArtifact",
    "SectionPlanUnit",
    "ShortProseUnitArtifact",
    "StoryMapAnchor",
    "StoryMapArtifact",
    "VolumeArchitectureArtifact",
    "VolumeContract",
    "bind_phase32_artifact",
    "DeliveryFormat",
    "phase32_artifact_binding",
    "validate_long_novel_hierarchy",
    "validate_rolling_detail_references",
    "validate_scene_deck_references",
    "validate_scene_contiguous_boundary",
    "validate_section_plan_references",
    "validate_story_map_promise_references",
    "validate_volume_architecture_references",
]
