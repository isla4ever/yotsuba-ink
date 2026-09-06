"""Bounded, source-traceable context for Phase 32 author collaboration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from novel_workflow.knowledge import KnowledgeChunk, KnowledgeSearchRequest
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingService,
)
from novel_workflow.output_contracts.phase32_author_collaboration import (
    Phase32CollaborationContextEnvelope,
    Phase32CollaborationContextPreviewRequest,
    Phase32CollaborationContextReceipt,
    Phase32CollaborationThread,
    Phase32ContextSourceReceipt,
    Phase32SelectionAnchor,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationContextBudgetExceeded,
    CollaborationContextError,
    CollaborationFieldNotEditable,
    CollaborationSourceStale,
)
from novel_workflow.references.phase32_collaboration_field_policy import (
    phase32_collaboration_field_is_editable,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_collaboration_store import Phase32CollaborationStore
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.workflows.frozen_route_contract import canonical_digest


_UNIT_REF_FIELDS = (
    "subject_ref",
    "beat_ref",
    "scene_ref",
    "anchor_ref",
    "unit_ref",
    "part_ref",
    "volume_ref",
    "window_ref",
    "chapter_ref",
)


@dataclass(frozen=True, slots=True)
class Phase32CollaborationSource:
    artifact_ref: str
    effective_payload_digest: str
    source_signature: str
    unit_ref: str
    payload: dict[str, Any]
    scoped_payload: Any


class Phase32CollaborationContextCompiler:
    def __init__(
        self,
        repository: Phase32RunRepository,
        artifacts: Phase32ArtifactStore,
        editing: Phase32ArtifactEditingService,
        collaboration: Phase32CollaborationStore,
        *,
        knowledge_base: Any | None = None,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.editing = editing
        self.collaboration = collaboration
        self.knowledge_base = knowledge_base

    def resolve_source(
        self,
        run_id: str,
        stage_id: str,
        *,
        source_ref: str = "",
        unit_ref: str = "artifact",
    ) -> Phase32CollaborationSource:
        record = self.repository.read(run_id)
        stage = record.definition.stage(stage_id)
        selected_unit_ref = unit_ref.strip() or "artifact"
        current = self.editing.current(
            run_id,
            stage_id,
            unit_ref=(
                "" if selected_unit_ref == "artifact" or stage.unitization != "sequential_units"
                else selected_unit_ref
            ),
        )
        if source_ref and source_ref != current.artifact_ref:
            raise CollaborationSourceStale(
                "The requested source is not the current Phase 32 Artifact"
            )
        payload = dict(current.payload)
        effective_digest = current.payload_digest
        if current.pending_decision is not None:
            draft = self.editing.latest_draft(
                run_id,
                current.pending_decision.decision_id,
            )
            if draft is not None:
                payload = dict(draft.payload)
                effective_digest = draft.payload_digest
        if selected_unit_ref == "artifact" and current.unit_ref:
            selected_unit_ref = current.unit_ref
        scoped = (
            payload
            if selected_unit_ref in {"", "artifact"}
            else _find_unit(payload, selected_unit_ref)
        )
        if scoped is None:
            raise CollaborationContextError(
                f"Collaboration unit does not exist in the current Artifact: {selected_unit_ref}"
            )
        signature = canonical_digest(
            {
                "architecture_version": record.definition.architecture_version,
                "definition_digest": record.definition.definition_digest,
                "creation_route_id": record.definition.creation_route_id,
                "route_revision": record.definition.route_revision,
                "stage_id": stage.stage_id,
                "artifact_kind": stage.artifact_kind,
                "artifact_ref": current.artifact_ref,
                "effective_payload_digest": effective_digest,
                "unit_ref": selected_unit_ref or "artifact",
            }
        )
        return Phase32CollaborationSource(
            artifact_ref=current.artifact_ref,
            effective_payload_digest=effective_digest,
            source_signature=signature,
            unit_ref=selected_unit_ref or "artifact",
            payload=payload,
            scoped_payload=scoped,
        )

    def source_snapshot(
        self,
        thread: Phase32CollaborationThread,
    ) -> Phase32CollaborationSource:
        source = self.resolve_source(
            thread.run_id,
            thread.stage_id,
            source_ref=thread.scope.artifact_ref,
            unit_ref=thread.scope.unit_ref,
        )
        if (
            source.source_signature != thread.scope.source_signature
            or source.effective_payload_digest != thread.scope.effective_payload_digest
        ):
            raise CollaborationSourceStale(
                "The collaboration thread is bound to an older Artifact or author draft"
            )
        return source

    def compile_preview(
        self,
        thread: Phase32CollaborationThread,
        request: Phase32CollaborationContextPreviewRequest,
    ) -> Phase32CollaborationContextEnvelope:
        record = self.repository.read(thread.run_id)
        source = self.source_snapshot(thread)
        _validate_selection(thread, request.selection, source.payload)
        turn_id = self.collaboration.turn_id(thread.thread_id, request.client_turn_id)
        policy = request.context_policy
        if policy is None:
            from novel_workflow.output_contracts.author_collaboration import (
                CollaborationContextPolicy,
            )

            policy = CollaborationContextPolicy(policy_id=thread.context_policy_id)
        builder = _ContextBuilder(policy.max_input_chars)
        builder.add(
            category="history",
            source_ref=f"turn-input:{turn_id}",
            scope_ref=source.unit_ref,
            source_version="1",
            reason="本轮作者明确提出的协作目标",
            label="本轮要求",
            content=request.message.strip(),
            required=True,
            material_key="author_message",
        )
        builder.add(
            category="artifact",
            source_ref=source.artifact_ref,
            scope_ref=source.unit_ref,
            source_version=source.effective_payload_digest,
            reason="当前路线、阶段和局部单元的有效 Artifact 快照",
            label=thread.scope.label or thread.stage_id,
            content=_bounded_json(source.scoped_payload, 9_000),
            required=True,
            material_key="current_artifact",
        )
        if request.selection is not None:
            builder.add(
                category="selection",
                source_ref=request.selection.source_ref,
                scope_ref=request.selection.field_path,
                source_version=request.selection.selected_text_hash,
                reason="作者在当前编辑器中显式引用的选区",
                label=request.selection.preview,
                content=request.selection.selected_text,
                required=request.mode == "revise",
                material_key="selection",
            )
        self._add_upstream(record, thread, builder)
        history = self.collaboration.list_messages(
            thread.run_id,
            thread.thread_id,
            limit=max(1, policy.max_history_turns * 2),
        )
        for index, message in enumerate(history):
            builder.add(
                category="history",
                source_ref=message.message_id,
                scope_ref=thread.thread_id,
                source_version=canonical_digest(message.model_dump(mode="json")),
                reason="当前对话的近期多轮历史",
                label="作者" if message.role == "user" else "AI",
                content=message.content,
                required=False,
                material_key=f"history_{index:02d}",
            )
        if policy.include_author_preferences and policy.author_preferences.strip():
            builder.add(
                category="author_preferences",
                source_ref=policy.policy_id,
                scope_ref="author",
                source_version=str(policy.version),
                reason="作者主动维护的协作偏好",
                label="作者偏好",
                content=policy.author_preferences.strip(),
                required=False,
                material_key="author_preferences",
            )
        if policy.include_craft_mechanisms and policy.craft_mechanisms:
            builder.add(
                category="craft",
                source_ref=policy.policy_id,
                scope_ref=thread.stage_id,
                source_version=str(policy.version),
                reason="作者为本轮启用的创作机制",
                label="创作机制",
                content="\n".join(policy.craft_mechanisms),
                required=False,
                material_key="craft_mechanisms",
            )
        self._add_knowledge(thread, request, policy, builder)
        receipt_payload = {
            "thread_id": thread.thread_id,
            "turn_id": turn_id,
            "run_id": thread.run_id,
            "creation_route_id": thread.creation_route_id,
            "route_revision": thread.route_revision,
            "stage_id": thread.stage_id,
            "artifact_kind": thread.artifact_kind,
            "source_artifact_ref": source.artifact_ref,
            "source_signature": source.source_signature,
            "effective_payload_digest": source.effective_payload_digest,
            "sources": [item.model_dump(mode="json") for item in builder.sources],
            "history_message_refs": [item.message_id for item in history],
            "budget_chars": policy.max_input_chars,
            "used_chars": builder.used_chars,
            "token_estimate": _token_estimate(builder.used_chars),
            "provider_profile_id": thread.provider_execution.provider_profile_id,
            "model": thread.provider_execution.model_id,
        }
        receipt_hash = canonical_digest(receipt_payload)
        receipt = Phase32CollaborationContextReceipt(
            receipt_id=f"p32-context-{receipt_hash}",
            **receipt_payload,
            receipt_hash=receipt_hash,
            created_at=_now(),
        )
        return Phase32CollaborationContextEnvelope(
            receipt=receipt,
            material=builder.material,
        )

    def _add_upstream(self, record, thread, builder: "_ContextBuilder") -> None:
        for upstream_id in _ancestor_stage_ids(record.definition, thread.stage_id):
            artifact_ref = record.state.artifact_refs.get(upstream_id, "")
            if not artifact_ref:
                continue
            artifact = self.artifacts.read(thread.run_id, artifact_ref)
            if artifact.status != "committed":
                continue
            builder.add(
                category="upstream",
                source_ref=artifact.artifact_ref,
                scope_ref=upstream_id,
                source_version=artifact.payload_digest,
                reason="当前阶段声明依赖的已提交上游 Artifact",
                label=upstream_id,
                content=_bounded_json(artifact.payload, 4_000),
                required=False,
                material_key=f"upstream_{upstream_id}",
            )

    def _add_knowledge(self, thread, request, policy, builder: "_ContextBuilder") -> None:
        if not policy.include_knowledge or not policy.source_pack_refs:
            builder.omit(
                category="knowledge",
                source_ref=f"policy:{policy.policy_id}",
                scope_ref=thread.scope.unit_ref,
                source_version=str(policy.version),
                reason="本轮未选择知识库 Source Pack",
                label="本书知识库",
            )
            return
        if self.knowledge_base is None:
            raise CollaborationContextError("Selected knowledge Source Pack is unavailable")
        documents = {
            item.doc_id: item
            for item in self.knowledge_base.list_documents(thread.project_id)
        }
        refs = list(dict.fromkeys(policy.source_pack_refs))
        missing = [ref for ref in refs if ref not in documents]
        if missing:
            raise CollaborationContextError(
                f"Knowledge Source Pack is unavailable for this project: {missing}"
            )
        response = self.knowledge_base.search(
            KnowledgeSearchRequest(
                query=request.message.strip(),
                intent=f"{thread.creation_route_id}/{thread.stage_id}",
                project_id=thread.project_id,
                doc_ids=refs,
                top_k=min(8, max(3, len(refs) * 2)),
            )
        )
        for index, result in enumerate(response.results):
            chunk = KnowledgeChunk.model_validate(
                self.knowledge_base.chunks.read(result.chunk_id)
            )
            builder.add(
                category="knowledge",
                source_ref=chunk.chunk_id,
                scope_ref=chunk.doc_id,
                source_version=chunk.hash,
                reason="作者显式选择的 Source Pack 检索命中",
                label=chunk.title,
                content=chunk.text[:1_600],
                required=False,
                material_key=f"knowledge_{index:02d}",
            )


class _ContextBuilder:
    def __init__(self, budget_chars: int) -> None:
        self.budget_chars = budget_chars
        self.used_chars = 0
        self.sources: list[Phase32ContextSourceReceipt] = []
        self.material: dict[str, str] = {}

    def add(
        self,
        *,
        category: str,
        source_ref: str,
        scope_ref: str,
        source_version: str,
        reason: str,
        label: str,
        content: str,
        required: bool,
        material_key: str,
    ) -> None:
        value = content.strip()
        projected = self.used_chars + len(value)
        if projected > self.budget_chars:
            if required:
                raise CollaborationContextBudgetExceeded(
                    used_chars=projected,
                    budget_chars=self.budget_chars,
                )
            self.omit(
                category=category,
                source_ref=source_ref,
                scope_ref=scope_ref,
                source_version=source_version,
                reason=f"上下文预算不足，未注入：{reason}",
                label=label,
            )
            return
        self.used_chars = projected
        self.material[material_key] = value
        self.sources.append(
            Phase32ContextSourceReceipt(
                category=category,
                source_ref=source_ref,
                scope_ref=scope_ref,
                source_version=source_version,
                reason=reason,
                char_count=len(value),
                token_estimate=_token_estimate(len(value)),
                disposition="required" if required else "optional",
                label=label,
            )
        )

    def omit(self, **payload: Any) -> None:
        self.sources.append(
            Phase32ContextSourceReceipt(
                **payload,
                char_count=0,
                token_estimate=0,
                disposition="omitted",
            )
        )


def _validate_selection(
    thread: Phase32CollaborationThread,
    selection: Phase32SelectionAnchor | None,
    payload: dict[str, Any],
) -> None:
    if selection is None:
        return
    if (
        selection.stage_id != thread.stage_id
        or selection.source_ref != thread.scope.artifact_ref
        or selection.unit_ref != thread.scope.unit_ref
    ):
        raise CollaborationSourceStale("Selection does not belong to this collaboration scope")
    if not phase32_collaboration_field_is_editable(
        thread.stage_id, selection.field_path
    ):
        raise CollaborationFieldNotEditable(
            f"{selection.field_path} is not an editable collaboration field"
        )
    current = _resolve_path(payload, selection.field_path)
    if not isinstance(current, str):
        raise CollaborationFieldNotEditable("Selection target is not a text field")
    selected = current[selection.selection_start : selection.selection_end]
    if (
        _sha256(current) != selection.field_hash
        or selected != selection.selected_text
        or _sha256(selected) != selection.selected_text_hash
    ):
        raise CollaborationSourceStale("Selection no longer matches the effective Artifact")


def _find_unit(value: Any, unit_ref: str) -> Any | None:
    if isinstance(value, dict):
        if any(str(value.get(field) or "") == unit_ref for field in _UNIT_REF_FIELDS):
            return value
        for child in value.values():
            found = _find_unit(child, unit_ref)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_unit(child, unit_ref)
            if found is not None:
                return found
    return None


def _resolve_path(value: Any, field_path: str) -> Any:
    current = value
    for part in field_path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _ancestor_stage_ids(definition, stage_id: str) -> tuple[str, ...]:
    by_id = {stage.stage_id: stage for stage in definition.route_contract.route_manifest.stages}
    seen: set[str] = set()

    def visit(current: str) -> None:
        for upstream in by_id[current].upstream_stage_ids:
            if upstream not in seen:
                visit(upstream)
                seen.add(upstream)

    visit(stage_id)
    return tuple(stage.stage_id for stage in definition.route_contract.route_manifest.stages if stage.stage_id in seen)


def _bounded_json(value: Any, limit: int) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rendered if len(rendered) <= limit else rendered[: limit - 1] + "…"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _token_estimate(char_count: int) -> int:
    return (char_count + 2) // 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32CollaborationContextCompiler",
    "Phase32CollaborationSource",
]
