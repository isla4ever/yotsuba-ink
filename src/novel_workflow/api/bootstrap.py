from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from novel_workflow.knowledge import KnowledgeBase
from novel_workflow.memory.wiki import WikiStore
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.references import ReferenceStore, TavilySearchClient
from novel_workflow.storage.json_store import JsonStore
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.schemas import PromptTemplate, ProviderProfile
from novel_workflow.workflows.templates import default_prompt_templates, default_provider_profiles, default_workflow


def init_app_state(app: FastAPI, data_dir: Path | None = None) -> None:
    root = data_dir or Path("runtime/novel_workflow")
    app.state.run_store = RunStore(root / "runs")
    app.state.workflow_store = JsonStore(root / "workflows")
    app.state.provider_store = JsonStore(root / "providers")
    app.state.prompt_store = JsonStore(root / "prompts")
    app.state.wiki_store = WikiStore(root / "wiki")
    app.state.reference_store = ReferenceStore(root / "references")
    app.state.reference_search = TavilySearchClient()
    app.state.knowledge_base = KnowledgeBase(root / "knowledge")
    app.state.providers = ProviderRegistry.from_env()
    seed_defaults(app)


def seed_defaults(app: FastAPI) -> None:
    workflow = default_workflow()
    try:
        existing = app.state.workflow_store.read(workflow.id)
        has_retired_quality_node = any(node.get("type") == "quality_gate" for node in existing.get("nodes", []))
        if existing.get("version") != workflow.version or not existing.get("global_inputs") or has_retired_quality_node:
            app.state.workflow_store.write(workflow.id, workflow.model_dump())
    except FileNotFoundError:
        app.state.workflow_store.write(workflow.id, workflow.model_dump())

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

    app.state.providers = ProviderRegistry.from_profiles(
        [ProviderProfile.model_validate(item) for item in app.state.provider_store.list()]
    )


def list_provider_profiles(app: FastAPI) -> list[ProviderProfile]:
    return [ProviderProfile.model_validate(item) for item in app.state.provider_store.list()]


def list_prompt_templates(app: FastAPI) -> list[PromptTemplate]:
    return [PromptTemplate.model_validate(item) for item in app.state.prompt_store.list()]
