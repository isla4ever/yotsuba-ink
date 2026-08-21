from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI

from novel_workflow.knowledge import KnowledgeBase
from novel_workflow.orchestration.run_preflight import RunPreflightService
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.runtime.graph.execution_service import NarrativeExecutionService
from novel_workflow.runtime.graph.provider_gateway import FrozenNarrativeProviderGateway
from novel_workflow.archive import LegacyRunViewer
from novel_workflow.references import ReferenceStore, TavilySearchClient
from novel_workflow.storage.json_store import JsonStore
from novel_workflow.storage.project_store import ProjectStore
from novel_workflow.storage.collaboration_settings_store import CollaborationSettingsStore
from novel_workflow.storage.provider_profile_store import ProviderProfileStore
from novel_workflow.storage.provider_secret_store import ProviderSecretStore
from novel_workflow.storage.run_history_projection import RunHistoryProjection
from novel_workflow.workflows.schemas import PromptTemplate, ProviderProfile
from novel_workflow.workflows.templates import (
    default_prompt_templates,
    default_provider_profiles,
    official_workflows,
)

def init_app_state(app: FastAPI, data_dir: Path | None = None) -> None:
    root = data_dir or Path("runtime/novel_workflow")
    app.state.workflow_store = JsonStore(root / "workflows")
    app.state.provider_store = ProviderProfileStore(root / "provider_profiles.sqlite3")
    app.state.provider_secret_store = ProviderSecretStore(root / "provider_secrets.sqlite3")
    app.state.prompt_store = JsonStore(root / "prompts")
    app.state.reference_store = ReferenceStore(root / "references")
    app.state.reference_search = TavilySearchClient()
    app.state.knowledge_base = KnowledgeBase(root / "knowledge")
    app.state.collaboration_settings_store = CollaborationSettingsStore(
        root / "collaboration_settings"
    )
    app.state.providers = ProviderRegistry.from_env()
    seed_defaults(app)
    app.state.run_preflight = RunPreflightService(
        provider_store=app.state.provider_store,
        prompt_store=app.state.prompt_store,
        secret_store=app.state.provider_secret_store,
    )
    app.state.narrative_execution = NarrativeExecutionService(
        root / "native_runtime",
        lambda: FrozenNarrativeProviderGateway(
            app.state.provider_secret_store.get_api_key,
        ),
    )
    app.state.narrative_stores = app.state.narrative_execution.stores
    app.state.run_history = RunHistoryProjection(
        app.state.narrative_stores.runs,
        app.state.narrative_stores.exports,
        app.state.narrative_stores.chapters,
        app.state.narrative_stores.artifacts,
    )
    app.state.project_store = ProjectStore(
        root / "projects",
        workflow_store=app.state.workflow_store,
        run_history=app.state.run_history,
    )
    # Historical runs are an offline, read-only surface and never share the
    # production Run repository or graph checkpoint directory.
    app.state.legacy_run_viewer = LegacyRunViewer(root / "archive")


def seed_defaults(app: FastAPI) -> None:
    # Official templates are code-owned. User templates and project workflows
    # in the same store remain untouched.
    for workflow in official_workflows():
        expected = workflow.model_dump()
        try:
            existing = app.state.workflow_store.read(workflow.id)
            if _workflow_digest(existing) != _workflow_digest(expected):
                app.state.workflow_store.write(workflow.id, expected)
        except FileNotFoundError:
            app.state.workflow_store.write(workflow.id, expected)

    for provider in default_provider_profiles():
        try:
            app.state.provider_store.read(provider.id)
        except FileNotFoundError:
            app.state.provider_store.write(provider.id, provider.model_dump())
    for prompt in default_prompt_templates():
        try:
            existing = app.state.prompt_store.read(prompt.id)
            if existing != prompt.model_dump():
                app.state.prompt_store.write(prompt.id, prompt.model_dump())
        except FileNotFoundError:
            app.state.prompt_store.write(prompt.id, prompt.model_dump())

    valid_prompt_ids = {prompt.id for prompt in default_prompt_templates()}
    for prompt in app.state.prompt_store.list():
        if prompt.get("id") not in valid_prompt_ids or prompt.get("stage_type") == "quality_gate":
            app.state.prompt_store.delete(str(prompt.get("id") or ""))

    refresh_provider_registry(app)


def _workflow_digest(payload: dict) -> str:
    """Canonical content digest for the seeded default workflow comparison."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def list_provider_profiles(app: FastAPI) -> list[ProviderProfile]:
    return [ProviderProfile.model_validate(item) for item in app.state.provider_store.list()]


def refresh_provider_registry(app: FastAPI) -> None:
    secret_store = getattr(app.state, "provider_secret_store", None)
    app.state.providers = ProviderRegistry.from_profiles(
        list_provider_profiles(app),
        secret_resolver=secret_store.get_api_key if secret_store is not None else None,
    )


def list_prompt_templates(app: FastAPI) -> list[PromptTemplate]:
    return [PromptTemplate.model_validate(item) for item in app.state.prompt_store.list()]
