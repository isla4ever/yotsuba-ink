"""Author editing boundary for Phase 32 immutable stage Artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    CoverArtifact,
)

from novel_workflow.output_contracts.phase32_route_artifacts import (
    BeatBoardArtifact,
    BookArchitectureArtifact,
    CharacterBibleArtifact,
    DetailPlanIndexArtifact,
    Phase32CoreArtifact,
    SceneDeckArtifact,
    ScreenplayDraftArtifact,
    SectionPlanArtifact,
    ShortProseUnitArtifact,
    VolumeArchitectureArtifact,
    bind_phase32_artifact,
    phase32_artifact_binding,
)
from novel_workflow.orchestration.phase32_stage_reference_validation import (
    Phase32StageReferenceError,
    validate_phase32_stage_references,
)
from novel_workflow.storage.phase32_artifact_draft_store import (
    Phase32ArtifactDraft,
    Phase32ArtifactDraftStore,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_read_model import PendingDecisionProjection
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_compiler import CompiledRouteStage


_AUTHOR_EDITABLE_STAGE_KEYS = frozenset(
    {
        ("screenplay_sample", "brief"),
        ("screenplay_sample", "cast"),
        ("screenplay_sample", "beat_board"),
        ("screenplay_sample", "scene_deck"),
        ("screenplay_sample", "script"),
        ("short_novel", "brief"),
        ("short_novel", "story_map"),
        ("short_novel", "cast"),
        ("short_novel", "section_plan"),
        ("short_novel", "text"),
        ("short_novel", "cover"),
        ("long_novel", "brief"),
        ("long_novel", "book_architecture"),
        ("long_novel", "cast"),
        ("long_novel", "volumes"),
        ("long_novel", "rolling_detail"),
        ("long_novel", "text"),
        ("long_novel", "cover"),
    }
)


class Phase32ArtifactEditingError(ValueError):
    code = "phase32_artifact_editing_invalid"


class Phase32ArtifactEditingConflict(Phase32ArtifactEditingError):
    code = "phase32_artifact_editing_conflict"


class Phase32CurrentArtifact(BaseModel):
    """Author-facing projection of one exact candidate or committed Artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    creation_route_id: str
    stage_id: str
    artifact_kind: str
    artifact_ref: str
    unit_ref: str = ""
    status: str
    payload: dict[str, Any]
    payload_digest: str
    editable: bool
    pending_decision: PendingDecisionProjection | None = None


class Phase32ArtifactEditingService:
    """Validate source-bound drafts and materialize them as new candidates."""

    def __init__(
        self,
        repository: Phase32RunRepository,
        artifacts: Phase32ArtifactStore,
        drafts: Phase32ArtifactDraftStore,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.drafts = drafts

    def current(
        self,
        run_id: str,
        stage_id: str,
        *,
        unit_ref: str = "",
    ) -> Phase32CurrentArtifact:
        record = self.repository.read(run_id)
        stage = record.definition.stage(stage_id)
        decision = next(
            (
                item
                for item in record.read_model.pending_decisions
                if item.stage_id == stage_id
                and (not unit_ref or item.unit_ref == unit_ref)
            ),
            None,
        )
        writeback_recovery = bool(
            decision is not None and decision.kind == "writeback_recovery"
        )
        artifact_ref = decision.artifact_ref if decision else ""
        selected_unit_ref = decision.unit_ref if decision else unit_ref
        progress = record.read_model.sequential_stage_progress.get(stage_id)
        if unit_ref and stage.unitization != "sequential_units":
            raise Phase32ArtifactEditingConflict(
                "A unit ref can only select a sequential stage Artifact"
            )
        if not artifact_ref and progress is not None:
            if not selected_unit_ref and progress.committed_artifact_refs:
                selected_unit_ref = tuple(progress.committed_artifact_refs)[-1]
            artifact_ref = progress.committed_artifact_refs.get(selected_unit_ref, "")
        if not artifact_ref:
            projection = record.read_model.artifact_refs.get(stage_id)
            artifact_ref = projection.artifact_ref if projection else ""
        if not artifact_ref:
            raise FileNotFoundError(f"No Phase 32 Artifact exists for stage {stage_id}")
        artifact = self._read_bound_artifact(
            record.definition,
            stage,
            artifact_ref,
            expected_status=(
                "candidate" if decision is not None and not writeback_recovery else "committed"
            ),
        )
        self._validate_stage_references(
            record,
            stage.stage_id,
            artifact.payload,
            active_unit_ref=selected_unit_ref,
        )
        editable = bool(
            (record.definition.creation_route_id, stage_id)
            in _AUTHOR_EDITABLE_STAGE_KEYS
            and decision is not None
            and not writeback_recovery
            and decision.domain_revision is not None
            and decision.allowed_actions
        )
        return Phase32CurrentArtifact(
            run_id=run_id,
            creation_route_id=record.definition.creation_route_id,
            stage_id=stage_id,
            artifact_kind=stage.artifact_kind,
            artifact_ref=artifact.artifact_ref,
            unit_ref=selected_unit_ref,
            status=artifact.status,
            payload=dict(artifact.payload),
            payload_digest=artifact.payload_digest,
            editable=editable,
            pending_decision=decision,
        )

    def latest_draft(self, run_id: str, decision_id: str) -> Phase32ArtifactDraft | None:
        record, decision = self._active_decision(run_id, decision_id)
        draft = self.drafts.latest(run_id, decision_id)
        if draft is None:
            return None
        self._validate_draft_identity(record.definition, decision, draft)
        return draft

    def save_draft(
        self,
        run_id: str,
        decision_id: str,
        *,
        domain_revision: int,
        source_artifact_ref: str,
        payload: dict[str, Any],
    ) -> Phase32ArtifactDraft:
        record, decision = self._active_decision(run_id, decision_id)
        self._require_editable_stage(record.definition, decision)
        if domain_revision != decision.domain_revision:
            raise Phase32ArtifactEditingConflict("Draft domain revision is stale")
        if source_artifact_ref != decision.artifact_ref:
            raise Phase32ArtifactEditingConflict("Draft source Artifact is stale")
        stage = record.definition.stage(decision.stage_id)
        source_artifact = self._read_bound_artifact(
            record.definition,
            stage,
            source_artifact_ref,
            expected_status="candidate",
        )
        artifact = validate_phase32_artifact_payload(record.definition, stage, payload)
        self._validate_stage_references(
            record,
            stage.stage_id,
            artifact,
            active_unit_ref=decision.unit_ref,
        )
        validate_phase32_author_edit_identity(
            stage.stage_id,
            source_artifact.payload,
            artifact,
        )
        return self.drafts.save(
            run_id=run_id,
            decision_id=decision_id,
            domain_revision=domain_revision,
            creation_route_id=record.definition.creation_route_id,
            stage_id=decision.stage_id,
            source_artifact_ref=source_artifact_ref,
            payload=artifact.model_dump(mode="json"),
        )

    def materialize_accept_candidate(
        self,
        run_id: str,
        decision_id: str,
        draft_ref: str,
    ) -> Phase32ArtifactRecord:
        record, decision = self._active_decision(run_id, decision_id)
        self._require_editable_stage(record.definition, decision)
        draft = self.drafts.read(run_id, decision_id, draft_ref)
        self._validate_draft_identity(record.definition, decision, draft)
        stage = record.definition.stage(decision.stage_id)
        artifact = validate_phase32_artifact_payload(
            record.definition,
            stage,
            draft.payload,
        )
        self._validate_stage_references(
            record,
            stage.stage_id,
            artifact,
            active_unit_ref=decision.unit_ref,
        )
        source_artifact = self._read_bound_artifact(
            record.definition,
            stage,
            decision.artifact_ref,
            expected_status="candidate",
        )
        validate_phase32_author_edit_identity(
            stage.stage_id,
            source_artifact.payload,
            artifact,
        )
        return self.artifacts.save_candidate(
            run_id=run_id,
            creation_route_id=record.definition.creation_route_id,
            stage_id=stage.stage_id,
            artifact=artifact,
            source_operation_key=f"author-draft:{decision_id}:{draft_ref}",
        )

    def _validate_stage_references(
        self,
        record: Phase32RunRecord,
        stage_id: str,
        artifact: Phase32CoreArtifact | dict[str, Any],
        *,
        active_unit_ref: str = "",
    ) -> None:
        try:
            validated = (
                artifact
                if not isinstance(artifact, dict)
                else validate_phase32_artifact_payload(
                    record.definition,
                    record.definition.stage(stage_id),
                    artifact,
                )
            )
            validate_phase32_stage_references(
                self.artifacts,
                record.definition,
                record.state.artifact_refs,
                stage_id,
                validated,
                active_unit_ref=active_unit_ref,
            )
        except Phase32StageReferenceError as exc:
            raise Phase32ArtifactEditingConflict(
                str(exc)
            ) from exc

    def _active_decision(
        self,
        run_id: str,
        decision_id: str,
    ) -> tuple[Phase32RunRecord, PendingDecisionProjection]:
        record = self.repository.read(run_id)
        decision = next(
            (
                item
                for item in record.read_model.pending_decisions
                if item.decision_id == decision_id
            ),
            None,
        )
        if decision is None:
            raise Phase32ArtifactEditingConflict(
                "Decision is not pending on the current Phase 32 Run"
            )
        return record, decision

    @staticmethod
    def _require_editable_stage(
        definition: GraphRunDefinition,
        decision: PendingDecisionProjection,
    ) -> None:
        if decision.kind == "writeback_recovery":
            raise Phase32ArtifactEditingConflict(
                "Writeback recovery cannot edit an accepted Artifact"
            )
        if (
            definition.creation_route_id,
            decision.stage_id,
        ) not in _AUTHOR_EDITABLE_STAGE_KEYS:
            raise Phase32ArtifactEditingConflict(
                "This route stage has not opened source-bound author editing"
            )
        if decision.domain_revision is None or not decision.allowed_actions:
            raise Phase32ArtifactEditingConflict(
                "Historical decision projection is read-only because its authority is incomplete"
            )

    @staticmethod
    def _validate_draft_identity(
        definition: GraphRunDefinition,
        decision: PendingDecisionProjection,
        draft: Phase32ArtifactDraft,
    ) -> None:
        if (
            draft.run_id != definition.run_id
            or draft.decision_id != decision.decision_id
            or draft.domain_revision != decision.domain_revision
            or draft.creation_route_id != definition.creation_route_id
            or draft.stage_id != decision.stage_id
            or draft.source_artifact_ref != decision.artifact_ref
        ):
            raise Phase32ArtifactEditingConflict(
                "Draft is not bound to the active decision source and revision"
            )

    def _read_bound_artifact(
        self,
        definition: GraphRunDefinition,
        stage: CompiledRouteStage,
        artifact_ref: str,
        *,
        expected_status: str,
    ) -> Phase32ArtifactRecord:
        artifact = self.artifacts.read(definition.run_id, artifact_ref)
        if (
            artifact.creation_route_id != definition.creation_route_id
            or artifact.stage_id != stage.stage_id
            or artifact.artifact_kind != stage.artifact_kind
            or artifact.status != expected_status
        ):
            raise Phase32ArtifactEditingConflict(
                "Artifact does not match the frozen Run stage and status"
            )
        validate_phase32_artifact_payload(definition, stage, artifact.payload)
        return artifact


def validate_phase32_artifact_payload(
    definition: GraphRunDefinition,
    stage: CompiledRouteStage,
    payload: dict[str, Any],
) -> Phase32CoreArtifact:
    """Apply schema, route binding, and frozen Scale validation in one place."""

    binding = phase32_artifact_binding(definition.creation_route_id, stage.stage_id)
    try:
        artifact = binding.model_type.model_validate(payload)
        artifact = bind_phase32_artifact(
            definition.creation_route_id,
            stage.stage_id,
            artifact,
        )
        if stage.stage_id == "brief":
            target = definition.scale_profile.payload.get("target")
            if isinstance(target, int):
                target_field = (
                    "target_minutes"
                    if definition.creation_route_id == "screenplay_sample"
                    else "target_characters"
                )
                if getattr(artifact, target_field, None) != target:
                    raise ValueError("Brief target must equal the frozen scale target")
        return artifact
    except Exception as exc:
        raise Phase32ArtifactEditingError(
            f"Artifact payload does not satisfy {definition.creation_route_id}/{stage.stage_id}"
        ) from exc


def validate_phase32_author_edit_identity(
    stage_id: str,
    source_payload: dict[str, Any],
    artifact: Phase32CoreArtifact,
    *,
    allow_rolling_detail_cast_scope_changes: bool = False,
) -> None:
    """Keep code-stable registries fixed while allowing literary field edits."""

    if stage_id == "cast" and isinstance(artifact, CharacterBibleArtifact):
        source = CharacterBibleArtifact.model_validate(source_payload)
        source_refs = {character.subject_ref for character in source.characters}
        edited_refs = {character.subject_ref for character in artifact.characters}
        if source_refs != edited_refs or len(source.characters) != len(artifact.characters):
            raise Phase32ArtifactEditingConflict(
                "Cast author drafts cannot add, remove, or replace frozen subject refs"
            )
        return
    if stage_id == "beat_board" and isinstance(artifact, BeatBoardArtifact):
        source = BeatBoardArtifact.model_validate(source_payload)
        source_refs = {beat.beat_ref for beat in source.beats}
        edited_refs = {beat.beat_ref for beat in artifact.beats}
        if source_refs != edited_refs or len(source.beats) != len(artifact.beats):
            raise Phase32ArtifactEditingConflict(
                "Beat Board drafts cannot add, remove, or replace frozen Beat refs"
            )
        return
    if stage_id == "scene_deck" and isinstance(artifact, SceneDeckArtifact):
        source = SceneDeckArtifact.model_validate(source_payload)
        source_refs = {scene.scene_ref for scene in source.scenes}
        edited_refs = {scene.scene_ref for scene in artifact.scenes}
        if source_refs != edited_refs or len(source.scenes) != len(artifact.scenes):
            raise Phase32ArtifactEditingConflict(
                "Scene Deck drafts cannot add, remove, or replace frozen Scene refs"
            )
        return
    if stage_id == "script" and isinstance(artifact, ScreenplayDraftArtifact):
        source = ScreenplayDraftArtifact.model_validate(source_payload)
        if artifact.scene_ref != source.scene_ref:
            raise Phase32ArtifactEditingConflict(
                "Script author drafts cannot replace the frozen Scene ref"
            )
        return
    if stage_id == "text" and isinstance(artifact, ShortProseUnitArtifact):
        source = ShortProseUnitArtifact.model_validate(source_payload)
        if (
            artifact.unit_ref != source.unit_ref
            or artifact.unit_kind != source.unit_kind
            or artifact.title != source.title
            or artifact.pov_subject_ref != source.pov_subject_ref
        ):
            raise Phase32ArtifactEditingConflict(
                "Short prose drafts cannot change frozen unit identity, title, kind, or POV"
            )
        return
    if stage_id == "text" and isinstance(artifact, ChapterArtifact):
        source = ChapterArtifact.model_validate(source_payload)
        if (
            artifact.chapter_ref != source.chapter_ref
            or artifact.volume_ref != source.volume_ref
            or artifact.title != source.title
            or artifact.pov_subject_ref != source.pov_subject_ref
        ):
            raise Phase32ArtifactEditingConflict(
                "Chapter drafts cannot change frozen Chapter, Volume, title, or POV identity"
            )
        return
    if stage_id == "cover" and isinstance(artifact, CoverArtifact):
        source = CoverArtifact.model_validate(source_payload)
        if artifact.brief != source.brief or artifact.candidates != source.candidates:
            raise Phase32ArtifactEditingConflict(
                "Cover drafts may only select one of the generated immutable assets"
            )
        return
    if stage_id == "book_architecture" and isinstance(
        artifact, BookArchitectureArtifact
    ):
        source = BookArchitectureArtifact.model_validate(source_payload)
        source_refs = {part.part_ref for part in source.parts}
        edited_refs = {part.part_ref for part in artifact.parts}
        if source_refs != edited_refs or len(source.parts) != len(artifact.parts):
            raise Phase32ArtifactEditingConflict(
                "Book Architecture drafts cannot add, remove, or replace frozen Part refs"
            )
        return
    if stage_id == "section_plan" and isinstance(artifact, SectionPlanArtifact):
        source = SectionPlanArtifact.model_validate(source_payload)
        source_refs = {unit.unit_ref for unit in source.units}
        edited_refs = {unit.unit_ref for unit in artifact.units}
        if source_refs != edited_refs or len(source.units) != len(artifact.units):
            raise Phase32ArtifactEditingConflict(
                "Section Plan drafts cannot add, remove, or replace frozen unit refs"
            )
        return
    if stage_id == "volumes" and isinstance(artifact, VolumeArchitectureArtifact):
        source = VolumeArchitectureArtifact.model_validate(source_payload)
        source_by_ref = {volume.volume_ref: volume for volume in source.volumes}
        edited_refs = {volume.volume_ref for volume in artifact.volumes}
        if len(source.volumes) != len(artifact.volumes) or set(source_by_ref) != edited_refs:
            raise Phase32ArtifactEditingConflict(
                "Volume author drafts cannot add, remove, or replace frozen volume refs"
            )
        for volume in artifact.volumes:
            source_volume = source_by_ref[volume.volume_ref]
            if (
                volume.part_ref != source_volume.part_ref
                or set(volume.cast_subject_refs) != set(source_volume.cast_subject_refs)
            ):
                raise Phase32ArtifactEditingConflict(
                    "Volume author drafts cannot change frozen Part or Cast scope"
                )
        return
    if stage_id == "rolling_detail" and isinstance(
        artifact, DetailPlanIndexArtifact
    ):
        source = DetailPlanIndexArtifact.model_validate(source_payload)
        source_windows = {window.window_ref: window for window in source.windows}
        edited_window_refs = {window.window_ref for window in artifact.windows}
        if (
            len(source.windows) != len(artifact.windows)
            or set(source_windows) != edited_window_refs
        ):
            raise Phase32ArtifactEditingConflict(
                "Rolling Detail drafts cannot add, remove, or replace frozen Window refs"
            )
        for window in artifact.windows:
            source_window = source_windows[window.window_ref]
            if set(window.volume_refs) != set(source_window.volume_refs):
                raise Phase32ArtifactEditingConflict(
                    "Rolling Detail drafts cannot change frozen Window Volume scope"
                )
            source_chapters = {
                chapter.chapter_ref: chapter for chapter in source_window.chapters
            }
            edited_chapter_refs = {
                chapter.chapter_ref for chapter in window.chapters
            }
            if (
                len(source_window.chapters) != len(window.chapters)
                or set(source_chapters) != edited_chapter_refs
            ):
                raise Phase32ArtifactEditingConflict(
                    "Rolling Detail drafts cannot add, remove, move, or replace frozen Chapter refs"
                )
            for chapter in window.chapters:
                source_chapter = source_chapters[chapter.chapter_ref]
                if (
                    chapter.volume_ref != source_chapter.volume_ref
                    or chapter.pov_subject_ref != source_chapter.pov_subject_ref
                    or (
                        not allow_rolling_detail_cast_scope_changes
                        and set(chapter.cast_subject_refs)
                        != set(source_chapter.cast_subject_refs)
                    )
                ):
                    raise Phase32ArtifactEditingConflict(
                        "Rolling Detail drafts cannot change frozen Chapter Volume, POV, or Cast scope"
                    )
                source_scenes = {
                    scene.scene_ref: scene for scene in source_chapter.scenes
                }
                edited_scene_refs = {scene.scene_ref for scene in chapter.scenes}
                if (
                    len(source_chapter.scenes) != len(chapter.scenes)
                    or set(source_scenes) != edited_scene_refs
                ):
                    raise Phase32ArtifactEditingConflict(
                        "Rolling Detail drafts cannot add, remove, move, or replace frozen Scene refs"
                    )
                for scene in chapter.scenes:
                    if (
                        not allow_rolling_detail_cast_scope_changes
                        and set(scene.cast_subject_refs)
                        != set(source_scenes[scene.scene_ref].cast_subject_refs)
                    ):
                        raise Phase32ArtifactEditingConflict(
                            "Rolling Detail drafts cannot change frozen Scene Cast scope"
                        )


__all__ = [
    "Phase32ArtifactEditingConflict",
    "Phase32ArtifactEditingError",
    "Phase32ArtifactEditingService",
    "Phase32CurrentArtifact",
    "validate_phase32_author_edit_identity",
    "validate_phase32_artifact_payload",
]
