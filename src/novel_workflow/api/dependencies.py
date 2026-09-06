from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from novel_workflow.api.bootstrap import list_provider_profiles
from novel_workflow.orchestration.collaboration_settings import (
    CollaborationSettingsService,
)
from novel_workflow.storage.phase32_run_repository import Phase32PersistenceError


def collaboration_settings_service(request: Request) -> CollaborationSettingsService:
    return CollaborationSettingsService(
        request.app.state.collaboration_settings_store,
        providers=lambda: list_provider_profiles(request.app),
        secret_resolver=request.app.state.provider_secret_store.get_api_key,
    )


def run_state_or_404(app: FastAPI, run_id: str) -> dict[str, Any]:
    try:
        stored = app.state.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from exc
    return stored.get("state") or {}


def phase32_run_envelope(request: Request, run_id: str) -> dict[str, Any]:
    try:
        record = request.app.state.phase32_run_repository.read(run_id)
        summary = request.app.state.phase32_history_projection.item(
            record.read_model,
            definition=record.definition,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown Phase 32 Run: {run_id}",
        ) from exc
    except (Phase32PersistenceError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "definition": record.definition.model_dump(mode="json"),
        "read_model": record.read_model.model_dump(mode="json"),
        "summary": summary,
    }
