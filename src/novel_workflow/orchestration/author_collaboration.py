from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from novel_workflow.orchestration.stage_artifact_editing import (
    StageArtifactDraftConflict,
    save_stage_artifact_draft,
)
from novel_workflow.output_contracts.author_collaboration import (
    ArtifactPatchCandidate,
    CollaborationContextPreviewRequest,
    CollaborationMessage,
    CollaborationScope,
    CollaborationThread,
    CollaborationTurn,
    CreateCollaborationThreadRequest,
    CreateCollaborationTurnRequest,
    UpdateCollaborationThreadRequest,
)
from novel_workflow.references.collaboration_context import (
    CollaborationContextCompiler,
    CollaborationSourceStale,
    resolve_thread_source,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationFieldNotEditable,
)
from novel_workflow.references.collaboration_field_policy import (
    collaboration_field_is_editable,
)
from novel_workflow.storage.narrative_run_repository import ProviderBinding


class AuthorCollaborationError(ValueError):
    code = "author_collaboration_invalid"


class AuthorCollaborationUnavailable(AuthorCollaborationError):
    code = "author_collaboration_unavailable"


class ContextReconfirmationRequired(AuthorCollaborationError):
    code = "context_reconfirmation_required"


class PatchWritebackUnavailable(AuthorCollaborationError):
    code = "patch_writeback_unavailable"


class CollaborationThreadBusy(AuthorCollaborationError):
    code = "collaboration_thread_busy"


class AuthorCollaborationService:
    def __init__(
        self,
        stores: Any,
        *,
        binding_resolver: Callable[[ProviderBinding], ProviderBinding] | None = None,
        knowledge_base: Any | None = None,
    ) -> None:
        self.stores = stores
        self.context = CollaborationContextCompiler(
            stores,
            knowledge_base=knowledge_base,
        )
        self.binding_resolver = binding_resolver or (lambda binding: binding)

    def list_threads(self, run_id: str) -> list[CollaborationThread]:
        self._definition(run_id)
        return self.stores.collaboration.list_threads(run_id)

    def create_thread(
        self,
        run_id: str,
        request: CreateCollaborationThreadRequest,
    ) -> CollaborationThread:
        definition = self._definition(run_id)
        if request.field_path and not collaboration_field_is_editable(
            request.stage_id,
            request.field_path,
        ):
            raise CollaborationFieldNotEditable(
                f"{request.field_path} is not an editable {request.stage_id} collaboration field"
            )
        source_ref, source_signature = resolve_thread_source(
            self.stores,
            run_id=run_id,
            stage_id=request.stage_id,
            source_ref=request.source_ref,
            unit_ref=request.unit_ref,
        )
        thread_id = self.stores.collaboration.new_thread_id()
        provider_binding = self.binding_resolver(
            definition.provider_bindings[request.stage_id]
        )
        thread = CollaborationThread(
            thread_id=thread_id,
            run_id=run_id,
            project_id=definition.project_id,
            stage_id=request.stage_id,
            scope=CollaborationScope(
                source_ref=source_ref,
                source_signature=source_signature,
                unit_ref=request.unit_ref,
                field_path=request.field_path,
                label=request.label,
            ),
            title=request.title.strip() or _default_thread_title(request.stage_id, request.label),
            provider_binding=provider_binding,
            context_policy_id=request.context_policy.policy_id,
            created_at=_now(),
            updated_at=_now(),
        )
        saved = self.stores.collaboration.create_thread(thread)
        self.stores.events.append(
            run_id,
            event_id=f"{thread_id}:created",
            type="collaboration.thread_created",
            stage_id=request.stage_id,
            node_id="author_collaboration.create_thread",
            status="active",
            payload={"thread_id": thread_id, "scope": saved.scope.model_dump(mode="json")},
        )
        return saved

    def read_thread(self, run_id: str, thread_id: str) -> dict[str, Any]:
        self._definition(run_id)
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        return {
            "thread": thread,
            "turns": self.stores.collaboration.list_turns(run_id, thread_id),
            "messages": self.stores.collaboration.list_messages(run_id, thread_id),
            "patches": self.stores.collaboration.list_patches(
                run_id,
                thread_id=thread_id,
            ),
        }

    def update_thread(
        self,
        run_id: str,
        thread_id: str,
        request: UpdateCollaborationThreadRequest,
    ) -> CollaborationThread:
        self._definition(run_id)
        changes = request.model_dump(exclude_none=True)
        if not changes:
            return self.stores.collaboration.read_thread(run_id, thread_id)
        if changes.get("status") in {"archived", "deleted"}:
            self._assert_thread_idle(run_id, thread_id)
        return self.stores.collaboration.update_thread(run_id, thread_id, **changes)

    def delete_thread(self, run_id: str, thread_id: str) -> CollaborationThread:
        self._definition(run_id)
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        self._assert_thread_idle(run_id, thread_id)
        if thread.has_unapplied_patch:
            raise AuthorCollaborationError(
                "A thread with an unapplied patch must be resolved before deletion"
            )
        return self.stores.collaboration.update_thread(
            run_id,
            thread_id,
            status="deleted",
        )

    def preview_context(
        self,
        run_id: str,
        thread_id: str,
        request: CollaborationContextPreviewRequest,
    ):
        self._definition(run_id)
        thread = self._active_thread(run_id, thread_id)
        envelope = self.context.compile_preview(thread, request)
        saved = self.stores.collaboration_contexts.write(run_id, envelope)
        return saved.receipt

    def create_turn(
        self,
        run_id: str,
        thread_id: str,
        request: CreateCollaborationTurnRequest,
    ) -> CollaborationTurn:
        self._definition(run_id)
        thread = self._active_thread(run_id, thread_id)
        replay = self.stores.collaboration.find_turn_by_client_id(
            run_id,
            thread_id,
            request.client_turn_id,
        )
        if replay is not None:
            original = self.stores.collaboration.read_message(
                run_id,
                thread_id,
                replay.user_message_ref,
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
            raise AuthorCollaborationError("Revise mode requires an exact source selection")
        preview_request = CollaborationContextPreviewRequest(
            client_turn_id=request.client_turn_id,
            mode=request.mode,
            message=request.message,
            context_policy=request.context_policy,
            selection=request.selection,
        )
        envelope = self.context.compile_preview(thread, preview_request)
        if envelope.receipt.receipt_hash != request.preview_signature:
            raise ContextReconfirmationRequired(
                "Context sources changed; review and confirm the new receipt"
            )
        self.stores.collaboration_contexts.write(run_id, envelope)
        turn_id = envelope.receipt.turn_id
        user_message = CollaborationMessage(
            message_id=f"message-user-{turn_id}",
            thread_id=thread_id,
            turn_id=turn_id,
            role="user",
            mode=request.mode,
            content=request.message.strip(),
            context_receipt_ref=envelope.receipt.receipt_id,
            source_refs=[item.source_ref for item in envelope.receipt.sources],
            created_at=_now(),
        )
        self.stores.collaboration.write_message(run_id, user_message)
        turn = self.stores.collaboration.create_turn(
            CollaborationTurn(
                turn_id=turn_id,
                client_turn_id=request.client_turn_id,
                thread_id=thread_id,
                run_id=run_id,
                mode=request.mode,
                status="queued",
                user_message_ref=user_message.message_id,
                context_receipt_ref=envelope.receipt.receipt_id,
                context_preview_signature=envelope.receipt.receipt_hash,
                selection_anchor=request.selection,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        self.stores.collaboration.append_event(
            run_id,
            thread_id,
            "context.frozen",
            turn_id=turn_id,
            payload={
                "receipt_id": envelope.receipt.receipt_id,
                "token_estimate": envelope.receipt.token_estimate,
            },
        )
        self.stores.events.append(
            run_id,
            event_id=f"{turn_id}:started",
            type="collaboration.turn_started",
            stage_id=thread.stage_id,
            node_id="author_collaboration.create_turn",
            status="queued",
            payload={"thread_id": thread_id, "turn_id": turn_id, "mode": turn.mode},
        )
        self.stores.events.append(
            run_id,
            event_id=f"{turn_id}:context-frozen",
            type="collaboration.context_frozen",
            stage_id=thread.stage_id,
            node_id="author_collaboration.context",
            status="frozen",
            payload_ref=envelope.receipt.receipt_id,
            payload={"thread_id": thread_id, "turn_id": turn_id},
        )
        return turn

    def cancel_queued_turn(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> CollaborationTurn:
        self._definition(run_id)
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        turn = self.stores.collaboration.read_turn(run_id, thread_id, turn_id)
        if turn.status in {"completed", "cancelled", "failed", "contract_rejected"}:
            return turn
        if turn.status != "queued":
            raise AuthorCollaborationError("A streaming turn must be cancelled by its execution task")
        cancelled = self.stores.collaboration.transition_turn(
            run_id,
            thread_id,
            turn_id,
            "cancelled",
            error={"code": "cancelled", "message": "Cancelled before dispatch"},
        )
        self.stores.collaboration.append_event(
            run_id,
            thread_id,
            "turn.cancelled",
            turn_id=turn_id,
            payload={"code": "cancelled"},
        )
        self.stores.events.append(
            run_id,
            event_id=f"{turn_id}:cancelled",
            type="collaboration.turn_cancelled",
            stage_id=thread.stage_id,
            node_id="author_collaboration",
            status="cancelled",
            payload={"thread_id": thread_id, "turn_id": turn_id},
        )
        return cancelled

    def reject_patch(self, run_id: str, patch_id: str) -> ArtifactPatchCandidate:
        self._definition(run_id)
        patch = self.stores.collaboration.transition_patch(run_id, patch_id, "rejected")
        self._patch_event(patch, "patch.rejected", "collaboration.patch_rejected")
        return patch

    def accept_patch(self, run_id: str, patch_id: str) -> ArtifactPatchCandidate:
        self._definition(run_id)
        patch = self.stores.collaboration.read_patch(run_id, patch_id)
        if patch.status == "accepted":
            return patch
        if patch.status != "proposed":
            raise AuthorCollaborationError("Patch candidate is already resolved")
        thread = self.stores.collaboration.read_thread(run_id, patch.thread_id)
        turn = self.stores.collaboration.read_turn(run_id, patch.thread_id, patch.turn_id)
        try:
            source_ref, signature, payload = self.context.source_snapshot(thread)
        except CollaborationSourceStale:
            stale = self.stores.collaboration.transition_patch(run_id, patch_id, "stale")
            self._patch_event(stale, "patch.stale", "collaboration.patch_stale")
            return stale
        if source_ref != patch.source_ref or signature != patch.source_signature:
            stale = self.stores.collaboration.transition_patch(run_id, patch_id, "stale")
            self._patch_event(stale, "patch.stale", "collaboration.patch_stale")
            return stale
        selection = turn.selection_anchor
        if selection is None or len(patch.operations) != 1:
            raise AuthorCollaborationError("Patch is missing its exact source selection")
        edited = copy.deepcopy(payload)
        operation = patch.operations[0]
        if not collaboration_field_is_editable(patch.stage_id, operation.field_path):
            raise CollaborationFieldNotEditable(
                f"{operation.field_path} is not an editable {patch.stage_id} collaboration field"
            )
        current = _resolve_path(edited, operation.field_path)
        if not isinstance(current, str):
            raise AuthorCollaborationError("Patch target is not a text field")
        selected = current[selection.selection_start : selection.selection_end]
        if (
            _digest(current) != selection.field_hash
            or _digest(selected) != operation.before_hash
            or selected != selection.selected_text
        ):
            stale = self.stores.collaboration.transition_patch(run_id, patch_id, "stale")
            self._patch_event(stale, "patch.stale", "collaboration.patch_stale")
            return stale
        replacement = (
            current[: selection.selection_start]
            + operation.replacement
            + current[selection.selection_end :]
        )
        _assign_path(edited, operation.field_path, replacement)

        pending = next(
            (
                item
                for item in self.stores.runs.read(run_id).pending_decisions
                if str(item.get("artifact_ref") or "") == patch.source_ref
                and str(item.get("node_id") or "").partition(".")[0] == patch.stage_id
            ),
            None,
        )
        if pending is None:
            raise PatchWritebackUnavailable(
                "Committed planning and accepted prose require the Phase 29 amendment or chapter branch path"
            )
        try:
            draft = save_stage_artifact_draft(
                self.stores,
                run_id=run_id,
                decision_id=str(pending["decision_id"]),
                domain_revision=int(pending["domain_revision"]),
                source_artifact_id=patch.source_ref,
                artifact=edited,
            )
        except StageArtifactDraftConflict as exc:
            stale = self.stores.collaboration.transition_patch(run_id, patch_id, "stale")
            self._patch_event(stale, "patch.stale", "collaboration.patch_stale")
            return stale
        accepted = self.stores.collaboration.transition_patch(
            run_id,
            patch_id,
            "accepted",
            writeback_ref=draft.draft_id,
        )
        self._patch_event(accepted, "patch.accepted", "collaboration.patch_accepted")
        return accepted

    def _patch_event(
        self,
        patch: ArtifactPatchCandidate,
        stream_type: str,
        run_type: str,
    ) -> None:
        self.stores.collaboration.append_event(
            patch.run_id,
            patch.thread_id,
            stream_type,
            turn_id=patch.turn_id,
            payload={"patch_id": patch.patch_id, "status": patch.status},
        )
        self.stores.events.append(
            patch.run_id,
            event_id=f"{patch.patch_id}:{patch.status}",
            type=run_type,
            stage_id=patch.stage_id,
            node_id="author_collaboration.patch_decision",
            status=patch.status,
            payload={
                "thread_id": patch.thread_id,
                "turn_id": patch.turn_id,
                "patch_id": patch.patch_id,
                "writeback_ref": patch.writeback_ref,
            },
        )

    def _definition(self, run_id: str):
        definition = self.stores.runs.executable_definition(run_id)
        if definition.quality_mode != "deep":
            raise AuthorCollaborationUnavailable(
                "Author collaboration is available only in deep mode"
            )
        return definition

    def _active_thread(self, run_id: str, thread_id: str) -> CollaborationThread:
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        if thread.status != "active":
            raise AuthorCollaborationUnavailable("Collaboration thread is read-only")
        return thread

    def _assert_thread_idle(self, run_id: str, thread_id: str) -> None:
        if any(
            turn.status in {"queued", "streaming"}
            for turn in self.stores.collaboration.list_turns(run_id, thread_id)
        ):
            raise CollaborationThreadBusy(
                "Stop the active collaboration turn before archiving or deleting its thread"
            )


def _resolve_path(value: Any, field_path: str) -> Any:
    current = value
    for part in field_path.split("."):
        if not part:
            continue
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _assign_path(value: Any, field_path: str, replacement: str) -> None:
    parts = [part for part in field_path.split(".") if part]
    if not parts:
        raise AuthorCollaborationError("Patch field path is required")
    current = value
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = replacement
    else:
        current[final] = replacement


def _default_thread_title(stage_id: str, label: str) -> str:
    stage = {
        "spine": "脊柱",
        "cast": "人物",
        "volumes": "分卷",
        "detail": "细纲",
        "text": "正文",
    }[stage_id]
    return f"{stage} · {label.strip() or '新对话'}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "AuthorCollaborationError",
    "AuthorCollaborationService",
    "AuthorCollaborationUnavailable",
    "CollaborationThreadBusy",
    "ContextReconfirmationRequired",
    "PatchWritebackUnavailable",
]
