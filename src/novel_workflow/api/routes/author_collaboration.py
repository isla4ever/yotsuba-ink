from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from novel_workflow.api.dependencies import collaboration_settings_service
from novel_workflow.api.sse import observe_collaboration_events
from novel_workflow.orchestration.phase32_author_collaboration import (
    Phase32AuthorCollaborationError,
    Phase32AuthorCollaborationService,
    Phase32ContextReconfirmationRequired,
    Phase32PatchWritebackUnavailable,
)
from novel_workflow.orchestration.collaboration_settings import (
    CollaborationSettingsError,
)
from novel_workflow.output_contracts.phase32_author_collaboration import (
    CreatePhase32CollaborationThreadRequest,
    CreatePhase32CollaborationTurnRequest,
    Phase32CollaborationContextPreviewRequest,
    UpdatePhase32CollaborationThreadRequest,
)
from novel_workflow.references.collaboration_context import (
    CollaborationContextBudgetExceeded,
    CollaborationContextError,
)
from novel_workflow.references.phase32_collaboration_context import (
    Phase32CollaborationContextCompiler,
)
from novel_workflow.runtime.graph.phase32_collaboration_execution import (
    Phase32CollaborationExecutor,
)


router = APIRouter(prefix="/api/runs/{run_id}/collaboration", tags=["author-collaboration"])


def _service(request: Request) -> Phase32AuthorCollaborationService:
    context = Phase32CollaborationContextCompiler(
        request.app.state.phase32_run_repository,
        request.app.state.phase32_artifact_store,
        request.app.state.phase32_artifact_editing,
        request.app.state.phase32_collaboration,
        knowledge_base=request.app.state.knowledge_base,
    )
    executor = Phase32CollaborationExecutor(
        request.app.state.phase32_collaboration,
        request.app.state.phase32_collaboration_contexts,
        context,
        request.app.state.phase32_provider_inputs,
        request.app.state.phase32_provider_operations,
        request.app.state.phase32_provider_gateway,
    )
    return Phase32AuthorCollaborationService(
        request.app.state.phase32_run_repository,
        request.app.state.phase32_collaboration,
        request.app.state.phase32_collaboration_contexts,
        context,
        executor,
        execution_resolver=collaboration_settings_service(
            request
        ).freeze_phase32_new_thread_execution,
    )


@router.get("/threads")
def list_threads(request: Request, run_id: str) -> dict[str, Any]:
    try:
        items = _service(request).list_threads(run_id)
        return {"run_id": run_id, "threads": [item.model_dump(mode="json") for item in items]}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/threads", status_code=201)
def create_thread(
    request: Request,
    run_id: str,
    payload: CreatePhase32CollaborationThreadRequest,
) -> dict[str, Any]:
    try:
        return _service(request).create_thread(run_id, payload).model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/threads/{thread_id}")
def get_thread(request: Request, run_id: str, thread_id: str) -> dict[str, Any]:
    try:
        value = _service(request).read_thread(run_id, thread_id)
        return {
            key: [item.model_dump(mode="json") for item in item_or_items]
            if isinstance(item_or_items, list)
            else item_or_items.model_dump(mode="json")
            for key, item_or_items in value.items()
        }
    except Exception as exc:
        raise _http_error(exc) from exc


@router.patch("/threads/{thread_id}")
def update_thread(
    request: Request,
    run_id: str,
    thread_id: str,
    payload: UpdatePhase32CollaborationThreadRequest,
) -> dict[str, Any]:
    try:
        return _service(request).update_thread(
            run_id,
            thread_id,
            payload,
        ).model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.delete("/threads/{thread_id}")
def delete_thread(request: Request, run_id: str, thread_id: str) -> dict[str, Any]:
    try:
        return _service(request).delete_thread(run_id, thread_id).model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/threads/{thread_id}/context-preview")
def preview_context(
    request: Request,
    run_id: str,
    thread_id: str,
    payload: Phase32CollaborationContextPreviewRequest,
) -> dict[str, Any]:
    try:
        return _service(request).preview_context(
            run_id,
            thread_id,
            payload,
        ).model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/threads/{thread_id}/turns", status_code=202)
async def create_turn(
    request: Request,
    run_id: str,
    thread_id: str,
    payload: CreatePhase32CollaborationTurnRequest,
) -> dict[str, Any]:
    try:
        service = _service(request)
        turn = service.create_turn(run_id, thread_id, payload)
        if turn.status in {"queued", "streaming"}:
            turn = await service.execute_turn(run_id, thread_id, turn.turn_id)
        return turn.model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/threads/{thread_id}/turns/{turn_id}/cancel")
def cancel_turn(
    request: Request,
    run_id: str,
    thread_id: str,
    turn_id: str,
) -> dict[str, Any]:
    try:
        turn = request.app.state.phase32_collaboration.read_turn(
            run_id,
            thread_id,
            turn_id,
        )
        if turn.status in {"completed", "cancelled", "failed", "contract_rejected"}:
            return turn.model_dump(mode="json")
        if turn.status == "queued":
            turn = _service(request).cancel_queued_turn(run_id, thread_id, turn_id)
        return {**turn.model_dump(mode="json"), "cancellation_requested": False}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/threads/{thread_id}/stream")
def stream_thread(
    request: Request,
    run_id: str,
    thread_id: str,
    after: int = Query(default=0, ge=0),
):
    try:
        request.app.state.phase32_collaboration.read_thread(run_id, thread_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return observe_collaboration_events(
        request,
        request.app.state.phase32_collaboration,
        run_id,
        thread_id,
        after=after,
    )


@router.post("/patches/{patch_id}/accept")
def accept_patch(request: Request, run_id: str, patch_id: str) -> dict[str, Any]:
    try:
        return _service(request).accept_patch(run_id, patch_id).model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/patches/{patch_id}/reject")
def reject_patch(request: Request, run_id: str, patch_id: str) -> dict[str, Any]:
    try:
        return _service(request).reject_patch(run_id, patch_id).model_dump(mode="json")
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail={"code": "not_found", "message": str(exc)})
    if isinstance(exc, CollaborationContextBudgetExceeded):
        return HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": str(exc),
                "used_chars": exc.used_chars,
                "budget_chars": exc.budget_chars,
            },
        )
    if isinstance(
        exc,
        (Phase32ContextReconfirmationRequired, Phase32PatchWritebackUnavailable),
    ):
        return HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, CollaborationContextError):
        return HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, Phase32AuthorCollaborationError):
        status = 403 if exc.code == "author_collaboration_unavailable" else 409
        return HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, CollaborationSettingsError):
        return HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})
    if isinstance(exc, ValueError):
        code = str(exc) if str(exc) in {"turn_replay_conflict"} else "invalid_request"
        return HTTPException(status_code=409, detail={"code": code, "message": str(exc)})
    return HTTPException(
        status_code=500,
        detail={
            "code": "author_collaboration_internal",
            "message": "Author collaboration request failed",
        },
    )


__all__ = ["router"]
