"""Authoritative Phase 32 Run HTTP adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.api.dependencies import phase32_run_envelope
from novel_workflow.api.sse import observe_run_events
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingConflict,
    Phase32ArtifactEditingError,
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_continuity_acceptance import (
    Phase32ContinuityAdmissionError,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32DecisionCommand,
    Phase32ExecutionConflict,
    Phase32FailureRecoveryCommand,
    Phase32RunAdmissionRequired,
    Phase32RunExecutionService,
)
from novel_workflow.orchestration.phase32_graph_execution import Phase32ExecutionError
from novel_workflow.orchestration.phase32_live_candidate_authorization import (
    Phase32LiveCandidateAuthorizationError,
)
from novel_workflow.orchestration.phase32_provider_readiness_admission import (
    Phase32ProviderReadinessAdmissionError,
)
from novel_workflow.orchestration.phase32_run_preflight import Phase32PreflightError
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptConflict,
)
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_run_budget_store import Phase32RunBudgetStoreError
from novel_workflow.storage.phase32_run_repository import Phase32PersistenceError


router = APIRouter(prefix="/api/runs", tags=["runs"])
retired_router = APIRouter(prefix="/api/phase32/runs", tags=["retired-runs"])


class Phase32DraftWriteCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    domain_revision: int = Field(ge=0)
    source_artifact_ref: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any]


def _repository(request: Request):
    return request.app.state.phase32_run_repository


def _execution(request: Request) -> Phase32RunExecutionService:
    service = getattr(request.app.state, "phase32_execution_service", None)
    if not isinstance(service, Phase32RunExecutionService):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "phase32_execution_unavailable",
                "message": "Phase 32 execution is not registered in this process",
            },
        )
    return service


def _artifact_editing(request: Request) -> Phase32ArtifactEditingService:
    service = getattr(request.app.state, "phase32_artifact_editing", None)
    if not isinstance(service, Phase32ArtifactEditingService):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "phase32_artifact_editing_unavailable",
                "message": "Phase 32 Artifact editing is not registered in this process",
            },
        )
    return service


def _exports(request: Request) -> ExportStore:
    store = getattr(request.app.state, "phase32_exports", None)
    if not isinstance(store, ExportStore):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "phase32_exports_unavailable",
                "message": "Phase 32 delivery storage is not registered in this process",
            },
        )
    return store


def _map_execution_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail="Unknown Phase 32 Run")
    if isinstance(exc, Phase32ProviderReadinessAdmissionError):
        return HTTPException(
            status_code=409,
            detail=_execution_gate_detail(
                exc,
                message="Continuity acceptance Provider readiness is not current",
                retryable=True,
                retry_condition="after_provider_readiness_refresh",
                issue_codes=exc.verdict.issue_codes,
            ),
        )
    if isinstance(exc, Phase32ContinuityAdmissionError):
        return HTTPException(
            status_code=409,
            detail=_execution_gate_detail(
                exc,
                message="Continuity acceptance authority is not available for this Run",
                retryable=True,
                retry_condition="after_continuity_authority_restore",
            ),
        )
    if isinstance(exc, Phase32LiveCandidateAuthorizationError):
        return HTTPException(
            status_code=409,
            detail=_execution_gate_detail(
                exc,
                message="Live candidate authorization is not current",
                retryable=True,
                retry_condition="after_live_candidate_reauthorization",
            ),
        )
    if isinstance(exc, Phase32RunAdmissionRequired):
        return HTTPException(
            status_code=409,
            detail=_execution_gate_detail(
                exc,
                message="Continuity acceptance execution admission is not configured",
                retryable=False,
                retry_condition="continuity_admission_service_required",
            ),
        )
    if isinstance(exc, Phase32PreflightError):
        return HTTPException(
            status_code=422,
            detail=_execution_gate_detail(
                exc,
                message="Phase 32 Run preflight rejected the current definition or projection",
                retryable=False,
                retry_condition="run_definition_or_projection_repair_required",
            ),
        )
    if isinstance(exc, Phase32RunBudgetStoreError):
        return HTTPException(
            status_code=409,
            detail=_execution_gate_detail(
                exc,
                message="Continuity acceptance budget authority is inconsistent",
                retryable=False,
                retry_condition="budget_authority_repair_required",
            ),
        )
    if isinstance(exc, (Phase32ExecutionConflict, Phase32DecisionReceiptConflict)):
        return HTTPException(
            status_code=409,
            detail={
                "code": getattr(exc, "code", "phase32_execution_conflict"),
                "message": str(exc),
            },
        )
    if isinstance(exc, Phase32ExecutionError):
        return HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        )
    return HTTPException(status_code=422, detail=str(exc))


def _execution_gate_detail(
    exc: Exception,
    *,
    message: str,
    retryable: bool,
    retry_condition: str,
    issue_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    detail: dict[str, object] = {
        "code": getattr(exc, "code", "phase32_execution_gate_failed"),
        "message": message,
        "retryable": retryable,
        "retry_condition": retry_condition,
    }
    if issue_codes:
        detail["issue_codes"] = list(issue_codes)
    return detail


def _map_artifact_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, Phase32ArtifactEditingConflict):
        return HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        )
    if isinstance(exc, Phase32ArtifactEditingError):
        return HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc)},
        )
    return HTTPException(status_code=422, detail=str(exc))


def _delivery_artifact_type(creation_route_id: str) -> str:
    return "script_delivery" if creation_route_id == "screenplay_sample" else "book_delivery"


def _delivery_source_refs(records: list[object]) -> list[str]:
    """Project immutable source versions without teaching the adapter domain rules."""

    refs: list[str] = []
    for record in records:
        for value in (
            getattr(record, "artifact_ref", ""),
            *getattr(record, "scene_version_refs", ()),
            *getattr(record, "chapter_version_refs", ()),
        ):
            if value and value not in refs:
                refs.append(value)
    return refs


def _image_deferred_detail(envelope: dict[str, Any]) -> dict[str, Any]:
    read_model = envelope["read_model"]
    refs = [
        value.get("artifact_ref")
        for value in read_model.get("artifact_refs", {}).values()
        if isinstance(value, dict) and value.get("artifact_ref")
    ]
    return {
        "code": "image_deferred",
        "message": "图片验收尚未启用，当前 Run 仅完成 CoverBrief，暂不可导出成书。",
        "artifact_type": _delivery_artifact_type(read_model["creation_route_id"]),
        "dependency_status": "deferred",
        "deferred_reason": "image_acceptance_not_in_current_wave",
        "source_artifact_refs": refs,
        "artifact_ref": "",
        "artifact_digest": "",
        "items": [],
    }


def _delivery_not_materialized_detail(envelope: dict[str, Any]) -> dict[str, Any]:
    read_model = envelope["read_model"]
    return {
        "code": "delivery_not_materialized",
        "message": "Run 已结束但交付文件回执不存在，不能返回空成功。",
        "artifact_type": _delivery_artifact_type(read_model["creation_route_id"]),
        "dependency_status": "blocked",
        "deferred_reason": "delivery_artifact_not_materialized",
        "source_artifact_refs": [],
        "artifact_ref": "",
        "artifact_digest": "",
        "items": [],
    }


@router.get("")
async def list_runs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    project_id: str = Query(default="", max_length=240),
    status: str = Query(default="", max_length=64),
) -> dict[str, object]:
    try:
        items = request.app.state.phase32_history_projection.list(
            project_id=project_id,
            status=status,
            limit=limit,
        )
    except (Phase32PersistenceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"items": items, "next_cursor": ""}


@router.post("")
async def create_run() -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "phase27_run_creation_retired",
            "message": "POST /api/projects is the only Phase 32 Project and Run creation authority.",
        },
    )


@router.get("/{run_id}")
async def get_run(request: Request, run_id: str) -> dict[str, Any]:
    return phase32_run_envelope(request, run_id)


@router.get("/{run_id}/exports")
async def list_run_exports(request: Request, run_id: str) -> dict[str, Any]:
    envelope = phase32_run_envelope(request, run_id)
    if envelope["read_model"]["status"] == "image_deferred":
        raise HTTPException(status_code=409, detail=_image_deferred_detail(envelope))
    creation_route_id = envelope["read_model"]["creation_route_id"]
    try:
        if creation_route_id == "screenplay_sample":
            records = _exports(request).list_script_delivery(run_id)
        else:
            records = _exports(request).list_book_delivery(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not records:
        raise HTTPException(status_code=409, detail=_delivery_not_materialized_detail(envelope))
    artifact_type = _delivery_artifact_type(creation_route_id)
    return {
        "run_id": run_id,
        "artifact_type": artifact_type,
        "dependency_status": "ready",
        "deferred_reason": "",
        "source_artifact_refs": _delivery_source_refs(records),
        "artifact_ref": records[0].artifact_ref if records else "",
        "artifact_digest": records[0].artifact_digest if records else "",
        "items": [record.model_dump(mode="json") for record in records],
    }


@router.get("/{run_id}/exports/{export_id}")
async def download_run_export(
    request: Request,
    run_id: str,
    export_id: str,
) -> Response:
    envelope = phase32_run_envelope(request, run_id)
    if envelope["read_model"]["status"] == "image_deferred":
        raise HTTPException(status_code=409, detail=_image_deferred_detail(envelope))
    creation_route_id = envelope["read_model"]["creation_route_id"]
    try:
        if creation_route_id == "screenplay_sample":
            record, content = _exports(request).script_delivery_content(run_id, export_id)
            ascii_stem = "screenplay"
        else:
            record, content = _exports(request).book_delivery_content(run_id, export_id)
            ascii_stem = "book"
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown delivery file") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ascii_name = ascii_stem + "." + ("md" if record.format == "markdown" else record.format)
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(record.filename)}"
    )
    return Response(
        content=content,
        media_type=record.media_type,
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(record.size_bytes),
            "ETag": f'"{record.sha256}"',
            "X-Content-SHA256": record.sha256,
        },
    )


@router.get("/{run_id}/stages/{stage_id}/artifacts/current")
async def get_current_stage_artifact(
    request: Request,
    run_id: str,
    stage_id: str,
    unit_ref: str = Query(default="", max_length=500),
) -> dict[str, Any]:
    try:
        current = _artifact_editing(request).current(
            run_id,
            stage_id,
            unit_ref=unit_ref,
        )
    except (FileNotFoundError, Phase32ArtifactEditingError, ValueError) as exc:
        raise _map_artifact_error(exc) from exc
    return current.model_dump(mode="json")


@router.get("/{run_id}/stage-drafts/{decision_id}")
async def get_stage_draft(
    request: Request,
    run_id: str,
    decision_id: str,
) -> dict[str, Any]:
    try:
        draft = _artifact_editing(request).latest_draft(run_id, decision_id)
    except (FileNotFoundError, Phase32ArtifactEditingError, ValueError) as exc:
        raise _map_artifact_error(exc) from exc
    return {"draft": draft.model_dump(mode="json") if draft else None}


@router.put("/{run_id}/stage-drafts/{decision_id}")
async def put_stage_draft(
    request: Request,
    run_id: str,
    decision_id: str,
    payload: Phase32DraftWriteCommand,
) -> dict[str, Any]:
    try:
        draft = _artifact_editing(request).save_draft(
            run_id,
            decision_id,
            domain_revision=payload.domain_revision,
            source_artifact_ref=payload.source_artifact_ref,
            payload=payload.payload,
        )
    except (FileNotFoundError, Phase32ArtifactEditingError, ValueError) as exc:
        raise _map_artifact_error(exc) from exc
    return {"draft": draft.model_dump(mode="json")}


@router.get("/{run_id}/events")
async def run_events(
    request: Request,
    run_id: str,
    after: int = Query(default=0, ge=0),
):
    repository = _repository(request)
    try:
        repository.definition(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown Phase 32 Run: {run_id}") from exc
    except (Phase32PersistenceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    projection: Phase32EventProjection = request.app.state.phase32_event_projection
    return observe_run_events(request, projection, run_id, after=after)


@router.post("/{run_id}/start")
async def start_run(request: Request, run_id: str) -> dict[str, Any]:
    try:
        outcome = await _execution(request).start(run_id)
    except (
        FileNotFoundError,
        Phase32ContinuityAdmissionError,
        Phase32RunAdmissionRequired,
        Phase32ExecutionConflict,
        Phase32ExecutionError,
        Phase32LiveCandidateAuthorizationError,
        Phase32PreflightError,
        Phase32ProviderReadinessAdmissionError,
        Phase32PersistenceError,
        Phase32RunBudgetStoreError,
    ) as exc:
        raise _map_execution_error(exc) from exc
    return {
        "reused": outcome.reused,
        "run": phase32_run_envelope(request, run_id),
        "decision": outcome.result.decision,
    }


@router.post("/{run_id}/decisions")
async def resolve_decision(
    request: Request,
    run_id: str,
    payload: Phase32DecisionCommand,
) -> dict[str, Any]:
    try:
        outcome = await _execution(request).resume(run_id, payload)
    except (
        FileNotFoundError,
        Phase32ContinuityAdmissionError,
        Phase32DecisionReceiptConflict,
        Phase32RunAdmissionRequired,
        Phase32ExecutionConflict,
        Phase32ExecutionError,
        Phase32LiveCandidateAuthorizationError,
        Phase32PreflightError,
        Phase32ProviderReadinessAdmissionError,
        Phase32PersistenceError,
        Phase32RunBudgetStoreError,
    ) as exc:
        raise _map_execution_error(exc) from exc
    return {
        "reused": outcome.reused,
        "run": phase32_run_envelope(request, run_id),
        "decision": outcome.result.decision,
    }


@router.post("/{run_id}/recoveries")
async def recover_failed_stage(
    request: Request,
    run_id: str,
    payload: Phase32FailureRecoveryCommand,
) -> dict[str, Any]:
    try:
        outcome = await _execution(request).recover(run_id, payload)
    except (
        FileNotFoundError,
        Phase32ContinuityAdmissionError,
        Phase32DecisionReceiptConflict,
        Phase32RunAdmissionRequired,
        Phase32ExecutionConflict,
        Phase32ExecutionError,
        Phase32LiveCandidateAuthorizationError,
        Phase32PreflightError,
        Phase32ProviderReadinessAdmissionError,
        Phase32PersistenceError,
        Phase32RunBudgetStoreError,
    ) as exc:
        raise _map_execution_error(exc) from exc
    return {
        "reused": outcome.reused,
        "run": phase32_run_envelope(request, run_id),
        "decision": outcome.result.decision,
    }


@router.post("/{run_id}/resume")
async def retired_resume(run_id: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "phase32_resume_alias_retired",
            "message": f"Run {run_id} decisions must use POST /api/runs/{{run_id}}/decisions.",
        },
    )


@retired_router.api_route(
    "",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
@retired_router.api_route(
    "/{retired_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def retired_phase32_run_alias(retired_path: str = "") -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "phase32_run_alias_retired",
            "message": "Use the authoritative /api/runs contract.",
        },
    )


__all__ = ["retired_router", "router"]
