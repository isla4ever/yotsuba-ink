"""Thin HTTP adapter for Phase 32 contract quarantine and repair."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from novel_workflow.api.dependencies import phase32_run_envelope
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingConflict,
    Phase32ArtifactEditingError,
)
from novel_workflow.orchestration.phase32_contract_repair import (
    Phase32ContractRepairCommand,
    Phase32ContractRepairConflict,
    Phase32ContractRepairError,
    Phase32ContractRepairService,
)
from novel_workflow.orchestration.phase32_execution_service import (
    Phase32ExecutionConflict,
)
from novel_workflow.orchestration.phase32_graph_execution import Phase32ExecutionError
from novel_workflow.orchestration.phase32_run_preflight import Phase32PreflightError
from novel_workflow.storage.phase32_contract_repair_store import (
    Phase32ContractRepairStoreConflict,
)
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceiptConflict,
)
from novel_workflow.storage.phase32_run_repository import Phase32PersistenceError


router = APIRouter(prefix="/api/runs", tags=["contract-repairs"])


def _service(request: Request) -> Phase32ContractRepairService:
    service = getattr(request.app.state, "phase32_contract_repairs", None)
    if not isinstance(service, Phase32ContractRepairService):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "phase32_contract_repair_unavailable",
                "message": "Phase 32 contract repair is not registered in this process",
            },
        )
    return service


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(
        exc,
        (
            Phase32ArtifactEditingConflict,
            Phase32ContractRepairConflict,
            Phase32ContractRepairStoreConflict,
            Phase32ExecutionConflict,
            Phase32ProviderOperationReceiptConflict,
        ),
    ):
        return HTTPException(
            status_code=409,
            detail={
                "code": getattr(exc, "code", "phase32_contract_repair_conflict"),
                "message": str(exc),
            },
        )
    if isinstance(
        exc,
        (
            Phase32ArtifactEditingError,
            Phase32ContractRepairError,
            Phase32ExecutionError,
            Phase32PreflightError,
            Phase32PersistenceError,
        ),
    ):
        return HTTPException(
            status_code=422,
            detail={
                "code": getattr(exc, "code", "phase32_contract_repair_invalid"),
                "message": str(exc),
            },
        )
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/{run_id}/contract-quarantines/{provider_receipt_ref}")
async def get_contract_quarantine(
    request: Request,
    run_id: str,
    provider_receipt_ref: str,
) -> dict[str, Any]:
    try:
        quarantine = _service(request).inspect(run_id, provider_receipt_ref)
    except (FileNotFoundError, ValueError) as exc:
        raise _map_error(exc) from exc
    return {"quarantine": quarantine.model_dump(mode="json")}


@router.get("/{run_id}/contract-quarantine")
async def get_current_contract_quarantine(
    request: Request,
    run_id: str,
) -> dict[str, Any]:
    try:
        quarantine = _service(request).inspect_current(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise _map_error(exc) from exc
    return {"quarantine": quarantine.model_dump(mode="json")}


@router.post("/{run_id}/contract-repairs")
async def repair_contract_candidate(
    request: Request,
    run_id: str,
    payload: Phase32ContractRepairCommand,
) -> dict[str, Any]:
    try:
        outcome = await _service(request).repair(run_id, payload)
    except (FileNotFoundError, ValueError) as exc:
        raise _map_error(exc) from exc
    return {
        "reused": outcome.reused,
        "repair": outcome.repair.model_dump(mode="json"),
        "run": phase32_run_envelope(request, run_id),
        "decision": outcome.decision,
    }


__all__ = ["router"]
