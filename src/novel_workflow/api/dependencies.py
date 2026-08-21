from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from novel_workflow.api.bootstrap import list_provider_profiles
from novel_workflow.orchestration.collaboration_settings import (
    CollaborationSettingsService,
)


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
