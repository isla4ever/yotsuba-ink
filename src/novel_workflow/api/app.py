from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from novel_workflow.api.reference_context import (
    append_rag_event as _append_rag_event,
    compact as _compact,
    enrich_reference_summary as _enrich_reference_summary,
    merged_reference_summary as _merged_reference_summary,
    rag_blocking_issue as _rag_blocking_issue,
    string_list as _string_list,
    summary_from_knowledge_results as _summary_from_knowledge_results,
    summary_from_search_results as _summary_from_search_results,
    summary_from_urls as _summary_from_urls,
)
from novel_workflow.api.routes import knowledge_router, prompts_router, providers_router, references_router, runs_router, workflow_router
from novel_workflow.api.state import init_app_state, seed_defaults as _seed_defaults


def create_app() -> FastAPI:
    app = FastAPI(title="Novel Workflow API", version="0.1.0")
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
    app.include_router(providers_router)
    app.include_router(prompts_router)
    app.include_router(references_router)
    app.include_router(knowledge_router)
    app.include_router(runs_router)
    return app


app = create_app()
