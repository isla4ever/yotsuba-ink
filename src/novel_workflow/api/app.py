from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novel_workflow import __version__
from novel_workflow.api.bootstrap import init_app_state
from novel_workflow.api.routes import archive_runs_router, artifact_amendments_router, author_collaboration_router, collaboration_settings_router, contract_repairs_router, creation_wizard_router, cover_assets_router, knowledge_router, projects_router, provider_models_router, providers_router, references_router, retired_runs_router, runs_router, story_bible_router
from novel_workflow.workflows.phase32_creation_wizard import official_workflow_catalog


_DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5176",
    "http://localhost:5176",
)


def _cors_origins() -> list[str]:
    configured = os.environ.get("YOTSUBA_CORS_ORIGINS")
    if configured is None:
        return list(_DEFAULT_CORS_ORIGINS)
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if "*" in origins:
        raise ValueError("YOTSUBA_CORS_ORIGINS must list explicit trusted origins")
    return origins


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Yotsuba Ink API", version=__version__, lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    init_app_state(app)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "providers": app.state.providers.describe(),
            "workflows": [item.workflow_id for item in official_workflow_catalog()],
        }

    app.include_router(projects_router)
    app.include_router(providers_router)
    app.include_router(provider_models_router)
    app.include_router(references_router)
    app.include_router(knowledge_router)
    app.include_router(archive_runs_router)
    app.include_router(cover_assets_router)
    app.include_router(story_bible_router)
    app.include_router(runs_router)
    app.include_router(contract_repairs_router)
    app.include_router(artifact_amendments_router)
    app.include_router(retired_runs_router)
    app.include_router(author_collaboration_router)
    app.include_router(collaboration_settings_router)
    app.include_router(creation_wizard_router)
    return app


app = create_app()
