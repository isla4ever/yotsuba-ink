from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from novel_workflow.output_contracts.author_collaboration import (
    ArtifactPatchCandidate,
    ArtifactPatchOperation,
    CollaborationMessage,
)
from novel_workflow.references.collaboration_context import (
    CollaborationContextCompiler,
)
from novel_workflow.runtime.graph.author_collaboration_requests import (
    CollaborationGenerationRequest,
    CollaborationProviderResult,
    compile_collaboration_provider_input,
)
from novel_workflow.runtime.graph.provider_requests import ProviderOperationError


class AuthorCollaborationState(TypedDict, total=False):
    run_id: str
    collaboration_thread_id: str
    active_turn_id: str
    stage_id: str
    source_ref: str
    context_receipt_ref: str
    provider_operation_ref: str
    assistant_message_ref: str
    patch_candidate_ref: str
    status_revision: int


class AuthorCollaborationExecutor:
    def __init__(self, stores: Any, provider: Any) -> None:
        self.stores = stores
        self.provider = provider
        self.context = CollaborationContextCompiler(stores)

    def validate_source(self, state: AuthorCollaborationState) -> dict[str, Any]:
        thread = self.stores.collaboration.read_thread(
            state["run_id"],
            state["collaboration_thread_id"],
        )
        source_ref, signature, _ = self.context.source_snapshot(thread)
        if (
            source_ref != thread.scope.source_ref
            or signature != thread.scope.source_signature
        ):
            raise ValueError("collaboration_source_stale")
        turn = self.stores.collaboration.read_turn(
            state["run_id"],
            thread.thread_id,
            state["active_turn_id"],
        )
        envelope = self.stores.collaboration_contexts.read(
            state["run_id"],
            turn.context_receipt_ref,
        )
        if (
            envelope.receipt.thread_id != thread.thread_id
            or envelope.receipt.turn_id != turn.turn_id
            or envelope.receipt.receipt_hash != turn.context_preview_signature
        ):
            raise ValueError("context_reconfirmation_required")
        return {
            "stage_id": thread.stage_id,
            "source_ref": source_ref,
            "context_receipt_ref": turn.context_receipt_ref,
        }

    async def call_provider(self, state: AuthorCollaborationState) -> dict[str, Any]:
        run_id = state["run_id"]
        thread_id = state["collaboration_thread_id"]
        turn_id = state["active_turn_id"]
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        turn = self.stores.collaboration.read_turn(run_id, thread_id, turn_id)
        envelope = self.stores.collaboration_contexts.read(
            run_id,
            turn.context_receipt_ref,
        )
        operation_key = f"collab:{thread_id}:{turn_id}:{turn.attempt}"
        request = CollaborationGenerationRequest(
            operation_key=operation_key,
            run_id=run_id,
            thread_id=thread_id,
            turn_id=turn_id,
            stage_id=thread.stage_id,
            mode=turn.mode,
            binding=thread.provider_binding,
            context_receipt_ref=turn.context_receipt_ref,
            material=envelope.material,
            selection_field_path=(
                turn.selection_anchor.field_path if turn.selection_anchor else ""
            ),
        )
        provider_input = compile_collaboration_provider_input(request)
        receipt = self.stores.operations.begin_provider(
            run_id=run_id,
            operation_key=operation_key,
            kind="author_collaboration",
            provider_profile_id=thread.provider_binding.provider_profile_id,
            model=thread.provider_binding.model,
            provider_input=provider_input,
        )
        if receipt.status == "succeeded":
            return {"provider_operation_ref": operation_key}
        if receipt.status == "provider_returned":
            return {"provider_operation_ref": operation_key}
        if receipt.status != "pending":
            raise ValueError(f"Collaboration Provider operation is {receipt.status}")

        self.stores.collaboration.transition_turn(
            run_id,
            thread_id,
            turn_id,
            "streaming",
            provider_operation_ref=operation_key,
        )
        self.stores.collaboration.append_event(
            run_id,
            thread_id,
            "turn.streaming",
            turn_id=turn_id,
            payload={"provider_profile_id": receipt.provider_profile_id, "model": receipt.model},
        )
        try:
            result = await self.provider.generate_collaboration_turn(request)
        except ProviderOperationError as exc:
            if exc.provider_result is not None:
                self.stores.operations.record_provider_return(
                    run_id,
                    operation_key,
                    exc.provider_result,
                    usage=exc.usage,
                    diagnostic=exc.diagnostic,
                )
                self.stores.operations.reject_provider_contract(
                    run_id,
                    operation_key,
                    {"code": "collaboration_contract_invalid", "message": str(exc)},
                    diagnostic=exc.diagnostic,
                )
                self.stores.collaboration.transition_turn(
                    run_id,
                    thread_id,
                    turn_id,
                    "contract_rejected",
                    error={"code": "collaboration_contract_invalid", "message": str(exc)},
                )
                self._emit_terminal_event(
                    run_id,
                    thread_id,
                    turn_id,
                    "turn.failed",
                    "collaboration.turn_failed",
                    "contract_rejected",
                    {"code": "collaboration_contract_invalid"},
                )
                return {"provider_operation_ref": operation_key}
            self.stores.operations.fail(
                run_id,
                operation_key,
                {"code": "provider_failed", "message": str(exc)},
                usage=exc.usage,
                diagnostic=exc.diagnostic,
            )
            self.stores.collaboration.transition_turn(
                run_id,
                thread_id,
                turn_id,
                "failed",
                error={"code": "provider_failed", "message": str(exc)},
            )
            self._emit_terminal_event(
                run_id,
                thread_id,
                turn_id,
                "turn.failed",
                "collaboration.turn_failed",
                "failed",
                {"code": "provider_failed"},
            )
            return {"provider_operation_ref": operation_key}
        self.stores.operations.record_provider_return(
            run_id,
            operation_key,
            result.model_dump(mode="json"),
            usage=result.usage,
            diagnostic=result.diagnostic,
        )
        return {"provider_operation_ref": operation_key}

    def persist_result(self, state: AuthorCollaborationState) -> dict[str, Any]:
        run_id = state["run_id"]
        thread_id = state["collaboration_thread_id"]
        turn_id = state["active_turn_id"]
        turn = self.stores.collaboration.read_turn(run_id, thread_id, turn_id)
        if turn.status in {"failed", "cancelled", "contract_rejected"}:
            return {}
        operation_key = state["provider_operation_ref"]
        receipt = self.stores.operations.read(run_id, operation_key)
        if receipt.status == "succeeded":
            result = CollaborationProviderResult.model_validate(receipt.result)
        elif receipt.status == "provider_returned":
            try:
                result = CollaborationProviderResult.model_validate(
                    receipt.provider_result
                )
            except Exception as exc:
                self.stores.operations.reject_provider_contract(
                    run_id,
                    operation_key,
                    {"code": "collaboration_contract_invalid", "message": str(exc)},
                )
                self.stores.collaboration.transition_turn(
                    run_id,
                    thread_id,
                    turn_id,
                    "contract_rejected",
                    error={"code": "collaboration_contract_invalid", "message": str(exc)},
                )
                self._emit_terminal_event(
                    run_id,
                    thread_id,
                    turn_id,
                    "turn.failed",
                    "collaboration.turn_failed",
                    "contract_rejected",
                    {"code": "collaboration_contract_invalid"},
                )
                return {}
        else:
            raise ValueError("Collaboration result requires a persisted Provider return")

        patch = self._patch_candidate(state, result)
        message_id = f"message-assistant-{turn_id}"
        envelope = self.stores.collaboration_contexts.read(
            run_id,
            turn.context_receipt_ref,
        )
        message = self.stores.collaboration.write_message(
            run_id,
            CollaborationMessage(
                message_id=message_id,
                thread_id=thread_id,
                turn_id=turn_id,
                role="assistant",
                mode=turn.mode,
                content=result.content,
                context_receipt_ref=turn.context_receipt_ref,
                patch_candidate_ref=patch.patch_id if patch else "",
                plan=result.plan,
                source_refs=[item.source_ref for item in envelope.receipt.sources],
                created_at=_now(),
            ),
        )
        if receipt.status == "provider_returned":
            self.stores.operations.accept_provider_result(
                run_id,
                operation_key,
                result.model_dump(mode="json"),
            )
        self.stores.collaboration.transition_turn(
            run_id,
            thread_id,
            turn_id,
            "completed",
            assistant_message_ref=message.message_id,
            patch_candidate_ref=patch.patch_id if patch else "",
        )
        if patch is not None:
            self.stores.collaboration.append_event(
                run_id,
                thread_id,
                "patch.ready",
                turn_id=turn_id,
                payload={"patch_id": patch.patch_id},
            )
            self.stores.events.append(
                run_id,
                event_id=f"{patch.patch_id}:ready",
                type="collaboration.patch_ready",
                stage_id=patch.stage_id,
                node_id="author_collaboration.persist_result",
                status="awaiting_decision",
                payload={"thread_id": thread_id, "turn_id": turn_id, "patch_id": patch.patch_id},
            )
        self._emit_terminal_event(
            run_id,
            thread_id,
            turn_id,
            "turn.completed",
            "collaboration.turn_completed",
            "completed",
            {"message_id": message.message_id, "patch_id": patch.patch_id if patch else ""},
        )
        return {
            "assistant_message_ref": message.message_id,
            "patch_candidate_ref": patch.patch_id if patch else "",
            "status_revision": int(state.get("status_revision") or 0) + 1,
        }

    def _patch_candidate(
        self,
        state: AuthorCollaborationState,
        result: CollaborationProviderResult,
    ) -> ArtifactPatchCandidate | None:
        run_id = state["run_id"]
        thread_id = state["collaboration_thread_id"]
        turn_id = state["active_turn_id"]
        turn = self.stores.collaboration.read_turn(run_id, thread_id, turn_id)
        if turn.mode != "revise":
            return None
        selection = turn.selection_anchor
        if selection is None or not result.replacement.strip() or not result.rationale.strip():
            raise ValueError("Revise mode requires a selection-bound replacement")
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        semantic = {
            "thread_id": thread_id,
            "turn_id": turn_id,
            "source_ref": thread.scope.source_ref,
            "source_signature": thread.scope.source_signature,
            "selection_anchor_id": selection.anchor_id,
            "replacement": result.replacement,
        }
        patch_id = f"patch-{_digest(semantic)[:40]}"
        patch = ArtifactPatchCandidate(
            patch_id=patch_id,
            thread_id=thread_id,
            turn_id=turn_id,
            run_id=run_id,
            stage_id=thread.stage_id,
            source_ref=thread.scope.source_ref,
            source_signature=thread.scope.source_signature,
            unit_ref=thread.scope.unit_ref,
            operations=[
                ArtifactPatchOperation(
                    field_path=selection.field_path,
                    before_hash=selection.selected_text_hash,
                    selection_anchor_id=selection.anchor_id,
                    replacement=result.replacement.strip(),
                    rationale=result.rationale.strip(),
                )
            ],
            context_receipt_ref=turn.context_receipt_ref,
            provider_operation_ref=state["provider_operation_ref"],
            created_at=_now(),
            updated_at=_now(),
        )
        return self.stores.collaboration.write_patch(patch)

    def _emit_terminal_event(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
        stream_type: str,
        run_type: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        self.stores.collaboration.append_event(
            run_id,
            thread_id,
            stream_type,
            turn_id=turn_id,
            payload=payload,
        )
        thread = self.stores.collaboration.read_thread(run_id, thread_id)
        self.stores.events.append(
            run_id,
            event_id=f"{turn_id}:{status}",
            type=run_type,
            stage_id=thread.stage_id,
            node_id="author_collaboration",
            status=status,
            payload={"thread_id": thread_id, "turn_id": turn_id, **payload},
        )


def build_author_collaboration_graph(
    executor: AuthorCollaborationExecutor,
    *,
    checkpointer: Any,
):
    builder = StateGraph(AuthorCollaborationState)
    builder.add_node("validate_source_binding", executor.validate_source)
    builder.add_node("call_collaboration_provider", executor.call_provider)
    builder.add_node("persist_assistant_message", executor.persist_result)
    builder.add_edge(START, "validate_source_binding")
    builder.add_edge("validate_source_binding", "call_collaboration_provider")
    builder.add_edge("call_collaboration_provider", "persist_assistant_message")
    builder.add_edge("persist_assistant_message", END)
    return builder.compile(
        checkpointer=checkpointer,
        name="yotsuba_author_collaboration",
    )


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "AuthorCollaborationExecutor",
    "AuthorCollaborationState",
    "build_author_collaboration_graph",
]
