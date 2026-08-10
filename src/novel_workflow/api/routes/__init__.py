from novel_workflow.api.routes.knowledge import router as knowledge_router
from novel_workflow.api.routes.cover_assets import router as cover_assets_router
from novel_workflow.api.routes.projects import router as projects_router
from novel_workflow.api.routes.prompts import router as prompts_router
from novel_workflow.api.routes.provider_models import router as provider_models_router
from novel_workflow.api.routes.providers import router as providers_router
from novel_workflow.api.routes.references import router as references_router
from novel_workflow.api.routes.run_history import router as run_history_router
from novel_workflow.api.routes.runs import router as runs_router
from novel_workflow.api.routes.workflow import router as workflow_router

__all__ = [
    "archive_runs_router",
    "cover_assets_router",
    "knowledge_router",
    "projects_router",
    "prompts_router",
    "provider_models_router",
    "providers_router",
    "references_router",
    "run_history_router",
    "runs_router",
    "workflow_router",
]
from novel_workflow.api.routes.archive_runs import router as archive_runs_router
