from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StageId = Literal[
    "info",
    "characters",
    "summary",
    "outline",
    "detail",
    "text",
    "cover",
    "export",
]

STAGE_ORDER: tuple[StageId, ...] = (
    "info",
    "characters",
    "summary",
    "outline",
    "detail",
    "text",
    "cover",
    "export",
)

STAGE_LABELS: dict[StageId, str] = {
    "info": "创作立项",
    "characters": "人物编排",
    "summary": "全书梗概",
    "outline": "分卷大纲",
    "detail": "章节施工图",
    "text": "正文",
    "cover": "封面",
    "export": "导出",
}


def stage_pointer(stage_id: StageId) -> dict[str, str]:
    return {"id": stage_id, "label": STAGE_LABELS[stage_id], "type": stage_id}


class StrictArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StoryPromise(StrictArtifact):
    genre: str = Field(min_length=1, max_length=120)
    audience: str = Field(min_length=1, max_length=160)
    tone: str = Field(min_length=1, max_length=240)


class NarrativeVoice(StrictArtifact):
    viewpoint: str = Field(min_length=1, max_length=120)
    tense: str = Field(min_length=1, max_length=80)
    texture: str = Field(min_length=1, max_length=500)
    avoid: list[str] = Field(max_length=30)


class CastRequirement(StrictArtifact):
    function: str = Field(min_length=1, max_length=240)
    importance: Literal["protagonist", "major", "functional", "npc"]


class StoryBriefArtifact(StrictArtifact):
    title: str = Field(min_length=1, max_length=200)
    premise: str = Field(min_length=1, max_length=2000)
    story_promise: StoryPromise
    world_rules: list[str] = Field(min_length=1, max_length=40)
    thematic_question: str = Field(min_length=1, max_length=500)
    ending_promise: str = Field(min_length=1, max_length=1000)
    voice: NarrativeVoice
    cast_requirements: list[CastRequirement] = Field(max_length=40)


CharacterTier = Literal["protagonist", "major", "functional"]


class CharacterArc(StrictArtifact):
    start: str = Field(min_length=1, max_length=500)
    turning_point: str = Field(min_length=1, max_length=500)
    end: str = Field(min_length=1, max_length=500)


class CharacterRecord(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    name: str = Field(min_length=1, max_length=120)
    tier: CharacterTier
    narrative_function: str = Field(min_length=1, max_length=500)
    external_goal: str = Field(min_length=1, max_length=500)
    inner_need: str = Field(min_length=1, max_length=500)
    arc: CharacterArc
    first_appearance_window: str = Field(
        pattern=r"^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$"
    )
    hard_boundaries: list[str] = Field(max_length=30)

    @field_validator("first_appearance_window")
    @classmethod
    def validate_appearance_window(cls, value: str) -> str:
        return _validate_appearance_window(value)


class CharacterRelationship(StrictArtifact):
    source_id: str = Field(min_length=1, max_length=120)
    target_id: str = Field(min_length=1, max_length=120)
    nature: str = Field(min_length=1, max_length=240)
    initial_state: str = Field(min_length=1, max_length=500)
    pressure: str = Field(min_length=1, max_length=500)


class NpcSlot(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    function: str = Field(min_length=1, max_length=500)
    first_appearance_window: str = Field(
        pattern=r"^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$"
    )
    limits: list[str] = Field(max_length=30)

    @field_validator("first_appearance_window")
    @classmethod
    def validate_appearance_window(cls, value: str) -> str:
        return _validate_appearance_window(value)


class CharacterBibleArtifact(StrictArtifact):
    characters: list[CharacterRecord] = Field(min_length=1, max_length=80)
    relationships: list[CharacterRelationship] = Field(max_length=300)
    npc_slots: list[NpcSlot] = Field(max_length=120)

    @model_validator(mode="after")
    def validate_registry(self) -> "CharacterBibleArtifact":
        character_ids = [item.id for item in self.characters]
        slot_ids = [item.id for item in self.npc_slots]
        if len(character_ids) != len(set(character_ids)):
            raise ValueError("Character ids must be unique")
        if len(slot_ids) != len(set(slot_ids)) or set(character_ids) & set(slot_ids):
            raise ValueError("NPC slot ids must be unique and distinct from character ids")
        known = set(character_ids)
        if not any(item.tier == "protagonist" for item in self.characters):
            raise ValueError("Character Bible must register at least one protagonist")
        for relation in self.relationships:
            if relation.source_id == relation.target_id:
                raise ValueError("A character relationship cannot target itself")
            if relation.source_id not in known or relation.target_id not in known:
                raise ValueError("Character relationships must reference registered characters")
        return self


class SummaryBeat(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    phase: str = Field(min_length=1, max_length=120)
    event: str = Field(min_length=1, max_length=1000)
    consequence: str = Field(min_length=1, max_length=1000)


class CharacterOutcome(StrictArtifact):
    character_id: str = Field(min_length=1, max_length=120)
    outcome: str = Field(min_length=1, max_length=1000)


class SummaryArtifact(StrictArtifact):
    beats: list[SummaryBeat] = Field(min_length=1, max_length=80)
    climax: str = Field(min_length=1, max_length=1500)
    resolution: str = Field(min_length=1, max_length=1500)
    character_outcomes: list[CharacterOutcome] = Field(max_length=80)

    @model_validator(mode="after")
    def validate_summary_registry(self) -> "SummaryArtifact":
        _require_unique([item.id for item in self.beats], "Summary beat ids")
        _require_unique(
            [item.character_id for item in self.character_outcomes],
            "Summary character outcomes",
        )
        return self


class VolumeTurn(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    event: str = Field(min_length=1, max_length=1000)
    consequence: str = Field(min_length=1, max_length=1000)


class CharacterWindow(StrictArtifact):
    character_id: str = Field(min_length=1, max_length=120)
    entry_state: str = Field(min_length=1, max_length=500)
    exit_state: str = Field(min_length=1, max_length=500)
    turn_id: str = Field(min_length=1, max_length=120)


class ThreadWindow(StrictArtifact):
    thread_id: str = Field(min_length=1, max_length=120)
    kind: Literal["plot", "relationship", "mystery", "foreshadow"]
    action: str = Field(min_length=1, max_length=500)
    chapter_window: str = Field(min_length=1, max_length=120)


class VolumePlan(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    chapter_window: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=1000)
    turns: list[VolumeTurn] = Field(min_length=1, max_length=40)
    ending_state: str = Field(min_length=1, max_length=1000)
    character_windows: list[CharacterWindow] = Field(max_length=120)
    thread_windows: list[ThreadWindow] = Field(max_length=120)

    @model_validator(mode="after")
    def validate_volume_registry(self) -> "VolumePlan":
        _chapter_window(self.chapter_window)
        turn_ids = [item.id for item in self.turns]
        _require_unique(turn_ids, "Volume turn ids")
        known_turns = set(turn_ids)
        unknown_turns = {
            item.turn_id for item in self.character_windows if item.turn_id not in known_turns
        }
        if unknown_turns:
            raise ValueError(
                f"Character windows reference unknown turns: {sorted(unknown_turns)}"
            )
        _require_unique(
            [item.character_id for item in self.character_windows],
            "Volume character windows",
        )
        for item in self.thread_windows:
            start, end = _chapter_window(item.chapter_window)
            volume_start, volume_end = _chapter_window(self.chapter_window)
            if start < volume_start or end > volume_end:
                raise ValueError("Thread windows must stay inside their volume chapter window")
        return self


class OutlineArtifact(StrictArtifact):
    volumes: list[VolumePlan] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_volume_windows(self) -> "OutlineArtifact":
        _require_unique([item.id for item in self.volumes], "Outline volume ids")
        expected_start = 1
        for volume in self.volumes:
            start, end = _chapter_window(volume.chapter_window)
            if start != expected_start:
                raise ValueError("Outline volume windows must be contiguous and start at chapter one")
            expected_start = end + 1
        return self


class ScenePlan(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    location: str = Field(min_length=1, max_length=300)
    goal: str = Field(min_length=1, max_length=700)
    obstacle: str = Field(min_length=1, max_length=700)
    turn: str = Field(min_length=1, max_length=700)
    outcome: str = Field(min_length=1, max_length=700)


class ChapterObligation(StrictArtifact):
    kind: Literal["character", "thread", "world_rule", "promise"]
    ref_id: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=500)


class ChapterHandoff(StrictArtifact):
    unresolved_actions: list[str] = Field(max_length=30)
    emotional_carryover: list[str] = Field(max_length=30)
    next_pressure: str = Field(max_length=700)


class ChapterPlan(StrictArtifact):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
    number: int = Field(ge=1)
    purpose: str = Field(min_length=1, max_length=1000)
    pov_character_id: str = Field(min_length=1, max_length=120)
    scenes: list[ScenePlan] = Field(min_length=1, max_length=3)
    obligations: list[ChapterObligation] = Field(max_length=40)
    handoff: ChapterHandoff


class DetailArtifact(StrictArtifact):
    chapters: list[ChapterPlan] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_chapters(self) -> "DetailArtifact":
        ids = [item.id for item in self.chapters]
        numbers = [item.number for item in self.chapters]
        if len(ids) != len(set(ids)):
            raise ValueError("Chapter ids must be unique")
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Chapter numbers must be contiguous and start at one")
        for chapter in self.chapters:
            if chapter.id != f"chapter-{chapter.number}":
                raise ValueError("Chapter ids must match their frozen chapter number")
            _require_unique(
                [scene.id for scene in chapter.scenes],
                f"Scene ids in {chapter.id}",
            )
        return self


class ChapterArtifact(StrictArtifact):
    chapter_id: str = Field(min_length=1, max_length=120)
    version_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)
    author_status: Literal["candidate", "accepted", "edited", "branched"]


class CoverBrief(StrictArtifact):
    concept: str = Field(min_length=1, max_length=1000)
    image_prompt: str = Field(min_length=1, max_length=3000)
    palette: list[str] = Field(min_length=1, max_length=6)
    negative_constraints: list[str] = Field(max_length=16)


class CoverArtifact(StrictArtifact):
    brief: CoverBrief
    selected_asset_id: str = Field(max_length=200)


class ExportMetadata(StrictArtifact):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(max_length=160)
    version_note: str = Field(max_length=500)


class ExportArtifact(StrictArtifact):
    format: Literal["md", "json", "zip"]
    chapter_version_ids: list[str] = Field(min_length=1)
    cover_asset_id: str = Field(max_length=200)
    metadata: ExportMetadata


ARTIFACT_MODELS: dict[StageId, type[StrictArtifact]] = {
    "info": StoryBriefArtifact,
    "characters": CharacterBibleArtifact,
    "summary": SummaryArtifact,
    "outline": OutlineArtifact,
    "detail": DetailArtifact,
    "text": ChapterArtifact,
    "cover": CoverArtifact,
    "export": ExportArtifact,
}


def _validate_appearance_window(value: str) -> str:
    bounds = value.removeprefix("chapter:").split("-", maxsplit=1)
    if len(bounds) == 2 and int(bounds[1]) < int(bounds[0]):
        raise ValueError("Character appearance window must be ordered")
    return value


def validate_artifact_vnext(
    stage_id: StageId,
    payload: Any,
    *,
    character_ids: set[str] | None = None,
    required_outcome_character_ids: set[str] | None = None,
    npc_slot_ids: set[str] | None = None,
    obligation_ref_ids: dict[str, set[str]] | None = None,
    chapter_ids: set[str] | None = None,
    chapter_version_ids: list[str] | None = None,
    cover_asset_ids: set[str] | None = None,
    export_title: str | None = None,
) -> StrictArtifact:
    artifact = ARTIFACT_MODELS[stage_id].model_validate(payload)
    known_characters = character_ids or set()
    if isinstance(artifact, CharacterBibleArtifact) and chapter_ids is not None:
        total_chapters = len(chapter_ids)
        windows = [
            *(item.first_appearance_window for item in artifact.characters),
            *(item.first_appearance_window for item in artifact.npc_slots),
        ]
        if any(_chapter_window(value)[1] > total_chapters for value in windows):
            raise ValueError("Character appearance windows must stay inside the frozen BookScalePlan")
    if isinstance(artifact, SummaryArtifact) and known_characters:
        unknown = {item.character_id for item in artifact.character_outcomes} - known_characters
        if unknown:
            raise ValueError(f"Summary references unknown characters: {sorted(unknown)}")
    if isinstance(artifact, SummaryArtifact) and required_outcome_character_ids:
        missing = required_outcome_character_ids - {
            item.character_id for item in artifact.character_outcomes
        }
        if missing:
            raise ValueError(
                f"Summary is missing required character outcomes: {sorted(missing)}"
            )
    if isinstance(artifact, OutlineArtifact) and known_characters:
        unknown = {
            item.character_id
            for volume in artifact.volumes
            for item in volume.character_windows
        } - known_characters
        if unknown:
            raise ValueError(f"Outline references unknown characters: {sorted(unknown)}")
        if chapter_ids is not None:
            covered = {
                f"chapter-{number}"
                for volume in artifact.volumes
                for number in range(
                    _chapter_window(volume.chapter_window)[0],
                    _chapter_window(volume.chapter_window)[1] + 1,
                )
            }
            if covered != chapter_ids:
                raise ValueError("Outline volume windows must exactly cover the frozen BookScalePlan")
    if isinstance(artifact, DetailArtifact):
        if known_characters:
            unknown = {item.pov_character_id for item in artifact.chapters} - known_characters
            if unknown:
                raise ValueError(f"Detail references unknown POV characters: {sorted(unknown)}")
            registered_refs = known_characters | (npc_slot_ids or set())
            unknown_obligations = {
                obligation.ref_id
                for chapter in artifact.chapters
                for obligation in chapter.obligations
                if obligation.kind == "character" and obligation.ref_id not in registered_refs
            }
            if unknown_obligations:
                raise ValueError(
                    f"Detail references unknown character obligations: {sorted(unknown_obligations)}"
                )
        if obligation_ref_ids is not None:
            unknown_by_kind = {
                kind: sorted({
                    obligation.ref_id
                    for chapter in artifact.chapters
                    for obligation in chapter.obligations
                    if obligation.kind == kind
                    and obligation.ref_id not in allowed
                })
                for kind, allowed in obligation_ref_ids.items()
            }
            unknown_by_kind = {
                kind: values for kind, values in unknown_by_kind.items() if values
            }
            if unknown_by_kind:
                raise ValueError(
                    f"Detail references unknown frozen obligations: {unknown_by_kind}"
                )
        if chapter_ids is not None and {item.id for item in artifact.chapters} != chapter_ids:
            raise ValueError("Detail chapters must exactly match the frozen BookScalePlan")
    if isinstance(artifact, CoverArtifact) and artifact.selected_asset_id:
        if cover_asset_ids is not None and artifact.selected_asset_id not in cover_asset_ids:
            raise ValueError("Cover selects an asset outside the active immutable candidate set")
    if isinstance(artifact, ExportArtifact):
        if chapter_version_ids is not None and artifact.chapter_version_ids != chapter_version_ids:
            raise ValueError("Export chapter versions must exactly match the accepted manuscript")
        if artifact.cover_asset_id and cover_asset_ids is not None:
            if artifact.cover_asset_id not in cover_asset_ids:
                raise ValueError("Export references an unknown immutable cover asset")
        if export_title is not None and artifact.metadata.title != export_title:
            raise ValueError("Export title must match the committed Story Brief")
    return artifact


def required_summary_outcome_ids(artifact: CharacterBibleArtifact) -> set[str]:
    return {
        item.id for item in artifact.characters if item.tier in {"protagonist", "major"}
    }


def detail_obligation_registry(
    story: StoryBriefArtifact,
    characters: CharacterBibleArtifact,
    outline: OutlineArtifact,
) -> dict[str, list[dict[str, str]]]:
    character_refs = [
        {"id": item.id, "label": item.name}
        for item in characters.characters
    ] + [
        {"id": item.id, "label": f"NPC: {item.function}"}
        for item in characters.npc_slots
    ]
    thread_refs: dict[str, str] = {}
    for volume in outline.volumes:
        for item in volume.thread_windows:
            thread_refs.setdefault(item.thread_id, item.action)
    return {
        "character": character_refs,
        "thread": [
            {"id": key, "label": value}
            for key, value in sorted(thread_refs.items())
        ],
        "world_rule": [
            {"id": f"world-rule-{index}", "label": value}
            for index, value in enumerate(story.world_rules, start=1)
        ],
        "promise": [
            {"id": "thematic-question", "label": story.thematic_question},
            {"id": "ending-promise", "label": story.ending_promise},
        ],
    }


def detail_obligation_ref_ids(
    story: StoryBriefArtifact,
    characters: CharacterBibleArtifact,
    outline: OutlineArtifact,
) -> dict[str, set[str]]:
    return {
        kind: {item["id"] for item in items}
        for kind, items in detail_obligation_registry(
            story,
            characters,
            outline,
        ).items()
    }


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _chapter_window(value: str) -> tuple[int, int]:
    if not value.startswith("chapter:"):
        raise ValueError("Chapter windows must use chapter:N or chapter:N-M")
    match = value.removeprefix("chapter:").split("-", maxsplit=1)
    if not all(item.isdigit() and int(item) > 0 for item in match):
        raise ValueError("Chapter windows must use chapter:N or chapter:N-M")
    start = int(match[0])
    end = int(match[-1])
    if end < start:
        raise ValueError("Chapter windows must be ordered")
    return start, end
