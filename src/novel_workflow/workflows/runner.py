from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.memory.wiki import WikiStore
from novel_workflow.orchestration.chapters import run_chapter_text_node
from novel_workflow.orchestration.control import pause_if_requested, wait_for_artifact_approval
from novel_workflow.orchestration.helpers import (
    character_graph,
    chapter_content,
    chapter_count,
    chapter_deltas,
    continuity_state,
    detail_outline_issue,
    effective_variant_policy,
    memory_query,
    node_with_mode_policy,
    quality_event,
    update_worldbuilding_state,
    variant_score,
    wiki_state,
)
from novel_workflow.orchestration.quality import quality_loop_for_result
from novel_workflow.orchestration.stream import stream_workflow
from novel_workflow.orchestration.variants import execute_with_variants
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.quality.engine import QualityEngine
from novel_workflow.stages.registry import StageRegistry
from novel_workflow.storage.run_store import RunStore
from novel_workflow.workflows.compiler import NovelWorkflowCompiler
from novel_workflow.workflows.schemas import NovelRunState, VariantPolicy, WorkflowDefinition


class NovelWorkflowRunner:
    def __init__(
        self,
        providers: ProviderRegistry,
        wiki_store: WikiStore,
        run_store: RunStore,
    ) -> None:
        self.providers = providers
        self.wiki_store = wiki_store
        self.run_store = run_store
        self.compiler = NovelWorkflowCompiler()
        self.stages = StageRegistry(providers=providers, wiki_store=wiki_store)
        self.quality_engine = QualityEngine()

    async def run(
        self,
        workflow: WorkflowDefinition,
        run_id: str,
        inputs: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in stream_workflow(self, workflow, run_id=run_id, inputs=inputs):
            yield event

    async def _execute_with_variants(self, node: Any, state: NovelRunState, workflow: WorkflowDefinition) -> tuple[Any, list[dict[str, Any]]]:
        return await execute_with_variants(self, node, state, workflow)

    async def _run_chapter_text_node(
        self,
        node: Any,
        state: NovelRunState,
        workflow: WorkflowDefinition,
        run_id: str,
        index: int,
        total: int,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in run_chapter_text_node(self, node, state, workflow, run_id, index, total):
            yield event

    def _memory_query(self, node: Any, state: NovelRunState) -> str:
        return memory_query(node, state)

    async def _pause_if_requested(
        self,
        run_id: str,
        state: NovelRunState,
        *,
        node_id: str = "",
        chapter: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in pause_if_requested(self, run_id, state, node_id=node_id, chapter=chapter):
            yield event

    async def _wait_for_artifact_approval(
        self,
        run_id: str,
        state: NovelRunState,
        *,
        node_id: str,
        output_key: str,
        artifact: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in wait_for_artifact_approval(self, run_id, state, node_id=node_id, output_key=output_key, artifact=artifact):
            yield event

    async def _quality_loop_for_result(
        self,
        node: Any,
        result: Any,
        state: NovelRunState,
        workflow: WorkflowDefinition,
        run_id: str,
        *,
        chapter: str = "",
        context_packet: Any = None,
    ) -> AsyncIterator[dict[str, Any]]:
        async for event in quality_loop_for_result(self, node, result, state, workflow, run_id, chapter=chapter, context_packet=context_packet):
            yield event

    def _write_memory(self, node: Any, output_key: str, result: Any, state: NovelRunState) -> list[dict[str, Any]]:
        if result is None:
            return []
        ref = self.wiki_store.write_artifact(
            state.project_id,
            node_id=node.id,
            node_type=node.type,
            output_key=output_key,
            content=str(result),
            kinds=[str(kind) for kind in node.memory_policy.kinds],
        )
        return [ref]

    def _effective_variant_policy(self, node: Any, workflow: WorkflowDefinition) -> VariantPolicy:
        return effective_variant_policy(node, workflow)

    def _node_with_mode_policy(self, node: Any, workflow: WorkflowDefinition) -> Any:
        return node_with_mode_policy(node, workflow)

    def _variant_score(self, result: Any, index: int) -> float:
        return variant_score(result, index)

    def _chapter_count(self, node: Any, state: NovelRunState) -> int:
        return chapter_count(node, state)

    def _detail_outline_issue(self, node: Any, state: NovelRunState) -> str:
        return detail_outline_issue(node, state)

    def _chapter_content(self, result: Any, chapter_index: int, candidate_count: int, variant_index: int) -> str:
        return chapter_content(result, chapter_index, candidate_count, variant_index)

    def _chapter_deltas(self, content: str) -> list[str]:
        return chapter_deltas(content)

    def _update_worldbuilding_state(self, node: Any, result: Any, state: NovelRunState, chapter_name: str = "") -> None:
        update_worldbuilding_state(node, result, state, chapter_name=chapter_name)

    def _wiki_state(self, state: NovelRunState) -> dict[str, Any]:
        return wiki_state(self, state)

    def _continuity_state(self, state: NovelRunState) -> dict[str, Any]:
        return continuity_state(state)

    def _quality_check(self, node: Any, result: Any):
        return quality_event(node, result)

    def _character_graph(self, node_id: str):
        return character_graph(node_id)
