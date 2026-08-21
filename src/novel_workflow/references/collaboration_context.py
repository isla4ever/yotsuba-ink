from __future__ import annotations

from typing import Any

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationContextEnvelope,
    CollaborationContextPolicy,
    CollaborationContextPreviewRequest,
    CollaborationThread,
    CollaborationTurnContextReceipt,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationContextBudgetExceeded,
    CollaborationContextError,
    CollaborationSourceStale,
)
from novel_workflow.references.collaboration_context_material import (
    ContextMaterialBuilder,
    bounded_json,
    digest,
    now_iso,
    stage_label,
    token_estimate,
)
from novel_workflow.references.collaboration_knowledge_context import (
    add_knowledge_sources,
)
from novel_workflow.references.collaboration_source_context import (
    relevant_upstream,
    resolve_thread_source,
    scope_bindings,
    scoped_source_payload,
    source_snapshot,
    validate_selection,
)
from novel_workflow.references.collaboration_story_context import add_story_sources


class CollaborationContextCompiler:
    """Build one bounded, source-traceable context envelope for a collaboration turn."""

    _STAGE_UPSTREAM = {
        "spine": ("brief",),
        "cast": ("brief", "spine"),
        "volumes": ("brief", "spine", "cast"),
        "detail": ("brief", "spine", "cast", "volumes"),
        "text": ("brief", "spine", "cast", "volumes", "detail"),
    }

    def __init__(self, stores: Any, *, knowledge_base: Any | None = None) -> None:
        self.stores = stores
        self.knowledge_base = knowledge_base

    def compile_preview(
        self,
        thread: CollaborationThread,
        request: CollaborationContextPreviewRequest,
    ) -> CollaborationContextEnvelope:
        source_ref, source_signature, source_payload = source_snapshot(
            self.stores,
            thread,
        )
        if (
            source_ref != thread.scope.source_ref
            or source_signature != thread.scope.source_signature
        ):
            raise CollaborationSourceStale(
                "The collaboration thread is bound to an older Artifact version"
            )
        validate_selection(thread, request.selection, source_payload)
        turn_id = self.stores.collaboration.turn_id(
            thread.thread_id,
            request.client_turn_id,
        )
        policy = request.context_policy or self._policy(thread)
        builder = ContextMaterialBuilder()

        builder.add(
            category="history",
            source_ref=f"turn-input:{turn_id}",
            scope_ref=thread.scope.unit_ref,
            version="1",
            reason="本轮作者明确提出的协作目标",
            label="本轮要求",
            content=request.message.strip(),
            disposition="required",
            material_key="author_message",
        )
        scoped = scoped_source_payload(thread, source_payload)
        bindings = scope_bindings(self.stores, thread, scoped)
        builder.add(
            category="artifact",
            source_ref=source_ref,
            scope_ref=thread.scope.unit_ref,
            version=source_signature,
            reason="当前阶段、当前局部单元的冻结来源",
            label=thread.scope.label or stage_label(thread.stage_id),
            content=bounded_json(scoped, 8_000),
            disposition="required",
            material_key="current_artifact",
        )
        if request.selection is not None:
            builder.add(
                category="selection",
                source_ref=request.selection.source_ref,
                scope_ref=request.selection.field_path,
                version=request.selection.selected_text_hash,
                reason="作者在当前编辑器中显式引用的选区",
                label=request.selection.preview,
                content=request.selection.selected_text,
                disposition="required" if request.mode == "revise" else "optional",
                material_key="selection",
            )

        self._add_upstream_sources(thread, builder, bindings)
        add_story_sources(
            self.stores,
            thread,
            policy,
            builder,
            subject_ids=bindings["subject_ids"],
            chapter_number=bindings["chapter_number"],
        )
        add_knowledge_sources(
            self.knowledge_base,
            thread,
            request,
            policy,
            builder,
        )

        history = self.stores.collaboration.list_messages(
            thread.run_id,
            thread.thread_id,
            limit=policy.max_history_turns * 2,
        )
        for index, message in enumerate(history):
            builder.add_history(message, index)

        if policy.include_author_preferences and policy.author_preferences.strip():
            builder.add(
                category="author_preferences",
                source_ref=policy.policy_id,
                scope_ref="author",
                version=str(policy.version),
                reason="作者在协作设置中主动维护的偏好",
                label="作者偏好",
                content=policy.author_preferences.strip(),
                disposition="optional",
                material_key="author_preferences",
            )
        if policy.include_craft_mechanisms and policy.craft_mechanisms:
            builder.add(
                category="craft",
                source_ref=policy.policy_id,
                scope_ref="craft",
                version=str(policy.version),
                reason="作者为本次协作选择的写作机制",
                label="写作机制",
                content="\n".join(policy.craft_mechanisms),
                disposition="optional",
                material_key="craft_mechanisms",
            )

        used_chars = builder.used_chars
        if used_chars > policy.max_input_chars:
            raise CollaborationContextBudgetExceeded(
                used_chars=used_chars,
                budget_chars=policy.max_input_chars,
            )
        semantic = {
            "thread_id": thread.thread_id,
            "turn_id": turn_id,
            "mode": request.mode,
            "source_ref": source_ref,
            "sources": [item.model_dump(mode="json") for item in builder.sources],
            "history_message_refs": [item.message_id for item in history],
            "budget_chars": policy.max_input_chars,
            "used_chars": used_chars,
            "provider_profile_id": thread.provider_binding.provider_profile_id,
            "model": thread.provider_binding.model,
            "context_policy": policy.model_dump(mode="json"),
            "material": builder.material,
        }
        receipt_hash = digest(semantic)
        receipt = CollaborationTurnContextReceipt(
            receipt_id=f"collab-context-{receipt_hash}",
            thread_id=thread.thread_id,
            turn_id=turn_id,
            source_artifact_ref=source_ref,
            sources=builder.sources,
            history_message_refs=[item.message_id for item in history],
            budget_chars=policy.max_input_chars,
            used_chars=used_chars,
            token_estimate=token_estimate(used_chars),
            provider_profile_id=thread.provider_binding.provider_profile_id,
            model=thread.provider_binding.model,
            receipt_hash=receipt_hash,
            created_at=now_iso(),
        )
        return CollaborationContextEnvelope(receipt=receipt, material=builder.material)

    def source_snapshot(
        self,
        thread: CollaborationThread,
    ) -> tuple[str, str, dict[str, Any]]:
        return source_snapshot(self.stores, thread)

    def _add_upstream_sources(
        self,
        thread: CollaborationThread,
        builder: ContextMaterialBuilder,
        bindings: dict[str, Any],
    ) -> None:
        for stage_id in self._STAGE_UPSTREAM[thread.stage_id]:
            try:
                record = self.stores.artifacts.latest(
                    thread.run_id,
                    stage_id,
                    status="committed",
                )
            except FileNotFoundError:
                continue
            builder.add(
                category="characters" if stage_id == "cast" else "upstream",
                source_ref=record.artifact_id,
                scope_ref=stage_id,
                version=record.signature,
                reason=f"{stage_id} 是 {thread.stage_id} 当前局部决策的冻结上游约束",
                label=stage_label(stage_id),
                content=bounded_json(
                    relevant_upstream(
                        record.payload,
                        thread.scope.unit_ref,
                        subject_ids=bindings["subject_ids"],
                        turn_refs=bindings["turn_refs"],
                        volume_ref=bindings["volume_ref"],
                    ),
                    2_400,
                ),
                disposition="required" if stage_id in {"brief", "spine"} else "optional",
                material_key=f"upstream_{stage_id}",
            )

    @staticmethod
    def _policy(thread: CollaborationThread) -> CollaborationContextPolicy:
        return CollaborationContextPolicy(policy_id=thread.context_policy_id)


__all__ = [
    "CollaborationContextBudgetExceeded",
    "CollaborationContextCompiler",
    "CollaborationContextError",
    "CollaborationSourceStale",
    "resolve_thread_source",
]
