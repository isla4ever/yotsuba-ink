"""Committed planning Artifact amendment HTTP adapter."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.api.dependencies import phase32_run_envelope
from novel_workflow.orchestration.phase32_amendment_branch import (
    Phase32AmendmentBranchConflict,
    Phase32AmendmentBranchError,
    Phase32AmendmentBranchService,
)
from novel_workflow.orchestration.phase32_artifact_amendment import (
    Phase32ArtifactAmendmentBlocked,
    Phase32ArtifactAmendmentConflict,
    Phase32ArtifactAmendmentError,
    Phase32ArtifactAmendmentService,
)
from novel_workflow.output_contracts.phase32_artifact_amendment import (
    AmendmentApplyScope,
)
from novel_workflow.storage.phase32_artifact_amendment_store import (
    Phase32ArtifactAmendmentIdempotencyConflict,
    Phase32ArtifactAmendmentStoreError,
)
from novel_workflow.storage.phase32_amendment_branch_store import (
    Phase32AmendmentBranchIdempotencyConflict,
    Phase32AmendmentBranchStoreError,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStoreError
from novel_workflow.storage.phase32_project_catalog_store import (
    Phase32ProjectCatalogError,
)
from novel_workflow.storage.phase32_run_repository import Phase32PersistenceError


router = APIRouter(prefix="/api/runs", tags=["runs"])


class Phase32AmendmentCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_artifact_ref: str = Field(min_length=1, max_length=500)
    proposed_payload: dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=240)
    author_note: str = Field(default="", max_length=4_000)


class Phase32AmendmentApplyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scope: AmendmentApplyScope
    idempotency_key: str = Field(min_length=1, max_length=240)


class Phase32AmendmentBranchCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    apply_receipt_id: str = Field(pattern=r"^p32-amendment-receipt-[a-f0-9]{32}$")
    source_domain_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=240)


def _artifact_amendments(request: Request) -> Phase32ArtifactAmendmentService:
    service = getattr(
        request.app.state,
        "phase32_artifact_amendment_service",
        None,
    )
    if not isinstance(service, Phase32ArtifactAmendmentService):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "phase32_artifact_amendment_unavailable",
                "message": "Phase 32 Artifact amendment is not registered in this process",
            },
        )
    return service


def _amendment_branches(request: Request) -> Phase32AmendmentBranchService:
    service = getattr(request.app.state, "phase32_amendment_branch_service", None)
    if not isinstance(service, Phase32AmendmentBranchService):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "phase32_amendment_branch_unavailable",
                "message": "Phase 32 amendment branch is not registered in this process",
            },
        )
    return service


def _map_amendment_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(
        exc,
        (
            Phase32ArtifactAmendmentBlocked,
            Phase32ArtifactAmendmentConflict,
            Phase32ArtifactAmendmentIdempotencyConflict,
        ),
    ):
        return HTTPException(
            status_code=409,
            detail={
                "code": getattr(exc, "code", "phase32_artifact_amendment_conflict"),
                "message": str(exc),
            },
        )
    if isinstance(
        exc,
        (Phase32ArtifactAmendmentError, Phase32ArtifactAmendmentStoreError),
    ):
        return HTTPException(
            status_code=422,
            detail={
                "code": getattr(exc, "code", "phase32_artifact_amendment_invalid"),
                "message": str(exc),
            },
        )
    return HTTPException(status_code=422, detail=str(exc))


def _map_branch_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(
        exc,
        (
            Phase32AmendmentBranchConflict,
            Phase32AmendmentBranchIdempotencyConflict,
            Phase32ProjectCatalogError,
        ),
    ):
        return HTTPException(
            status_code=409,
            detail={
                "code": getattr(exc, "code", "phase32_amendment_branch_conflict"),
                "message": str(exc),
            },
        )
    if isinstance(
        exc,
        (
            Phase32AmendmentBranchError,
            Phase32AmendmentBranchStoreError,
            Phase32ArtifactStoreError,
            Phase32PersistenceError,
        ),
    ):
        return HTTPException(
            status_code=422,
            detail={
                "code": getattr(exc, "code", "phase32_amendment_branch_invalid"),
                "message": str(exc),
            },
        )
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/{run_id}/planning/{stage_id}/amendments")
async def create_planning_amendment(
    request: Request,
    run_id: str,
    stage_id: str,
    payload: Phase32AmendmentCreateCommand,
) -> dict[str, Any]:
    try:
        amendment, impact, reused = _artifact_amendments(request).create(
            run_id,
            stage_id,
            source_artifact_ref=payload.source_artifact_ref,
            proposed_payload=payload.proposed_payload,
            idempotency_key=payload.idempotency_key,
            author_note=payload.author_note,
        )
    except (
        FileNotFoundError,
        Phase32ArtifactAmendmentError,
        Phase32ArtifactAmendmentStoreError,
        ValueError,
    ) as exc:
        raise _map_amendment_error(exc) from exc
    return {
        "reused": reused,
        "amendment": amendment.model_dump(mode="json"),
        "impact": impact.model_dump(mode="json"),
    }


@router.get("/{run_id}/planning/amendments/{amendment_id}/impact")
async def get_planning_amendment_impact(
    request: Request,
    run_id: str,
    amendment_id: str,
) -> dict[str, Any]:
    try:
        impact = _artifact_amendments(request).impact(run_id, amendment_id)
    except (
        FileNotFoundError,
        Phase32ArtifactAmendmentError,
        Phase32ArtifactAmendmentStoreError,
        ValueError,
    ) as exc:
        raise _map_amendment_error(exc) from exc
    return {"impact": impact.model_dump(mode="json")}


@router.post("/{run_id}/planning/amendments/{amendment_id}/apply")
async def apply_planning_amendment(
    request: Request,
    run_id: str,
    amendment_id: str,
    payload: Phase32AmendmentApplyCommand,
) -> dict[str, Any]:
    try:
        outcome = _artifact_amendments(request).apply(
            run_id,
            amendment_id,
            scope=payload.scope,
            idempotency_key=payload.idempotency_key,
        )
    except (
        FileNotFoundError,
        Phase32ArtifactAmendmentError,
        Phase32ArtifactAmendmentStoreError,
        Phase32PersistenceError,
        ValueError,
    ) as exc:
        raise _map_amendment_error(exc) from exc
    return {
        "reused": outcome.reused,
        "receipt": outcome.receipt.model_dump(mode="json"),
        "run": phase32_run_envelope(request, run_id),
    }


@router.get("/{run_id}/planning/amendments/{amendment_id}/branch")
async def get_planning_amendment_branch(
    request: Request,
    run_id: str,
    amendment_id: str,
) -> dict[str, Any]:
    try:
        branch_service = _amendment_branches(request)
        apply_receipt = branch_service.apply_receipt(
            run_id,
            amendment_id,
        )
        receipt = branch_service.receipt(run_id, amendment_id)
    except (
        Phase32ArtifactAmendmentStoreError,
        Phase32AmendmentBranchStoreError,
        ValueError,
    ) as exc:
        if isinstance(exc, Phase32ArtifactAmendmentStoreError):
            raise _map_amendment_error(exc) from exc
        raise _map_branch_error(exc) from exc
    return {
        "apply_receipt": (
            apply_receipt.model_dump(mode="json") if apply_receipt else None
        ),
        "receipt": receipt.model_dump(mode="json") if receipt else None,
        "target_run": (
            phase32_run_envelope(request, receipt.target_run_id) if receipt else None
        ),
    }


@router.post("/{run_id}/planning/amendments/{amendment_id}/branch")
async def create_planning_amendment_branch(
    request: Request,
    run_id: str,
    amendment_id: str,
    payload: Phase32AmendmentBranchCommand,
) -> dict[str, Any]:
    try:
        outcome = _amendment_branches(request).branch(
            run_id,
            amendment_id,
            apply_receipt_id=payload.apply_receipt_id,
            source_domain_revision=payload.source_domain_revision,
            idempotency_key=payload.idempotency_key,
        )
    except (
        FileNotFoundError,
        Phase32AmendmentBranchError,
        Phase32AmendmentBranchStoreError,
        Phase32ArtifactStoreError,
        Phase32ProjectCatalogError,
        Phase32PersistenceError,
        ValueError,
    ) as exc:
        raise _map_branch_error(exc) from exc
    return {
        "reused": outcome.reused,
        "receipt": outcome.receipt.model_dump(mode="json"),
        "source_run": phase32_run_envelope(request, run_id),
        "target_run": phase32_run_envelope(request, outcome.receipt.target_run_id),
    }


__all__ = ["router"]
