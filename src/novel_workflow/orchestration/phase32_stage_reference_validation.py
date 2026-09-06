"""Cross-Artifact reference validation for Phase 32 planning stages."""

from __future__ import annotations

import re
from collections.abc import Mapping

from novel_workflow.output_contracts.phase32_route_artifacts import (
    BookArchitectureArtifact,
    CharacterBibleArtifact,
    ChapterArtifact,
    DetailPlanIndexArtifact,
    Phase32CoreArtifact,
    SceneDeckArtifact,
    ScreenplayDraftArtifact,
    SectionPlanArtifact,
    ShortProseUnitArtifact,
    StoryMapArtifact,
    VolumeArchitectureArtifact,
    validate_rolling_detail_references,
    validate_scene_contiguous_boundary,
    validate_scene_deck_references,
    validate_section_plan_references,
    validate_story_map_promise_references,
    validate_volume_architecture_references,
)
from novel_workflow.runtime.graph.chapter_scene_facts import (
    CHINESE_PERSON_NAME_PATTERN,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.phase32_scale import (
    ScaleProfile,
    validate_continuity_acceptance_chapter_counts,
)
from novel_workflow.workflows.phase32_short_prose import short_prose_unit_kind


class Phase32StageReferenceError(ValueError):
    """A planning Artifact references identity outside committed upstream state."""


_NAME_TOKEN = r"(?:[A-Za-z][A-Za-z0-9_-]{1,30}|[\u4e00-\u9fff]{2,8})"
_EXPLICIT_NAME_PATTERNS = (
    re.compile(rf"(?:姓名|名字)\s*[：:]\s*({_NAME_TOKEN})"),
    re.compile(
        rf"(?:姓名|名字)\s*(?:是|为|叫作|叫做)\s*"
        rf"(?!我|他|她|其|这|那|一)({_NAME_TOKEN})"
    ),
    re.compile(
        rf"(?:叫作|叫做|名为|称为)\s*"
        rf"(?!我|他|她|其|这|那|一)({_NAME_TOKEN})"
    ),
    re.compile(
        rf"({_NAME_TOKEN})\s*是(?:我|他|她|其)?(?:的)?"
        r"(?:妹妹|弟弟|姐姐|哥哥|母亲|父亲|女儿|儿子|妻子|丈夫|朋友|同事)的名字"
    ),
    re.compile(rf"输入[“\"]({_NAME_TOKEN})[”\"]"),
    re.compile(
        rf"(?:同事|用户|值班员|修复师|馆员|组长|导师)\s*"
        rf"(?:名叫|叫作|叫做|是|为)?\s*({CHINESE_PERSON_NAME_PATTERN.pattern})"
    ),
    re.compile(
        r"(?:同事|用户|值班员|修复师|馆员|组长|导师)\s*"
        r"(?:名叫|叫作|叫做|是|为)?\s*((?:小|老)[\u4e00-\u9fff])"
    ),
)

_NON_CHARACTER_NAME_PREFIXES = ("我", "他", "她", "其")


def _validate_explicit_character_names(
    content: str,
    cast: CharacterBibleArtifact,
    *,
    allowed_subject_refs: set[str] | None = None,
) -> None:
    """Reject strong identity markers that introduce an unregistered name.

    This is intentionally a narrow lexical guard, not a general Chinese NER
    system.  It catches the high-signal forms that previously leaked through
    long-novel smoke runs (for example ``姓名：林晚`` and ``输入“林晚”``) while
    leaving ordinary prose review to the literary-quality layer.
    """

    allowed = {
        character.display_name
        for character in cast.characters
        if allowed_subject_refs is None or character.subject_ref in allowed_subject_refs
    }
    unknown = {
        match.group(1).strip()
        for pattern in _EXPLICIT_NAME_PATTERNS
        for match in pattern.finditer(content)
        if match.group(1).strip()
        and not match.group(1).strip().startswith(_NON_CHARACTER_NAME_PREFIXES)
        and match.group(1).strip() not in allowed
    }
    if unknown:
        names = ", ".join(sorted(unknown))
        raise Phase32StageReferenceError(
            "Prose introduces an unregistered explicit character name: "
            f"{names}"
        )


def validate_phase32_stage_references(
    artifacts: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    artifact_refs: Mapping[str, str],
    stage_id: str,
    artifact: Phase32CoreArtifact,
    *,
    active_unit_ref: str = "",
) -> None:
    if stage_id not in {
        "story_map",
        "scene_deck",
        "script",
        "text",
        "section_plan",
        "volumes",
        "rolling_detail",
    }:
        return
    try:
        if stage_id == "story_map" and isinstance(artifact, StoryMapArtifact):
            validate_story_map_promise_references(artifact)
            return
        cast = CharacterBibleArtifact.model_validate(
            _read_committed_upstream(
                artifacts, definition, artifact_refs, "cast"
            ).payload
        )
        if stage_id == "scene_deck" and isinstance(artifact, SceneDeckArtifact):
            validate_scene_deck_references(artifact, cast)
            return
        if stage_id == "script" and isinstance(artifact, ScreenplayDraftArtifact):
            scene_deck = SceneDeckArtifact.model_validate(
                _read_committed_upstream(
                    artifacts, definition, artifact_refs, "scene_deck"
                ).payload
            )
            _validate_screenplay_scene(
                artifact,
                scene_deck,
                cast,
                active_unit_ref=active_unit_ref,
            )
            return
        if stage_id == "section_plan" and isinstance(
            artifact, SectionPlanArtifact
        ):
            story_map = StoryMapArtifact.model_validate(
                _read_committed_upstream(
                    artifacts, definition, artifact_refs, "story_map"
                ).payload
            )
            validate_section_plan_references(story_map, artifact, cast)
            return
        if stage_id == "text" and isinstance(artifact, ShortProseUnitArtifact):
            section_plan = SectionPlanArtifact.model_validate(
                _read_committed_upstream(
                    artifacts, definition, artifact_refs, "section_plan"
                ).payload
            )
            _validate_short_prose_unit(
                artifact,
                section_plan,
                cast,
                active_unit_ref=active_unit_ref,
                expected_unit_kind=short_prose_unit_kind(
                    definition.scale_profile.payload
                ),
            )
            return
        if stage_id == "text" and isinstance(artifact, ChapterArtifact):
            detail = DetailPlanIndexArtifact.model_validate(
                _read_committed_upstream(
                    artifacts, definition, artifact_refs, "rolling_detail"
                ).payload
            )
            _validate_long_novel_chapter(
                artifact,
                detail,
                cast,
                active_unit_ref=active_unit_ref,
            )
            return
        if stage_id == "volumes" and isinstance(
            artifact, VolumeArchitectureArtifact
        ):
            architecture = BookArchitectureArtifact.model_validate(
                _read_committed_upstream(
                    artifacts, definition, artifact_refs, "book_architecture"
                ).payload
            )
            validate_volume_architecture_references(architecture, artifact, cast)
            return
        if stage_id == "rolling_detail" and isinstance(
            artifact, DetailPlanIndexArtifact
        ):
            volumes = VolumeArchitectureArtifact.model_validate(
                _read_committed_upstream(
                    artifacts, definition, artifact_refs, "volumes"
                ).payload
            )
            validate_rolling_detail_references(volumes, artifact, cast)
            _validate_detail_registered_name_scope(artifact, cast)
            _validate_rolling_detail_scale(definition, artifact, volumes)
            return
        raise Phase32StageReferenceError(
            f"Artifact type does not match reference contract for {stage_id}"
        )
    except Phase32StageReferenceError:
        raise
    except Exception as exc:
        message = {
            "story_map": "Story Map Artifact does not expose a usable promise spine",
            "scene_deck": "Scene Deck Artifact does not match committed Cast references",
            "script": (
                "Screenplay Scene does not match the frozen Scene Deck and Cast references"
            ),
            "text": (
                "Chapter does not match the frozen Rolling Detail, Volume, and Cast references"
                if definition.creation_route_id == "long_novel"
                else "Short prose unit does not match the frozen Section Plan and Cast references"
            ),
            "section_plan": (
                "Section Plan Artifact does not match committed Story Map and Cast references"
            ),
            "volumes": "Volume Artifact does not match committed Part and Cast references",
            "rolling_detail": (
                "Rolling Detail Artifact does not match committed upstream references"
            ),
        }[stage_id]
        raise Phase32StageReferenceError(message) from exc


def _validate_rolling_detail_scale(
    definition: GraphRunDefinition,
    artifact: DetailPlanIndexArtifact,
    volumes: VolumeArchitectureArtifact,
) -> None:
    """Apply private frozen acceptance capacity without changing route policy."""

    if not definition.scale_profile.contract_id.startswith("length."):
        return
    profile = ScaleProfile.model_validate(definition.scale_profile.payload)
    try:
        validate_continuity_acceptance_chapter_counts(
            profile,
            window_chapter_counts=tuple(
                len(window.chapters) for window in artifact.windows
            ),
            window_volume_counts=tuple(
                len(window.volume_refs) for window in artifact.windows
            ),
        )
        if profile.profile_kind == "continuity_acceptance":
            expected_volume_ref = volumes.volumes[0].volume_ref
            actual_volume_refs = artifact.windows[0].volume_refs
            if actual_volume_refs != (expected_volume_ref,):
                raise ValueError(
                    "Continuity acceptance Rolling Detail must plan the first "
                    f"Volume prefix {expected_volume_ref}; received {actual_volume_refs}"
                )
            expected_subject_refs = set(volumes.volumes[0].cast_subject_refs)
            actual_subject_refs = {
                subject_ref
                for chapter in artifact.windows[0].chapters
                for subject_ref in chapter.cast_subject_refs
            }
            missing_subject_refs = sorted(expected_subject_refs - actual_subject_refs)
            if missing_subject_refs:
                raise ValueError(
                    "Continuity acceptance Rolling Detail does not cover the first "
                    f"Volume Cast scope: {missing_subject_refs}"
                )
    except ValueError as exc:
        raise Phase32StageReferenceError(str(exc)) from exc


def _validate_detail_registered_name_scope(
    artifact: DetailPlanIndexArtifact,
    cast: CharacterBibleArtifact,
) -> None:
    """Keep registered names inside the Chapter and Scene Cast boundaries."""

    names_by_ref = {
        character.subject_ref: character.display_name
        for character in cast.characters
    }
    for window in artifact.windows:
        for chapter in window.chapters:
            chapter_text = "\n".join(
                (
                    chapter.title,
                    chapter.dramatic_job,
                    chapter.entry_state,
                    chapter.conflict,
                    chapter.stakes,
                    chapter.exit_state,
                    chapter.hook,
                    chapter.handoff,
                    *(
                        value
                        for scene in chapter.scenes
                        for value in (
                            scene.location,
                            scene.time_context,
                            scene.goal,
                            scene.opposition,
                            scene.outcome,
                        )
                    ),
                )
            )
            allowed = set(chapter.cast_subject_refs)
            leaked = sorted(
                subject_ref
                for subject_ref, display_name in names_by_ref.items()
                if subject_ref not in allowed and display_name in chapter_text
            )
            if leaked:
                raise Phase32StageReferenceError(
                    f"Detail Chapter {chapter.chapter_ref} names registered subjects "
                    f"outside its Cast scope: {leaked}"
                )
            for scene in chapter.scenes:
                scene_text = "\n".join(
                    (
                        scene.location,
                        scene.time_context,
                        scene.goal,
                        scene.opposition,
                        scene.outcome,
                    )
                )
                scene_allowed = set(scene.cast_subject_refs)
                scene_leaked = sorted(
                    subject_ref
                    for subject_ref, display_name in names_by_ref.items()
                    if subject_ref not in scene_allowed and display_name in scene_text
                )
                if scene_leaked:
                    raise Phase32StageReferenceError(
                        f"Detail Scene {scene.scene_ref} names registered subjects "
                        f"outside its Cast scope: {scene_leaked}"
                    )


def _validate_screenplay_scene(
    artifact: ScreenplayDraftArtifact,
    scene_deck: SceneDeckArtifact,
    cast: CharacterBibleArtifact,
    *,
    active_unit_ref: str,
) -> None:
    scenes = {scene.scene_ref: scene for scene in scene_deck.scenes}
    scene = scenes.get(artifact.scene_ref)
    if scene is None:
        raise ValueError("Screenplay draft references an unknown Scene")
    validate_scene_contiguous_boundary(scene)
    if active_unit_ref and artifact.scene_ref != active_unit_ref:
        raise ValueError("Screenplay draft is outside the active Scene cursor")
    heading_blocks = [
        block for block in artifact.blocks if block.kind == "scene_heading"
    ]
    if len(heading_blocks) != 1:
        raise ValueError(
            "Screenplay draft must contain exactly one frozen Scene heading"
        )
    if artifact.blocks[0].text != scene.heading:
        raise ValueError("Screenplay scene heading must match the frozen Scene Deck")
    cast_refs = {character.subject_ref for character in cast.characters}
    scene_cast_refs = set(scene.cast_subject_refs)
    speaker_refs = {
        block.speaker_ref for block in artifact.blocks if block.speaker_ref is not None
    }
    if not speaker_refs <= cast_refs:
        raise ValueError("Screenplay draft references an unknown Cast speaker")
    if not speaker_refs <= scene_cast_refs:
        raise ValueError("Screenplay draft speaker is outside the frozen Scene cast")
    _validate_explicit_character_names(
        "\n".join(block.text for block in artifact.blocks),
        cast,
        allowed_subject_refs=scene_cast_refs,
    )


def _validate_short_prose_unit(
    artifact: ShortProseUnitArtifact,
    section_plan: SectionPlanArtifact,
    cast: CharacterBibleArtifact,
    *,
    active_unit_ref: str,
    expected_unit_kind: str,
) -> None:
    if not active_unit_ref or artifact.unit_ref != active_unit_ref:
        raise ValueError("Short prose unit is outside the active Section Plan cursor")
    planned = next(
        (unit for unit in section_plan.units if unit.unit_ref == artifact.unit_ref),
        None,
    )
    if planned is None:
        raise ValueError("Short prose unit references an unknown Section Plan unit")
    if artifact.unit_kind != expected_unit_kind:
        raise ValueError("Short prose unit kind does not match the frozen scale projection")
    if artifact.title != planned.title:
        raise ValueError("Short prose title must match the frozen Section Plan")
    if artifact.pov_subject_ref != planned.pov_subject_ref:
        raise ValueError("Short prose POV must match the frozen Section Plan")
    if artifact.pov_subject_ref not in {
        character.subject_ref for character in cast.characters
    }:
        raise ValueError("Short prose POV references an unknown Cast subject")
    _validate_explicit_character_names(artifact.content, cast)


def _validate_long_novel_chapter(
    artifact: ChapterArtifact,
    detail: DetailPlanIndexArtifact,
    cast: CharacterBibleArtifact,
    *,
    active_unit_ref: str,
) -> None:
    if not active_unit_ref or artifact.chapter_ref != active_unit_ref:
        raise ValueError("Chapter is outside the active Rolling Detail cursor")
    planned = next(
        (
            chapter
            for window in detail.windows
            for chapter in window.chapters
            if chapter.chapter_ref == artifact.chapter_ref
        ),
        None,
    )
    if planned is None:
        raise ValueError("Chapter references an unknown Rolling Detail plan")
    if artifact.volume_ref != planned.volume_ref:
        raise ValueError("Chapter Volume must match the frozen Rolling Detail plan")
    if artifact.title != planned.title:
        raise ValueError("Chapter title must match the frozen Rolling Detail plan")
    if artifact.pov_subject_ref != planned.pov_subject_ref:
        raise ValueError("Chapter POV must match the frozen Rolling Detail plan")
    if artifact.pov_subject_ref not in {
        character.subject_ref for character in cast.characters
    }:
        raise ValueError("Chapter POV references an unknown Cast subject")
    _validate_explicit_character_names(
        artifact.content,
        cast,
        allowed_subject_refs=set(planned.cast_subject_refs),
    )


def _read_committed_upstream(
    artifacts: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    artifact_refs: Mapping[str, str],
    stage_id: str,
) -> Phase32ArtifactRecord:
    artifact_ref = artifact_refs.get(stage_id, "")
    if not artifact_ref:
        raise Phase32StageReferenceError(
            f"Committed upstream Artifact is missing for {stage_id}"
        )
    artifact = artifacts.read(definition.run_id, artifact_ref)
    if (
        artifact.creation_route_id != definition.creation_route_id
        or artifact.stage_id != stage_id
        or artifact.status != "committed"
    ):
        raise Phase32StageReferenceError(
            f"Upstream Artifact is not committed for {stage_id}"
        )
    return artifact


__all__ = [
    "Phase32StageReferenceError",
    "validate_phase32_stage_references",
]
