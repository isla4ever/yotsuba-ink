from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.api.sse import observe_run_events
from novel_workflow.output_contracts.artifacts_vnext import STAGE_ORDER, StageId
from novel_workflow.orchestration.run_preflight import RunPreflightError
from novel_workflow.runtime.graph.execution_service import RunExecutionConflict
from novel_workflow.runtime.graph.runtime import (
    decision_operation_key,
    decision_signature,
)
from novel_workflow.runtime.graph.chapter_decision import save_edited_chapter_candidate
from novel_workflow.runtime.graph.branch_service import BranchConflictError
from novel_workflow.runtime.graph.checkpoint_branch import CheckpointBranchError
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.narrative_run_repository import ExportPreferences
from novel_workflow.workflows.narrative_scale import scale_profile_from_inputs
from novel_workflow.workflows.executable_contract import (
    WorkflowContractError,
    require_executable_workflow,
    workflow_execution_digest,
)
from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    CoverArtifact,
    DetailArtifact,
    ExportArtifact,
    VolumeArchitectureArtifact,
    StoryBriefArtifact,
    StorySpineArtifact,
    validate_detail_writeback_identity,
)


router = APIRouter(prefix="/api/runs", tags=["runs"])
class CreateNarrativeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex[:16]}", min_length=1, max_length=240)
    project_id: str = Field(min_length=1, max_length=240)
    workflow_id: str = Field(min_length=1, max_length=240)
    inputs: dict[str, Any] = Field(default_factory=dict)
    export_preferences: ExportPreferences


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern=r"^(accept|regenerate|cancel)$")
    domain_revision: int = Field(ge=0)
    artifact: dict[str, Any] | None = None
    direction: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_action_payload(self) -> "DecisionRequest":
        if self.artifact is not None and self.action != "accept":
            raise ValueError("Only an accept decision may carry an edited Artifact")
        if self.action == "regenerate" and not self.direction.strip():
            raise ValueError("A regeneration decision requires an explicit direction")
        if self.direction.strip() and self.action != "regenerate":
            raise ValueError("A revision direction is only valid for regeneration")
        return self


class CreateBranchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_run_id: str = Field(
        default_factory=lambda: f"run-{uuid4().hex[:16]}", min_length=1, max_length=240
    )
    checkpoint_id: str = Field(min_length=1, max_length=240)


def _stores(request: Request):
    return request.app.state.narrative_stores


def _require_run(request: Request, run_id: str) -> None:
    if not _stores(request).runs.exists(run_id):
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")


@router.post("")
async def create_run(request: Request, payload: CreateNarrativeRunRequest) -> dict[str, Any]:
    try:
        project = request.app.state.project_store.get(payload.project_id)
        if project.workflow_id != payload.workflow_id:
            raise WorkflowContractError(
                "project_workflow_mismatch",
                "Run workflow does not match the workflow owned by this project",
            )
        workflow = require_executable_workflow(
            request.app.state.workflow_store.read(payload.workflow_id)
        )
        bindings = request.app.state.run_preflight.freeze_workflow(workflow)
        definition = _stores(request).runs.create(
            run_id=payload.run_id,
            project_id=payload.project_id,
            workflow_id=workflow.id,
            workflow_revision=workflow.version,
            workflow_digest=workflow_execution_digest(workflow),
            quality_mode=workflow.quality_mode,
            inputs=payload.inputs,
            scale_profile=scale_profile_from_inputs(
                {
                    "length_envelope": payload.inputs.get("length_envelope"),
                    "scale_overrides": payload.inputs.get("scale_overrides"),
                }
            ),
            provider_bindings=bindings.provider_bindings,
            cover_asset_binding=bindings.cover_asset_binding,
            export_preferences=payload.export_preferences,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"Run already exists: {payload.run_id}") from exc
    except (RunPreflightError, WorkflowContractError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown project or workflow") from exc
    request.app.state.project_store.touch_run(payload.project_id, payload.run_id)
    return {"run_id": definition.run_id, "thread_id": definition.run_id, "status": "created"}


@router.get("/{run_id}")
async def get_run(request: Request, run_id: str) -> dict[str, Any]:
    _require_run(request, run_id)
    try:
        return {
            "definition": _stores(request).runs.definition(run_id).model_dump(mode="json"),
            "read_model": _stores(request).runs.read(run_id).model_dump(mode="json"),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc


@router.post("/{run_id}/start")
async def start_run(request: Request, run_id: str) -> dict[str, Any]:
    _require_run(request, run_id)
    stores = _stores(request)
    current = stores.runs.read(run_id)
    if current.status not in {"created"}:
        raise HTTPException(status_code=409, detail=f"Run cannot start from status {current.status}")
    try:
        request.app.state.narrative_execution.dispatch_start(run_id)
    except RunExecutionConflict as exc:
        raise HTTPException(status_code=409, detail="Run execution is already active") from exc
    return {"run_id": run_id, "thread_id": run_id, "status": "scheduled"}


@router.get("/{run_id}/events")
async def run_events(
    request: Request,
    run_id: str,
    after: int = Query(default=0, ge=0),
):
    _require_run(request, run_id)
    return observe_run_events(request, _stores(request).events, run_id, after=after)


@router.get("/{run_id}/artifacts/{stage_id}")
async def get_artifact(request: Request, run_id: str, stage_id: StageId) -> dict[str, Any]:
    _require_run(request, run_id)
    try:
        record = _stores(request).artifacts.latest(run_id, stage_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No committed artifact for {stage_id}") from exc
    return record.model_dump(mode="json")


@router.get("/{run_id}/artifact-records/{artifact_id}")
async def get_artifact_record(
    request: Request,
    run_id: str,
    artifact_id: str,
) -> dict[str, Any]:
    _require_run(request, run_id)
    try:
        record = _stores(request).artifacts.read(run_id, artifact_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Unknown artifact record") from exc
    return record.model_dump(mode="json")


@router.get("/{run_id}/context-manifests/{manifest_id}")
async def get_context_manifest(
    request: Request,
    run_id: str,
    manifest_id: str,
) -> dict[str, Any]:
    _require_run(request, run_id)
    try:
        record = _stores(request).context_manifests.read(run_id, manifest_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Unknown Context Manifest") from exc
    return record.model_dump(mode="json")


@router.get("/{run_id}/chapters")
async def get_chapters(request: Request, run_id: str) -> dict[str, Any]:
    _require_run(request, run_id)
    return {"run_id": run_id, "chapters": [item.model_dump(mode="json") for item in _stores(request).chapters.list(run_id)]}


@router.get("/{run_id}/chapters/{chapter_id}/versions/{version_id}")
async def get_chapter_version(
    request: Request,
    run_id: str,
    chapter_id: str,
    version_id: str,
) -> dict[str, Any]:
    _require_run(request, run_id)
    try:
        record = _stores(request).chapters.read(run_id, chapter_id, version_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Unknown chapter version") from exc
    return record.model_dump(mode="json")


@router.post("/{run_id}/decisions/{decision_id}")
async def resolve_decision(
    request: Request,
    run_id: str,
    decision_id: str,
    payload: DecisionRequest,
) -> dict[str, Any]:
    _require_run(request, run_id)
    stores = _stores(request)
    receipt_signature = decision_signature(
        {"decision_id": decision_id, **payload.model_dump(mode="json")}
    )
    operation_key = decision_operation_key(decision_id)
    existing_receipt = stores.operations.find(run_id, operation_key)
    if existing_receipt is not None:
        if existing_receipt.request_signature != receipt_signature:
            raise HTTPException(
                status_code=409,
                detail="Decision was already submitted with different command data",
            )
        if existing_receipt.status == "succeeded":
            return {"run_id": run_id, "decision_id": decision_id, "status": "resolved"}

    current = stores.runs.read(run_id)
    pending = next(
        (item for item in current.pending_decisions if item.get("decision_id") == decision_id),
        None,
    )
    if pending is None and existing_receipt is None:
        raise HTTPException(status_code=409, detail="Decision is not pending on this Run")
    if pending is not None and payload.domain_revision != int(
        pending.get("domain_revision", -1)
    ):
        raise HTTPException(status_code=409, detail="Decision domain revision is stale")
    decision = {
        "action": payload.action,
        "domain_revision": payload.domain_revision,
        "decision_id": decision_id,
        **({"direction": payload.direction.strip()} if payload.direction.strip() else {}),
    }
    if payload.artifact is not None and pending is not None:
        node_id = str(pending.get("node_id") or "")
        stage_id = node_id.partition(".")[0]
        if stage_id == "text":
            chapter_id = str(pending.get("chapter_id") or "")
            source_version_id = str(pending.get("artifact_ref") or "")
            if not chapter_id or not source_version_id:
                raise HTTPException(status_code=422, detail="The chapter decision is missing its immutable candidate")
            try:
                record = save_edited_chapter_candidate(
                    _stores(request).chapters,
                    _stores(request).events,
                    run_id=run_id,
                    chapter_id=chapter_id,
                    source_version_id=source_version_id,
                    payload=payload.artifact,
                )
            except (FileNotFoundError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            decision["candidate_chapter_version_id"] = record.version_id
        elif stage_id not in STAGE_ORDER:
            raise HTTPException(status_code=422, detail="This decision does not accept an editable stage Artifact")
        else:
            try:
                record = _save_edited_candidate(
                    _stores(request),
                    run_id,
                    stage_id,  # type: ignore[arg-type]
                    payload.artifact,
                    source=f"user-decision:{decision_id}",
                )
            except (FileNotFoundError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            decision["candidate_artifact_id"] = record.artifact_id
    try:
        stores.operations.begin(
            run_id=run_id,
            operation_key=operation_key,
            kind="graph_decision",
            request_signature=receipt_signature,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Decision was already submitted with different command data",
        ) from exc
    decision["_receipt_signature"] = receipt_signature
    try:
        request.app.state.narrative_execution.dispatch_resume(run_id, decision)
    except RunExecutionConflict as exc:
        if existing_receipt is None:
            raise HTTPException(status_code=409, detail="Run execution is already active") from exc
        return {"run_id": run_id, "decision_id": decision_id, "status": "scheduled"}
    return {"run_id": run_id, "decision_id": decision_id, "status": "scheduled"}


def _save_edited_candidate(
    stores: Any,
    run_id: str,
    stage_id: StageId,
    artifact: dict[str, Any],
    *,
    source: str,
):
    subject_ids: set[str] | None = None
    turn_ids: set[str] | None = None
    volume_cast_ids: dict[str, set[str]] | None = None
    chapter_refs: set[str] | None = None
    chapter_version_ids: list[str] | None = None
    cover_asset_ids: set[str] | None = None
    export_title: str | None = None
    if stage_id in {"volumes", "detail"}:
        character_record = stores.artifacts.latest(run_id, "cast")
        character_bible = CharacterBibleArtifact.model_validate(
            character_record.payload
        )
        subject_ids = {item.id for item in character_bible.subjects}
    if stage_id == "volumes":
        spine = StorySpineArtifact.model_validate(
            stores.artifacts.latest(run_id, "spine").payload
        )
        turn_ids = {turn.id for turn in spine.turns}
    if stage_id == "detail":
        source_detail = DetailArtifact.model_validate(
            stores.artifacts.latest(run_id, "detail", status="candidate").payload
        )
        candidate_detail = DetailArtifact.model_validate(artifact)
        validate_detail_writeback_identity(source_detail, candidate_detail)
        chapter_refs = {item.ref for item in source_detail.chapters}
        architecture = VolumeArchitectureArtifact.model_validate(
            stores.artifacts.latest(run_id, "volumes").payload
        )
        volume_cast_ids = {
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
        cover_asset_ids = {
            item.asset_id for item in assets if item.generation_attempt == latest_attempt
        }
        if not cover.selected_asset_id:
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
        chapter_version_ids = [item.version_id for item in accepted]
        brief_artifact = stores.artifacts.latest(run_id, "brief").payload
        export_title = str(brief_artifact["title"])
        cover = CoverArtifact.model_validate(
            stores.artifacts.latest(run_id, "cover").payload
        )
        if export.cover_asset_id != cover.selected_asset_id:
            raise ValueError("Export must reference the committed Cover asset")
        cover_asset_ids = {cover.selected_asset_id}
    return stores.artifacts.save_candidate(
        run_id,
        stage_id,
        artifact,
        source=source,
        subject_ids=subject_ids,
        turn_ids=turn_ids,
        volume_cast_ids=volume_cast_ids,
        chapter_refs=chapter_refs,
        chapter_version_ids=chapter_version_ids,
        cover_asset_ids=cover_asset_ids,
        export_title=export_title,
    )


@router.get("/{run_id}/state")
async def get_graph_state(request: Request, run_id: str) -> dict[str, Any]:
    _require_run(request, run_id)
    current = _stores(request).runs.read(run_id)
    return current.model_dump(mode="json")


@router.post("/{run_id}/branches")
async def create_branch(
    request: Request,
    run_id: str,
    payload: CreateBranchRequest,
) -> dict[str, Any]:
    _require_run(request, run_id)
    try:
        projection = await request.app.state.narrative_execution.create_branch(
            source_run_id=run_id,
            target_run_id=payload.target_run_id,
            checkpoint_id=payload.checkpoint_id,
        )
    except RunExecutionConflict as exc:
        raise HTTPException(status_code=409, detail="Source or target Run execution is active") from exc
    except BranchConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (CheckpointBranchError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "run_id": projection.run_id,
        "thread_id": projection.thread_id,
        "status": projection.status,
        "source_run_id": run_id,
        "source_checkpoint_id": payload.checkpoint_id,
    }


__all__ = ["CreateBranchRequest", "CreateNarrativeRunRequest", "DecisionRequest", "router"]
