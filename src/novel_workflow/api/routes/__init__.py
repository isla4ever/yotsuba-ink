from novel_workflow.api.routes.artifact_amendments import (
    router as artifact_amendments_router,
)
from novel_workflow.api.routes.knowledge import router as knowledge_router
from novel_workflow.api.routes.cover_assets import router as cover_assets_router
from novel_workflow.api.routes.projects import router as projects_router
from novel_workflow.api.routes.provider_models import router as provider_models_router
from novel_workflow.api.routes.providers import router as providers_router
from novel_workflow.api.routes.references import router as references_router
from novel_workflow.api.routes.runs import retired_router as retired_runs_router
from novel_workflow.api.routes.runs import router as runs_router
from novel_workflow.api.routes.story_bible import router as story_bible_router
from novel_workflow.api.routes.author_collaboration import router as author_collaboration_router
from novel_workflow.api.routes.collaboration_settings import router as collaboration_settings_router
from novel_workflow.api.routes.contract_repairs import router as contract_repairs_router
from novel_workflow.api.routes.creation_wizard import router as creation_wizard_router

__all__ = [
    "archive_runs_router",
    "artifact_amendments_router",
    "cover_assets_router",
    "knowledge_router",
    "projects_router",
    "provider_models_router",
    "providers_router",
    "references_router",
    "retired_runs_router",
    "runs_router",
    "story_bible_router",
    "author_collaboration_router",
    "collaboration_settings_router",
    "contract_repairs_router",
    "creation_wizard_router",
]
from novel_workflow.api.routes.archive_runs import router as archive_runs_router
