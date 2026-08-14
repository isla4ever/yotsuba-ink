from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


StageId = Literal[
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
]

STAGE_ORDER: tuple[StageId, ...] = (
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
)

STAGE_LABELS: dict[StageId, str] = {
    "brief": "创作立项",
    "spine": "故事脊柱",
    "cast": "人物编排",
    "volumes": "分卷架构",
    "detail": "章节施工图",
    "text": "正文",
    "cover": "封面",
    "export": "导出",
}


def stage_pointer(stage_id: StageId) -> dict[str, str]:
    return {"id": stage_id, "label": STAGE_LABELS[stage_id], "type": stage_id}


class StrictArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LengthEnvelope(StrictArtifact):
    word_target_soft: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    chapter_target_soft: Optional[int] = Field(default=None, ge=1, le=10_000)


class StoryBriefArtifact(StrictArtifact):
    title: str = Field(min_length=1, max_length=200)
    premise: str = Field(min_length=1, max_length=2000)
    promise: str = Field(min_length=1, max_length=1000)
    world_rules: list[str] = Field(min_length=1, max_length=24)
    theme: str = Field(min_length=1, max_length=600)
    ending_promise: str = Field(min_length=1, max_length=1000)
    voice: str = Field(min_length=1, max_length=600)
    length_envelope: LengthEnvelope


class SpineTurn(StrictArtifact):
    id: str = Field(pattern=r"^turn-[1-9][0-9]*$")
    cause: str = Field(min_length=1, max_length=1200)
    change: str = Field(min_length=1, max_length=1200)


class SpineTurnDraft(StrictArtifact):
    cause: str = Field(min_length=1, max_length=1200)
    change: str = Field(min_length=1, max_length=1200)


class StorySpineArtifact(StrictArtifact):
    turns: list[SpineTurn] = Field(min_length=1, max_length=120)
    ending: str = Field(min_length=1, max_length=1600)
    open_questions: list[str] = Field(max_length=16)
    progress_types: list[Literal["information", "relationship", "external", "internal"]] = Field(
        min_length=1, max_length=4
    )

    @model_validator(mode="after")
    def unique_turns(self) -> "StorySpineArtifact":
        ids = [turn.id for turn in self.turns]
        if ids != [f"turn-{index}" for index in range(1, len(ids) + 1)]:
            raise ValueError("Spine turn ids must be deterministic and contiguous")
        return self


class StorySpineDraftArtifact(StrictArtifact):
    turns: list[SpineTurnDraft] = Field(min_length=1, max_length=120)
    ending: str = Field(min_length=1, max_length=1600)
    open_questions: list[str] = Field(max_length=16)
    progress_types: list[Literal["information", "relationship", "external", "internal"]] = Field(
        min_length=1, max_length=4
    )


class RoleDemandProposal(StrictArtifact):
    demand_key: str = Field(pattern=r"^demand-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    function: str = Field(min_length=1, max_length=400)
    required_change: str = Field(min_length=1, max_length=600)
    # A principal role can legitimately stay active across every spine turn,
    # so this cap must track StorySpineArtifact.turns (max 120), not a fixed dozen.
    active_turn_refs: list[str] = Field(min_length=1, max_length=120)


class CastDemand(StrictArtifact):
    """Rebuildable pressure diagnostic, never a character-count authority."""

    subject_id: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    pressure: int = Field(ge=0, le=200)
    signals: list[str] = Field(max_length=12)
    recommendation: Literal["keep", "split", "merge", "review"]


class VolumeBoundaryProposal(StrictArtifact):
    boundary_key: str = Field(pattern=r"^boundary-[1-9][0-9]*$")
    # One volume may absorb most of a long spine; keep in step with the 120-turn ceiling.
    turn_refs: list[str] = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)


class RoleDemandProposalBatch(StrictArtifact):
    proposals: list[RoleDemandProposal] = Field(min_length=1, max_length=24)


class VolumeBoundaryProposalBatch(StrictArtifact):
    proposals: list[VolumeBoundaryProposal] = Field(min_length=1, max_length=24)


class ContextSnippet(StrictArtifact):
    ref: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=12_000)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ContextBudget(StrictArtifact):
    input_chars: int = Field(ge=1, le=500_000)
    output_tokens: int = Field(ge=1, le=1_000_000)


class ContextManifest(StrictArtifact):
    task: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    required: list[str] = Field(min_length=1, max_length=8)
    optional: list[str] = Field(max_length=12)
    forbidden: list[str] = Field(min_length=1, max_length=12)
    snippets: list[ContextSnippet] = Field(max_length=16)
    budget: ContextBudget
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_integrity(self) -> "ContextManifest":
        required = self.required
        optional = self.optional
        if len(required) != len(set(required)) or len(optional) != len(set(optional)):
            raise ValueError("Context Manifest refs must be unique")
        if set(required) & set(optional):
            raise ValueError("Context Manifest required and optional refs must be disjoint")
        snippet_refs = [snippet.ref for snippet in self.snippets]
        if len(snippet_refs) != len(set(snippet_refs)):
            raise ValueError("Context Manifest snippet refs must be unique")
        if set(snippet_refs) != set(required) | set(optional):
            raise ValueError("Context Manifest refs must match its snippets exactly")
        if any(_content_hash(snippet.text) != snippet.source_hash for snippet in self.snippets):
            raise ValueError("Context Manifest source hash does not match snippet text")
        if self.budget.input_chars != sum(len(snippet.text) for snippet in self.snippets):
            raise ValueError("Context Manifest input character budget does not match snippets")
        payload = self.model_dump(mode="json", exclude={"manifest_hash"})
        if _content_hash(_canonical_json(payload)) != self.manifest_hash:
            raise ValueError("Context Manifest hash does not match its signed payload")
        return self


CharacterKind = Literal["protagonist", "major", "functional", "npc", "historical_record"]


class CharacterSubject(StrictArtifact):
    id: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    name: str = Field(min_length=1, max_length=120)
    kind: CharacterKind
    function: str = Field(min_length=1, max_length=500)
    drive: str = Field(min_length=1, max_length=600)
    change: str = Field(min_length=1, max_length=600)
    debut: str = Field(pattern=r"^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$")
    limits: list[str] = Field(min_length=1, max_length=16)
    demand_refs: list[str] = Field(min_length=1, max_length=8)


class CharacterDossier(StrictArtifact):
    """Provider-authored dossier; the runtime binds its preallocated subject id."""

    name: str = Field(min_length=1, max_length=120)
    kind: CharacterKind
    function: str = Field(min_length=1, max_length=500)
    drive: str = Field(min_length=1, max_length=600)
    change: str = Field(min_length=1, max_length=600)
    debut: str = Field(pattern=r"^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$")
    limits: list[str] = Field(min_length=1, max_length=16)
    demand_refs: list[str] = Field(min_length=1, max_length=8)


class CharacterDossierBatch(StrictArtifact):
    subjects: list[CharacterDossier] = Field(min_length=1, max_length=24)


class CharacterRelation(StrictArtifact):
    a: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    b: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    type: str = Field(min_length=1, max_length=160)
    pressure: str = Field(min_length=1, max_length=500)


class CharacterRelationBatch(StrictArtifact):
    relations: list[CharacterRelation] = Field(max_length=360)


class CharacterBibleArtifact(StrictArtifact):
    subjects: list[CharacterSubject] = Field(min_length=1, max_length=120)
    relations: list[CharacterRelation] = Field(max_length=360)

    @model_validator(mode="after")
    def validate_registry(self) -> "CharacterBibleArtifact":
        ids = [subject.id for subject in self.subjects]
        if len(ids) != len(set(ids)):
            raise ValueError("Character subject ids must be unique")
        if not any(subject.kind == "protagonist" for subject in self.subjects):
            raise ValueError("Character Bible must register at least one protagonist")
        known = set(ids)
        for relation in self.relations:
            if relation.a == relation.b or relation.a not in known or relation.b not in known:
                raise ValueError("Character relations must reference two registered subjects")
        return self


class VolumeContract(StrictArtifact):
    id: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    # Default keeps artifacts from runs created before volume titles existed
    # readable; new generations enforce a non-empty title at unit validation.
    title: str = Field(default="", max_length=80)
    promise: str = Field(min_length=1, max_length=1000)
    conflict: str = Field(min_length=1, max_length=1000)
    climax: str = Field(min_length=1, max_length=1200)
    closure: str = Field(min_length=1, max_length=1200)
    # Keep in step with the 120-turn spine ceiling: one volume may own most turns.
    turn_refs: list[str] = Field(min_length=1, max_length=120)
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    thread_ids: list[str] = Field(max_length=40)
    length_hint: Literal["short", "medium", "long"]


class VolumeContractDraft(StrictArtifact):
    title: str = Field(default="", max_length=80)
    promise: str = Field(min_length=1, max_length=1000)
    conflict: str = Field(min_length=1, max_length=1000)
    climax: str = Field(min_length=1, max_length=1200)
    closure: str = Field(min_length=1, max_length=1200)
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    thread_ids: list[str] = Field(max_length=40)
    length_hint: Literal["short", "medium", "long"]


class VolumeArchitectureDraftArtifact(StrictArtifact):
    volumes: list[VolumeContractDraft] = Field(min_length=1, max_length=24)


class VolumeArchitectureArtifact(StrictArtifact):
    volumes: list[VolumeContract] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def unique_and_contiguous(self) -> "VolumeArchitectureArtifact":
        ids = [volume.id for volume in self.volumes]
        if ids != [f"volume-{index}" for index in range(1, len(ids) + 1)]:
            raise ValueError("Volume ids must be deterministic and contiguous")
        return self


class DetailScene(StrictArtifact):
    place: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=700)
    conflict: str = Field(min_length=1, max_length=700)
    turn: str = Field(min_length=1, max_length=700)
    result: str = Field(min_length=1, max_length=700)


class DetailChapter(StrictArtifact):
    ref: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    # The chapter title is decided at the detail stage (the only stage that
    # knows what the chapter is about) and flows into the prose artifact.
    title: str = Field(default="", max_length=80)
    purpose: str = Field(min_length=1, max_length=1000)
    pov: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    scenes: list[DetailScene] = Field(min_length=1, max_length=8)
    handoff: str = Field(min_length=1, max_length=800)

    @model_validator(mode="after")
    def validate_cast(self) -> "DetailChapter":
        _validate_chapter_cast(self.pov, self.cast_ids)
        return self


class DetailArtifact(StrictArtifact):
    chapters: list[DetailChapter] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def unique_chapters(self) -> "DetailArtifact":
        refs = [chapter.ref for chapter in self.chapters]
        if refs != [f"chapter-{index}" for index in range(1, len(refs) + 1)]:
            raise ValueError("Detail chapter refs must be deterministic and contiguous")
        return self


class DetailSegmentChapter(StrictArtifact):
    title: str = Field(default="", max_length=80)
    purpose: str = Field(min_length=1, max_length=1000)
    pov: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    scenes: list[DetailScene] = Field(min_length=1, max_length=8)
    handoff: str = Field(min_length=1, max_length=800)

    @model_validator(mode="after")
    def validate_cast(self) -> "DetailSegmentChapter":
        _validate_chapter_cast(self.pov, self.cast_ids)
        return self


class DetailSegmentArtifact(StrictArtifact):
    chapters: list[DetailSegmentChapter] = Field(min_length=1, max_length=200)


class ChapterArtifact(StrictArtifact):
    chapter_id: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
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


class ExportVolume(StrictArtifact):
    """Volume grouping for delivery rendering: consecutive chapters per volume."""

    title: str = Field(default="", max_length=80)
    chapter_count: int = Field(ge=1)


class ExportArtifact(StrictArtifact):
    format: Literal["md", "json", "zip"]
    chapter_version_ids: list[str] = Field(min_length=1)
    cover_asset_id: str = Field(max_length=200)
    metadata: ExportMetadata
    # Empty for runs exported before volume grouping existed.
    volumes: list[ExportVolume] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def validate_volume_grouping(self) -> "ExportArtifact":
        if self.volumes:
            counted = sum(volume.chapter_count for volume in self.volumes)
            if counted != len(self.chapter_version_ids):
                raise ValueError("Export volume grouping must cover every chapter exactly once")
        return self


ARTIFACT_MODELS: dict[StageId, type[StrictArtifact]] = {
    "brief": StoryBriefArtifact,
    "spine": StorySpineArtifact,
    "cast": CharacterBibleArtifact,
    "volumes": VolumeArchitectureArtifact,
    "detail": DetailArtifact,
    "text": ChapterArtifact,
    "cover": CoverArtifact,
    "export": ExportArtifact,
}


def validate_artifact_vnext(
    stage_id: StageId,
    payload: Any,
    *,
    subject_ids: set[str] | None = None,
    chapter_refs: set[str] | None = None,
    demand_keys: set[str] | None = None,
    turn_ids: set[str] | None = None,
    volume_cast_ids: dict[str, set[str]] | None = None,
    cover_asset_ids: set[str] | None = None,
    chapter_version_ids: list[str] | None = None,
    export_title: str | None = None,
    **_: Any,
) -> StrictArtifact:
    artifact = ARTIFACT_MODELS[stage_id].model_validate(payload)
    known_subjects = subject_ids or set()
    if isinstance(artifact, CharacterBibleArtifact):
        known = {item.id for item in artifact.subjects}
        if demand_keys is not None:
            referenced_demands = {
                demand_ref for item in artifact.subjects for demand_ref in item.demand_refs
            }
            unknown_demands = referenced_demands - demand_keys
            if unknown_demands:
                raise ValueError(f"Character Bible references unknown role demands: {sorted(unknown_demands)}")
            missing_demands = demand_keys - referenced_demands
            if missing_demands:
                raise ValueError(f"Character Bible does not cover role demands: {sorted(missing_demands)}")
        if chapter_refs is not None and any(
            _chapter_end(item.debut) > len(chapter_refs) for item in artifact.subjects
        ):
            raise ValueError("Character debut windows exceed the frozen detail range")
        if known_subjects and not known.issubset(known_subjects):
            raise ValueError("Character Bible introduced a subject outside the frozen registry")
    if isinstance(artifact, VolumeArchitectureArtifact):
        if turn_ids is not None:
            unknown_turns = {
                turn_ref
                for volume in artifact.volumes
                for turn_ref in volume.turn_refs
                if turn_ref not in turn_ids
            }
            if unknown_turns:
                raise ValueError(f"Volume references unknown spine turns: {sorted(unknown_turns)}")
        if known_subjects:
            unknown = {
                subject_id
                for volume in artifact.volumes
                for subject_id in volume.cast_ids
                if subject_id not in known_subjects
            }
            if unknown:
                raise ValueError(f"Volume references unknown subjects: {sorted(unknown)}")
    if isinstance(artifact, DetailArtifact):
        if known_subjects:
            unknown = {
                subject_id
                for item in artifact.chapters
                for subject_id in item.cast_ids
            } - known_subjects
            if unknown:
                raise ValueError(f"Detail references unknown subjects: {sorted(unknown)}")
        if volume_cast_ids is not None:
            for item in artifact.chapters:
                allowed = volume_cast_ids.get(item.volume_ref)
                if allowed is None:
                    raise ValueError(f"Detail references unknown volume: {item.volume_ref}")
                outside_volume = set(item.cast_ids) - allowed
                if outside_volume:
                    raise ValueError(
                        f"Detail chapter references subjects outside {item.volume_ref}: {sorted(outside_volume)}"
                    )
        if chapter_refs is not None and {item.ref for item in artifact.chapters} != chapter_refs:
            raise ValueError("Detail chapters must match the frozen chapter refs")
    if isinstance(artifact, CoverArtifact) and artifact.selected_asset_id:
        if cover_asset_ids is not None and artifact.selected_asset_id not in cover_asset_ids:
            raise ValueError("Cover selects an asset outside the immutable candidate set")
    if isinstance(artifact, ExportArtifact):
        if chapter_version_ids is not None and artifact.chapter_version_ids != chapter_version_ids:
            raise ValueError("Export chapter versions must match the accepted manuscript")
        if cover_asset_ids is not None and artifact.cover_asset_id not in cover_asset_ids:
            raise ValueError("Export references an unknown cover asset")
        if export_title is not None and artifact.metadata.title != export_title:
            raise ValueError("Export title must match the committed brief")
    return artifact


def _chapter_end(window: str) -> int:
    bounds = window.removeprefix("chapter:").split("-", maxsplit=1)
    return int(bounds[-1])


def _validate_chapter_cast(pov: str, cast_ids: list[str]) -> None:
    if len(cast_ids) != len(set(cast_ids)):
        raise ValueError("Detail chapter cast ids must be unique")
    if pov not in cast_ids:
        raise ValueError("Detail chapter cast ids must include its POV")


def _canonical_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def required_cast_subject_ids(artifact: CharacterBibleArtifact) -> set[str]:
    return {subject.id for subject in artifact.subjects}


__all__ = [
    "ARTIFACT_MODELS",
    "CharacterBibleArtifact",
    "CastDemand",
    "CharacterDossier",
    "CharacterDossierBatch",
    "ContextBudget",
    "CharacterRelation",
    "CharacterRelationBatch",
    "CharacterSubject",
    "ChapterArtifact",
    "DetailArtifact",
    "DetailChapter",
    "DetailScene",
    "DetailSegmentChapter",
    "DetailSegmentArtifact",
    "ExportArtifact",
    "ExportMetadata",
    "CoverArtifact",
    "CoverBrief",
    "ContextManifest",
    "ContextSnippet",
    "LengthEnvelope",
    "RoleDemandProposal",
    "RoleDemandProposalBatch",
    "SpineTurn",
    "SpineTurnDraft",
    "StageId",
    "STAGE_LABELS",
    "STAGE_ORDER",
    "StoryBriefArtifact",
    "StorySpineArtifact",
    "StorySpineDraftArtifact",
    "StrictArtifact",
    "VolumeArchitectureArtifact",
    "VolumeArchitectureDraftArtifact",
    "VolumeBoundaryProposal",
    "VolumeBoundaryProposalBatch",
    "VolumeContract",
    "VolumeContractDraft",
    "required_cast_subject_ids",
    "stage_pointer",
    "validate_artifact_vnext",
]
