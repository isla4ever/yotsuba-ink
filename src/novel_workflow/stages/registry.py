from __future__ import annotations

from typing import Any

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.export_delivery import build_export_artifact
from novel_workflow.orchestration.provider_execution import execute_text_provider_call
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.workflows.schemas import NovelRunState, PromptTemplate, WorkflowNode
from novel_workflow.stages.prompt_plan import PromptPlanBuilder


class StageRegistry:
    def __init__(self, providers: ProviderRegistry, wiki_store: WikiStore, prompt_templates: list[PromptTemplate] | None = None, run_store: Any | None = None) -> None:
        self.providers = providers
        self.wiki_store = wiki_store
        self.run_store = run_store
        self.prompt_templates = {template.id: template.content for template in prompt_templates or []}
        self.prompt_builder = PromptPlanBuilder()

    async def execute(self, node: WorkflowNode, state: NovelRunState) -> Any:
        if node.type in {"info_recommend", "summary", "outline", "detail_outline", "chapter_text", "cover_image"}:
            return await self._text_stage(node, state)
        if node.type == "export_artifact":
            return build_export_artifact(
                state,
                cover_asset_reader=self.run_store.read_cover_asset if self.run_store is not None else None,
            )
        raise ValueError(f"Unsupported node type: {node.type}")

    async def _text_stage(self, node: WorkflowNode, state: NovelRunState) -> Any:
        prompt = self._render_prompt(node, state)
        schema = None if node.type == "chapter_text" else node.output_schema
        chapter = state.chapter_context_packets[-1].chapter if node.type == "chapter_text" and state.chapter_context_packets else ""
        kind = "candidate" if node.variant_policy.enabled else "generation"
        return await execute_text_provider_call(
            self.providers,
            node,
            state,
            prompt=prompt,
            task_name=node.type,
            context={**state.inputs, "artifacts": state.artifacts},
            schema=schema,
            kind=kind,
            chapter=chapter,
            idempotency_root=f"{state.run_id}:{node.id}:{chapter or 'stage'}",
            run_store=self.run_store,
        )

    def _render_prompt(self, node: WorkflowNode, state: NovelRunState) -> str:
        return self.prompt_builder.build(node, state, template_content=self.prompt_templates.get(node.prompt_template_id, ""))
