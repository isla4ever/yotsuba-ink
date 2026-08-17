from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    STAGE_ORDER,
    CharacterBibleArtifact,
    CoverArtifact,
    DetailArtifact,
    ExportArtifact,
    StageId,
    StorySpineArtifact,
    StoryBriefArtifact,
    VolumeArchitectureArtifact,
    validate_artifact_vnext,
    validate_detail_writeback_identity,
)
from novel_workflow.runtime.graph.chapter_decision import (
    validate_edited_chapter_candidate,
)
from novel_workflow.workflows.narrative_scale import plan_narrative_scale
from novel_workflow.storage.artifact_store import ArtifactRecord
from novel_workflow.storage.stage_artifact_draft_store import StageArtifactDraftRecord


class StageArtifactDraftConflict(ValueError):
    """The requested draft no longer belongs to the active graph interrupt."""


@dataclass(frozen=True, slots=True)
class PendingArtifactDecision:
    stage_id: StageId
    decision_id: str
    domain_revision: int
    source_artifact_id: str
    chapter_id: str = ""


@dataclass(frozen=True, slots=True)
class ValidatedStageArtifact:
    payload: dict[str, Any]
    context: dict[str, Any]


def load_stage_artifact_draft(
    stores: Any,
    *,
    run_id: str,
    decision_id: str,
) -> StageArtifactDraftRecord | None:
    try:
        record = stores.stage_drafts.latest(run_id, decision_id)
    except FileNotFoundError:
        return None
    pending = require_pending_artifact_decision(stores, run_id, decision_id)
    _require_matching_record(record, pending)
    return record


def save_stage_artifact_draft(
    stores: Any,
    *,
    run_id: str,
    decision_id: str,
    domain_revision: int,
    source_artifact_id: str,
    artifact: dict[str, Any],
) -> StageArtifactDraftRecord:
    pending = require_pending_artifact_decision(stores, run_id, decision_id)
    if pending.domain_revision != domain_revision:
        raise StageArtifactDraftConflict("Draft domain revision is stale")
    if pending.source_artifact_id != source_artifact_id:
        raise StageArtifactDraftConflict("Draft source Artifact is stale")
    payload = validate_edited_artifact(stores, run_id, pending, artifact)
    return stores.stage_drafts.save(
        run_id=run_id,
        stage_id=pending.stage_id,
        decision_id=pending.decision_id,
        domain_revision=pending.domain_revision,
        source_artifact_id=pending.source_artifact_id,
        payload=payload,
    )


def save_edited_stage_candidate(
    stores: Any,
    *,
    run_id: str,
    stage_id: StageId,
    source_artifact_id: str,
    artifact: dict[str, Any],
    source: str,
) -> ArtifactRecord:
    if stage_id == "text":
        raise ValueError("Chapter edits are stored by the Chapter Store")
    source_artifact = stores.artifacts.read(run_id, source_artifact_id)
    if source_artifact.stage_id != stage_id or source_artifact.status != "candidate":
        raise StageArtifactDraftConflict(
            "Decision source is not the active immutable candidate"
        )
    validated = _validate_stage_artifact(
        stores,
        run_id,
        stage_id,
        artifact,
        source_artifact=source_artifact,
    )
    return stores.artifacts.save_candidate(
        run_id,
        stage_id,
        validated.payload,
        source=source,
        **validated.context,
    )


def require_pending_artifact_decision(
    stores: Any,
    run_id: str,
    decision_id: str,
) -> PendingArtifactDecision:
    current = stores.runs.read(run_id)
    pending = next(
        (
            item
            for item in current.pending_decisions
            if item.get("decision_id") == decision_id
        ),
        None,
    )
    if pending is None:
        raise StageArtifactDraftConflict("Decision is not pending on this Run")
    stage_id = str(pending.get("node_id") or "").partition(".")[0]
    if stage_id not in STAGE_ORDER:
        raise StageArtifactDraftConflict("Decision does not target an editable Artifact")
    source_artifact_id = str(pending.get("artifact_ref") or "")
    domain_revision = pending.get("domain_revision")
    if not source_artifact_id or not isinstance(domain_revision, int):
        raise StageArtifactDraftConflict("Decision is missing its immutable source binding")
    return PendingArtifactDecision(
        stage_id=stage_id,  # type: ignore[arg-type]
        decision_id=decision_id,
        domain_revision=domain_revision,
        source_artifact_id=source_artifact_id,
        chapter_id=str(pending.get("chapter_id") or ""),
    )


def validate_edited_artifact(
    stores: Any,
    run_id: str,
    pending: PendingArtifactDecision,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    if pending.stage_id == "text":
        if not pending.chapter_id:
            raise ValueError("Chapter decision is missing its chapter binding")
        source = stores.chapters.read(
            run_id,
            pending.chapter_id,
            pending.source_artifact_id,
        ).artifact
        return validate_edited_chapter_candidate(
            source,
            chapter_id=pending.chapter_id,
            source_version_id=pending.source_artifact_id,
            payload=artifact,
        ).model_dump(mode="json")
    source = stores.artifacts.read(run_id, pending.source_artifact_id)
    if source.stage_id != pending.stage_id or source.status != "candidate":
        raise StageArtifactDraftConflict(
            "Decision source is not the active immutable candidate"
        )
    return _validate_stage_artifact(
        stores,
        run_id,
        pending.stage_id,
        artifact,
        source_artifact=source,
    ).payload


def _validate_stage_artifact(
    stores: Any,
    run_id: str,
    stage_id: StageId,
    artifact: dict[str, Any],
    *,
    source_artifact: ArtifactRecord | None = None,
) -> ValidatedStageArtifact:
    context: dict[str, Any] = {}
    if stage_id == "brief":
        brief = StoryBriefArtifact.model_validate(artifact)
        profile = stores.runs.definition(run_id).scale_profile
        if brief.length_envelope.word_target_soft != profile.word_target_soft:
            raise ValueError(
                "Brief length envelope is frozen by the Run; change it before starting a new Run"
            )
    if stage_id == "cast":
        if source_artifact is None:
            raise ValueError("Cast editing requires its immutable source candidate")
        source_cast = CharacterBibleArtifact.model_validate(source_artifact.payload)
        definition = stores.runs.definition(run_id)
        context["chapter_target"] = plan_narrative_scale(
            definition.scale_profile,
            definition.quality_mode,
        ).chapter_min
        context["subject_ids"] = {item.id for item in source_cast.subjects}
        context["demand_keys"] = {
            demand_ref
            for item in source_cast.subjects
            for demand_ref in item.demand_refs
        }
    if stage_id in {"volumes", "detail"}:
        character_bible = CharacterBibleArtifact.model_validate(
            stores.artifacts.latest(run_id, "cast").payload
        )
        context["subject_ids"] = {item.id for item in character_bible.subjects}
    if stage_id == "volumes":
        spine = StorySpineArtifact.model_validate(
            stores.artifacts.latest(run_id, "spine").payload
        )
        context["turn_ids"] = {turn.id for turn in spine.turns}
    if stage_id == "detail":
        context["historical_subject_ids"] = {
            item.id
            for item in character_bible.subjects
            if item.kind == "historical_record"
        }
        source_detail = DetailArtifact.model_validate(
            stores.artifacts.latest(run_id, "detail", status="candidate").payload
        )
        candidate_detail = DetailArtifact.model_validate(artifact)
        validate_detail_writeback_identity(source_detail, candidate_detail)
        context["chapter_refs"] = {item.ref for item in source_detail.chapters}
        context["chapter_turn_refs"] = {
            item.ref: list(item.turn_refs) for item in source_detail.chapters
        }
        architecture = VolumeArchitectureArtifact.model_validate(
            stores.artifacts.latest(run_id, "volumes").payload
        )
        context["volume_cast_ids"] = {
            volume.id: set(volume.cast_ids) for volume in architecture.volumes
        }
    if stage_id == "cover":
        cover = CoverArtifact.model_validate(artifact)
        source_cover = CoverArtifact.model_validate(
            stores.artifacts.latest(run_id, "cover", status="candidate").payload
        )
        if cover.brief != source_cover.brief:
            raise ValueError(
                "Cover brief changes require regeneration before asset selection"
            )
        assets = stores.cover_assets.list(run_id)
        latest_attempt = max((item.generation_attempt for item in assets), default=0)
        context["cover_asset_ids"] = {
            item.asset_id
            for item in assets
            if item.generation_attempt == latest_attempt
        }
        include_image = stores.runs.definition(
            run_id
        ).export_preferences.include_cover_image
        if include_image and not cover.selected_asset_id:
            raise ValueError("Cover acceptance requires one selected immutable asset")
    if stage_id == "export":
        export = ExportArtifact.model_validate(artifact)
        detail = stores.artifacts.latest(run_id, "detail").payload
        accepted = [
            stores.chapters.latest(run_id, str(chapter["ref"])).artifact
            for chapter in detail["chapters"]
        ]
        if any(item.author_status != "accepted" for item in accepted):
            raise ValueError("Export requires accepted versions for every frozen chapter")
        context["chapter_version_ids"] = [item.version_id for item in accepted]
        context["export_title"] = str(
            stores.artifacts.latest(run_id, "brief").payload["title"]
        )
        cover = CoverArtifact.model_validate(
            stores.artifacts.latest(run_id, "cover").payload
        )
        if export.cover_asset_id != cover.selected_asset_id:
            raise ValueError("Export must reference the committed Cover asset")
        context["cover_asset_ids"] = (
            {cover.selected_asset_id} if cover.selected_asset_id else set()
        )
    validated = validate_artifact_vnext(stage_id, artifact, **context)
    return ValidatedStageArtifact(
        payload=validated.model_dump(mode="json"),
        context=context,
    )


def _require_matching_record(
    record: StageArtifactDraftRecord,
    pending: PendingArtifactDecision,
) -> None:
    if (
        record.stage_id != pending.stage_id
        or record.decision_id != pending.decision_id
        or record.domain_revision != pending.domain_revision
        or record.source_artifact_id != pending.source_artifact_id
    ):
        raise StageArtifactDraftConflict(
            "Saved draft does not match the active graph decision"
        )


__all__ = [
    "StageArtifactDraftConflict",
    "load_stage_artifact_draft",
    "require_pending_artifact_decision",
    "save_edited_stage_candidate",
    "save_stage_artifact_draft",
    "validate_edited_artifact",
]
