from __future__ import annotations

from typing import Any

from novel_workflow.knowledge import KnowledgeSearchRequest
from novel_workflow.knowledge.schemas import KnowledgeChunk
from novel_workflow.output_contracts.author_collaboration import (
    CollaborationContextPolicy,
    CollaborationContextPreviewRequest,
    CollaborationThread,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationContextError,
)
from novel_workflow.references.collaboration_context_material import (
    ContextMaterialBuilder,
    bounded_text,
    digest,
    stage_label,
)


def add_knowledge_sources(
    knowledge_base: Any | None,
    thread: CollaborationThread,
    request: CollaborationContextPreviewRequest,
    policy: CollaborationContextPolicy,
    builder: ContextMaterialBuilder,
) -> None:
    if not policy.include_knowledge:
        builder.omit(
            category="knowledge",
            source_ref=f"policy:{policy.policy_id}",
            scope_ref=thread.scope.unit_ref,
            version=str(policy.version),
            reason="本轮未启用本书知识库 Source Pack",
            label="本书知识库",
        )
        return
    if not policy.source_pack_refs:
        builder.omit(
            category="knowledge",
            source_ref=f"policy:{policy.policy_id}",
            scope_ref=thread.scope.unit_ref,
            version=str(policy.version),
            reason="已启用知识库，但本轮尚未选择任何 Source Pack",
            label="本书知识库",
        )
        return
    if knowledge_base is None:
        raise CollaborationContextError(
            "Knowledge Source Pack was selected but the knowledge store is unavailable"
        )
    documents = {
        item.doc_id: item
        for item in knowledge_base.list_documents(thread.project_id)
    }
    requested_refs = list(dict.fromkeys(policy.source_pack_refs))
    missing = [item for item in requested_refs if item not in documents]
    if missing:
        raise CollaborationContextError(
            f"Knowledge Source Pack is unavailable for this project: {missing}"
        )
    response = knowledge_base.search(
        KnowledgeSearchRequest(
            query=request.message.strip(),
            intent=f"{stage_label(thread.stage_id)} · {thread.scope.label}",
            project_id=thread.project_id,
            doc_ids=requested_refs,
            top_k=min(8, max(3, len(requested_refs) * 2)),
        )
    )
    for index, result in enumerate(response.results):
        chunk = KnowledgeChunk.model_validate(knowledge_base.chunks.read(result.chunk_id))
        builder.add(
            category="knowledge",
            source_ref=chunk.chunk_id,
            scope_ref=chunk.doc_id,
            version=chunk.hash,
            reason="作者为本轮显式选择的 Source Pack 检索命中",
            label=f"{chunk.title}{f' · {chunk.section}' if chunk.section else ''}",
            content=bounded_text(chunk.text, 1_600),
            disposition="optional",
            material_key=f"knowledge_{index:02d}",
        )
    if not response.results:
        selected = [documents[item].model_dump(mode="json") for item in requested_refs]
        builder.omit(
            category="knowledge",
            source_ref="knowledge-search:no-match",
            scope_ref=thread.scope.unit_ref,
            version=digest(selected),
            reason="已选 Source Pack 与本轮问题没有达到检索阈值的片段",
            label="本书知识库",
        )


__all__ = ["add_knowledge_sources"]
