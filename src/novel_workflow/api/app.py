from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novel_workflow.api.bootstrap import init_app_state
from novel_workflow.api.routes import chapter_revisions_router, chapter_reviews_router, cover_assets_router, exports_router, knowledge_router, projects_router, prompts_router, provider_models_router, providers_router, references_router, run_history_router, runs_router, workflow_router
from novel_workflow.references.context_injection import enrich_reference_summary as _enrich_reference_summary


def create_app() -> FastAPI:
    app = FastAPI(title="Yotsuba Ink API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    init_app_state(app)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "providers": app.state.providers.describe(),
            "workflows": [item["id"] for item in app.state.workflow_store.list()],
        }

    app.include_router(workflow_router)
    app.include_router(projects_router)
    app.include_router(providers_router)
    app.include_router(provider_models_router)
    app.include_router(prompts_router)
    app.include_router(references_router)
    app.include_router(knowledge_router)
    app.include_router(run_history_router)
    app.include_router(runs_router)
    app.include_router(cover_assets_router)
    app.include_router(chapter_revisions_router)
    app.include_router(chapter_reviews_router)
    app.include_router(exports_router)
    return app


app = create_app()
