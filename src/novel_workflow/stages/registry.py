from __future__ import annotations

from typing import Any

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.workflows.schemas import NovelRunState, WorkflowNode
from novel_workflow.stages.prompt_plan import PromptPlanBuilder


class StageRegistry:
    def __init__(self, providers: ProviderRegistry, wiki_store: WikiStore) -> None:
        self.providers = providers
        self.wiki_store = wiki_store
        self.prompt_builder = PromptPlanBuilder()

    async def execute(self, node: WorkflowNode, state: NovelRunState) -> Any:
        if node.type in {"info_recommend", "summary", "outline", "detail_outline", "chapter_text"}:
            return await self._text_stage(node, state)
        if node.type == "cover_image":
            prompt = self._render_prompt(node, state)
            result = await self.providers.image_provider.generate_cover(prompt, context=state.inputs)
            state.cover_results.append(result)
            return result
        if node.type == "export_artifact":
            return self._export_artifact(state)
        raise ValueError(f"Unsupported node type: {node.type}")

    async def _text_stage(self, node: WorkflowNode, state: NovelRunState) -> str:
        prompt = self._render_prompt(node, state)
        return await self.providers.text_provider.generate_text(
            prompt,
            task_name=node.type,
            context={**state.inputs, "artifacts": state.artifacts},
        )

    def _render_prompt(self, node: WorkflowNode, state: NovelRunState) -> str:
        return self.prompt_builder.build(node, state)

    def _export_artifact(self, state: NovelRunState) -> dict[str, Any]:
        return {
            "format": "json",
            "artifact_keys": list(state.artifacts.keys()),
            "quality_reports": state.quality_reports,
            "quality_events": [event.model_dump() for event in state.quality_events],
            "cover_results": state.cover_results,
        }
