"""Phase 32-only lifecycle for source-bound author collaboration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from novel_workflow.output_contracts.phase32_author_collaboration import (
    CreatePhase32CollaborationThreadRequest,
    CreatePhase32CollaborationTurnRequest,
    Phase32ArtifactPatchCandidate,
    Phase32CollaborationContextPreviewRequest,
    Phase32CollaborationMessage,
    Phase32CollaborationScope,
    Phase32CollaborationThread,
    Phase32CollaborationTurn,
    UpdatePhase32CollaborationThreadRequest,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderExecutionSnapshot,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationFieldNotEditable,
    CollaborationSourceStale,
)
from novel_workflow.references.phase32_collaboration_context import (
    Phase32CollaborationContextCompiler,
)
from novel_workflow.references.phase32_collaboration_field_policy import (
    phase32_collaboration_field_is_editable,
)
from novel_workflow.runtime.graph.phase32_collaboration_execution import (
    Phase32CollaborationExecutor,
)
from novel_workflow.storage.phase32_collaboration_context_store import (
    Phase32CollaborationContextStore,
)
from novel_workflow.storage.phase32_collaboration_store import Phase32CollaborationStore
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository


class Phase32AuthorCollaborationError(ValueError):
    code = "author_collaboration_invalid"


class Phase32AuthorCollaborationUnavailable(Phase32AuthorCollaborationError):
    code = "author_collaboration_unavailable"


class Phase32ContextReconfirmationRequired(Phase32AuthorCollaborationError):
    code = "context_reconfirmation_required"


class Phase32PatchWritebackUnavailable(Phase32AuthorCollaborationError):
    code = "patch_writeback_unavailable"


class Phase32CollaborationThreadBusy(Phase32AuthorCollaborationError):
    code = "collaboration_thread_busy"


ExecutionResolver = Callable[
    [Phase32ProviderExecutionSnapshot],
    Phase32ProviderExecutionSnapshot,
]


class Phase32AuthorCollaborationService:
    def __init__(
        self,
        repository: Phase32RunRepository,
        collaboration: Phase32CollaborationStore,
        contexts: Phase32CollaborationContextStore,
        context_compiler: Phase32CollaborationContextCompiler,
        executor: Phase32CollaborationExecutor,
        *,
        execution_resolver: ExecutionResolver | None = None,
    ) -> None:
        self.repository = repository
        self.collaboration = collaboration
        self.contexts = contexts
        self.context_compiler = context_compiler
        self.executor = executor
        self.execution_resolver = execution_resolver or (lambda execution: execution)

    def list_threads(self, run_id: str) -> list[Phase32CollaborationThread]:
        definition = self.repository.definition(run_id)
        threads = self.collaboration.list_threads(run_id)
        for thread in threads:
            _validate_thread_definition(thread, definition)
        return threads

    def create_thread(
        self,
        run_id: str,
        request: CreatePhase32CollaborationThreadRequest,
    ) -> Phase32CollaborationThread:
        definition = self.repository.definition(run_id)
        _require_author_collaboration_available(definition)
        stage = _collaboration_stage(definition, request.stage_id)
        if request.field_path and not phase32_collaboration_field_is_editable(
            stage.stage_id, request.field_path
        ):
            raise CollaborationFieldNotEditable(
                f"{request.field_path} is not an editable {stage.stage_id} collaboration field"
            )
        source = self.context_compiler.resolve_source(
            run_id,
            stage.stage_id,
            source_ref=request.source_ref,
            unit_ref=request.unit_ref,
        )
        stage_binding = _stage_provider_binding(definition, stage.stage_id)
        thread_id = self.collaboration.new_thread_id()
        now = _now()
        thread = Phase32CollaborationThread(
            thread_id=thread_id,
            run_id=run_id,
            project_id=definition.project_id,
            creation_route_id=definition.creation_route_id,
            route_revision=definition.route_revision,
            stage_id=stage.stage_id,
            artifact_kind=stage.artifact_kind,
            scope=Phase32CollaborationScope(
                artifact_ref=source.artifact_ref,
                effective_payload_digest=source.effective_payload_digest,
                source_signature=source.source_signature,
                unit_ref=source.unit_ref,
                field_path=request.field_path,
                label=request.label,
            ),
            title=request.title.strip()
            or _default_thread_title(stage.label, request.label),
            provider_execution=self.execution_resolver(stage_binding.execution),
            context_policy_id=request.context_policy.policy_id,
            created_at=now,
            updated_at=now,
        )
        return self.collaboration.create_thread(thread)

    def read_thread(self, run_id: str, thread_id: str) -> dict[str, Any]:
        definition = self.repository.definition(run_id)
        thread = self.collaboration.read_thread(run_id, thread_id)
        _validate_thread_definition(thread, definition)
        return {
            "thread": thread,
            "turns": self.collaboration.list_turns(run_id, thread_id),
            "messages": self.collaboration.list_messages(run_id, thread_id),
            "patches": self.collaboration.list_patches(run_id, thread_id=thread_id),
        }

    def update_thread(
        self,
        run_id: str,
        thread_id: str,
        request: UpdatePhase32CollaborationThreadRequest,
    ) -> Phase32CollaborationThread:
        self.repository.definition(run_id)
        changes = request.model_dump(exclude_none=True)
        if not changes:
            return self.collaboration.read_thread(run_id, thread_id)
        if changes.get("status") == "archived":
            self._assert_thread_idle(run_id, thread_id)
        return self.collaboration.update_thread(run_id, thread_id, **changes)

    def delete_thread(self, run_id: str, thread_id: str) -> Phase32CollaborationThread:
        self.repository.definition(run_id)
        thread = self.collaboration.read_thread(run_id, thread_id)
        self._assert_thread_idle(run_id, thread_id)
        if thread.has_unapplied_patch:
            raise Phase32AuthorCollaborationError(
                "Resolve the pending Patch proposal before deleting this thread"
            )
        return self.collaboration.update_thread(run_id, thread_id, status="deleted")

    def preview_context(
        self,
        run_id: str,
        thread_id: str,
        request: Phase32CollaborationContextPreviewRequest,
    ):
        self.repository.definition(run_id)
        thread = self._active_thread(run_id, thread_id)
        envelope = self.context_compiler.compile_preview(thread, request)
        return self.contexts.write(run_id, envelope).receipt

    def create_turn(
        self,
        run_id: str,
        thread_id: str,
        request: CreatePhase32CollaborationTurnRequest,
    ) -> Phase32CollaborationTurn:
        self.repository.definition(run_id)
        thread = self._active_thread(run_id, thread_id)
        replay = self.collaboration.find_turn_by_client_id(
            run_id, thread_id, request.client_turn_id
        )
        if replay is not None:
            original = self.collaboration.read_message(
                run_id, thread_id, replay.user_message_ref
            )
            if (
                replay.mode != request.mode
                or replay.context_preview_signature != request.preview_signature
                or replay.selection_anchor != request.selection
                or original.content != request.message.strip()
            ):
                raise ValueError("turn_replay_conflict")
            return replay
        if request.mode == "revise" and request.selection is None:
            raise Phase32AuthorCollaborationError(
                "Revise mode requires an exact editable selection"
            )
        preview_request = Phase32CollaborationContextPreviewRequest(
            client_turn_id=request.client_turn_id,
            mode=request.mode,
            message=request.message,
            context_policy=request.context_policy,
            selection=request.selection,
        )
        envelope = self.context_compiler.compile_preview(thread, preview_request)
        if envelope.receipt.receipt_hash != request.preview_signature:
            raise Phase32ContextReconfirmationRequired(
                "Context sources changed; review and confirm the new receipt"
            )
        self.contexts.write(run_id, envelope)
        turn_id = envelope.receipt.turn_id
        message = self.collaboration.write_message(
            run_id,
            Phase32CollaborationMessage(
                message_id=f"p32-message-user-{turn_id}",
                thread_id=thread_id,
                turn_id=turn_id,
                role="user",
                mode=request.mode,
                content=request.message.strip(),
                context_receipt_ref=envelope.receipt.receipt_id,
                source_refs=tuple(item.source_ref for item in envelope.receipt.sources),
                created_at=_now(),
            ),
        )
        turn = self.collaboration.create_turn(
            Phase32CollaborationTurn(
                turn_id=turn_id,
                client_turn_id=request.client_turn_id,
                thread_id=thread_id,
                run_id=run_id,
                mode=request.mode,
                status="queued",
                user_message_ref=message.message_id,
                context_receipt_ref=envelope.receipt.receipt_id,
                context_preview_signature=envelope.receipt.receipt_hash,
                selection_anchor=request.selection,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        self.collaboration.append_event(
            run_id,
            thread_id,
            "context.frozen",
            turn_id=turn_id,
            payload={
                "receipt_id": envelope.receipt.receipt_id,
                "token_estimate": envelope.receipt.token_estimate,
            },
        )
        return turn

    async def execute_turn(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> Phase32CollaborationTurn:
        definition = self.repository.definition(run_id)
        _require_author_collaboration_available(definition)
        return await self.executor.execute(run_id, thread_id, turn_id)

    def cancel_queued_turn(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> Phase32CollaborationTurn:
        self.repository.definition(run_id)
        turn = self.collaboration.read_turn(run_id, thread_id, turn_id)
        if turn.status in {"completed", "cancelled", "failed", "contract_rejected"}:
            return turn
        if turn.status != "queued":
            raise Phase32AuthorCollaborationError(
                "A Provider request already in flight cannot be cancelled by this process"
            )
        cancelled = self.collaboration.transition_turn(
            run_id,
            thread_id,
            turn_id,
            "cancelled",
            error={"code": "cancelled", "message": "Cancelled before dispatch"},
        )
        self.collaboration.append_event(
            run_id,
            thread_id,
            "turn.cancelled",
            turn_id=turn_id,
            payload={"code": "cancelled"},
        )
        return cancelled

    def reject_patch(
        self,
        run_id: str,
        patch_id: str,
    ) -> Phase32ArtifactPatchCandidate:
        self.repository.definition(run_id)
        patch = self.collaboration.transition_patch(run_id, patch_id, "rejected")
        self.collaboration.append_event(
            run_id,
            patch.thread_id,
            "patch.rejected",
            turn_id=patch.turn_id,
            payload={"patch_id": patch.patch_id},
        )
        return patch

    def accept_patch(
        self,
        run_id: str,
        patch_id: str,
    ) -> Phase32ArtifactPatchCandidate:
        self.repository.definition(run_id)
        patch = self.collaboration.read_patch(run_id, patch_id)
        thread = self.collaboration.read_thread(run_id, patch.thread_id)
        try:
            self.context_compiler.source_snapshot(thread)
        except CollaborationSourceStale:
            stale = self.collaboration.transition_patch(run_id, patch_id, "stale")
            self.collaboration.append_event(
                run_id,
                patch.thread_id,
                "patch.stale",
                turn_id=patch.turn_id,
                payload={"patch_id": patch.patch_id},
            )
            return stale
        raise Phase32PatchWritebackUnavailable(
            "Patch proposals must enter a Phase 32 draft, amendment or branch; direct writeback is not available yet"
        )

    def _active_thread(
        self,
        run_id: str,
        thread_id: str,
    ) -> Phase32CollaborationThread:
        thread = self.collaboration.read_thread(run_id, thread_id)
        if thread.status != "active":
            raise Phase32AuthorCollaborationUnavailable(
                "Collaboration thread is read-only"
            )
        return thread

    def _assert_thread_idle(self, run_id: str, thread_id: str) -> None:
        if any(
            turn.status in {"queued", "streaming"}
            for turn in self.collaboration.list_turns(run_id, thread_id)
        ):
            raise Phase32CollaborationThreadBusy(
                "Stop the active turn before archiving or deleting its thread"
            )


def _collaboration_stage(definition, stage_id: str):
    try:
        stage = definition.stage(stage_id)
    except ValueError as exc:
        raise Phase32AuthorCollaborationUnavailable(str(exc)) from exc
    if not stage.collaboration_enabled:
        raise Phase32AuthorCollaborationUnavailable(
            f"Author collaboration is disabled for stage {stage_id}"
        )
    return stage


def _require_author_collaboration_available(definition) -> None:
    if definition.scale_profile.payload.get("profile_kind") == "continuity_acceptance":
        raise Phase32AuthorCollaborationUnavailable(
            "Author collaboration is unavailable for continuity acceptance Runs"
        )


def _stage_provider_binding(definition, stage_id: str):
    entry = next(
        (item for item in definition.provider_bindings_by_stage if item.stage_id == stage_id),
        None,
    )
    if entry is None:
        raise Phase32AuthorCollaborationUnavailable(
            f"Stage {stage_id} has no frozen text Provider binding"
        )
    return Phase32StageProviderBindingSnapshot.model_validate(entry.binding.payload)


def _validate_thread_definition(thread, definition) -> None:
    stage = _collaboration_stage(definition, thread.stage_id)
    if (
        thread.run_id != definition.run_id
        or thread.project_id != definition.project_id
        or thread.creation_route_id != definition.creation_route_id
        or thread.route_revision != definition.route_revision
        or thread.artifact_kind != stage.artifact_kind
    ):
        raise Phase32AuthorCollaborationUnavailable(
            "Collaboration thread does not belong to the current Phase 32 Run definition"
        )


def _default_thread_title(stage_label: str, label: str) -> str:
    return f"{stage_label} · {label.strip() or '新对话'}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32AuthorCollaborationError",
    "Phase32AuthorCollaborationService",
    "Phase32AuthorCollaborationUnavailable",
    "Phase32CollaborationThreadBusy",
    "Phase32ContextReconfirmationRequired",
    "Phase32PatchWritebackUnavailable",
]
