"""Provider execution sidecar for Phase 32 author collaboration turns."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from novel_workflow.output_contracts.phase32_author_collaboration import (
    Phase32ArtifactPatchCandidate,
    Phase32ArtifactPatchOperation,
    Phase32CollaborationMessage,
    Phase32CollaborationTurn,
    Phase32ProviderCollaborationDiscussResult,
    Phase32ProviderCollaborationPatchResult,
    Phase32ProviderCollaborationPlanResult,
)
from novel_workflow.providers.base import PROMPT_SYSTEM_SPLIT
from novel_workflow.providers.frozen_contract import prompt_digest, schema_digest
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.openai_request import ensure_structured_prompt
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderGateway,
    Phase32ProviderReadinessGate,
    Phase32ProviderRequest,
    Phase32ProviderResponse,
    Phase32ProviderTaskSnapshot,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.references.phase32_collaboration_context import (
    Phase32CollaborationContextCompiler,
)
from novel_workflow.storage.phase32_collaboration_context_store import (
    Phase32CollaborationContextStore,
)
from novel_workflow.storage.phase32_collaboration_store import Phase32CollaborationStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceiptConflict,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32CollaborationExecutionError(ValueError):
    code = "phase32_collaboration_execution_failed"


class Phase32CollaborationExecutor:
    def __init__(
        self,
        collaboration: Phase32CollaborationStore,
        contexts: Phase32CollaborationContextStore,
        context_compiler: Phase32CollaborationContextCompiler,
        provider_inputs: Phase32ProviderInputStore,
        provider_operations: Phase32ProviderOperationStore,
        gateway: Phase32ProviderGateway,
    ) -> None:
        self.collaboration = collaboration
        self.contexts = contexts
        self.context_compiler = context_compiler
        self.provider_inputs = provider_inputs
        self.provider_operations = provider_operations
        self.gateway = gateway

    async def execute(
        self,
        run_id: str,
        thread_id: str,
        turn_id: str,
    ) -> Phase32CollaborationTurn:
        thread = self.collaboration.read_thread(run_id, thread_id)
        turn = self.collaboration.read_turn(run_id, thread_id, turn_id)
        if turn.status in {"completed", "cancelled", "failed", "contract_rejected"}:
            return turn
        self.context_compiler.source_snapshot(thread)
        envelope = self.contexts.read(run_id, turn.context_receipt_ref)
        binding = _binding(thread, turn.mode)
        request = _request(thread, turn, envelope.material, binding)
        request_payload = request.model_dump(mode="json")
        request_signature = provider_request_signature(request_payload)
        input_snapshot = self.provider_inputs.write(
            run_id=run_id,
            operation_key=request.operation_key,
            stage_id=thread.stage_id,
            request=request_payload,
        )
        execution = binding.execution
        pricing = execution.pricing_snapshot
        receipt = self.provider_operations.begin(
            run_id=run_id,
            operation_key=request.operation_key,
            stage_id=thread.stage_id,
            request_signature=request_signature,
            provider_input_ref=input_snapshot.provider_input_ref,
            provider_profile_id=execution.provider_profile_id,
            provider_template_id=execution.provider_template_id,
            model_id=execution.model_id,
            pricing_snapshot_ref=pricing.snapshot_ref,
        )
        operation_ref = receipt.receipt_ref
        turn = self.collaboration.transition_turn(
            run_id,
            thread_id,
            turn_id,
            "streaming",
            provider_operation_ref=operation_ref,
        )
        self.collaboration.append_event(
            run_id,
            thread_id,
            "turn.streaming",
            turn_id=turn_id,
            payload={"provider_operation_ref": operation_ref},
        )
        if receipt.status == "succeeded":
            return self._finish_from_result(thread, turn, dict(receipt.result or {}))
        if receipt.status == "contract_rejected":
            return self._reject_turn(thread, turn, dict(receipt.diagnostic))
        lease_owner = f"phase32-collaboration:{os.getpid()}:{uuid4().hex}"
        if receipt.status == "pending":
            receipt = self.provider_operations.claim_pending(
                run_id=run_id,
                operation_key=request.operation_key,
                request_signature=request_signature,
                lease_owner=lease_owner,
                lease_seconds=180,
                max_transport_attempts=3,
            )
        if receipt.status == "pending":
            if isinstance(self.gateway, Phase32ProviderReadinessGate):
                self.gateway.ensure_ready(binding)
            try:
                raw = await self.gateway.generate(request, binding=binding)
                response = Phase32ProviderResponse.model_validate(raw)
            except Exception as exc:
                try:
                    self.provider_operations.release_pending(
                        run_id=run_id,
                        operation_key=request.operation_key,
                        request_signature=request_signature,
                        lease_owner=lease_owner,
                        diagnostic={"code": "provider_transport_failed"},
                    )
                except Phase32ProviderOperationReceiptConflict:
                    pass
                return self._fail_turn(
                    thread,
                    turn,
                    code="provider_transport_failed",
                    message="Author collaboration Provider request failed",
                )
            receipt = self.provider_operations.record_return(
                run_id=run_id,
                operation_key=request.operation_key,
                request_signature=request_signature,
                raw_provider_payload=response.payload,
                usage=response.usage,
                diagnostic=response.diagnostic,
                pricing_snapshot=pricing,
                lease_owner=lease_owner,
            )
        if receipt.raw_provider_payload is None:
            return self._reject_turn(
                thread,
                turn,
                {"code": "collaboration_response_missing"},
                request=request,
                request_signature=request_signature,
            )
        try:
            parsed = _parse_result(turn.mode, receipt.raw_provider_payload)
        except Exception as exc:
            return self._reject_turn(
                thread,
                turn,
                {"code": "collaboration_contract_invalid", "message": str(exc)},
                request=request,
                request_signature=request_signature,
            )
        result = self._persist_result(thread, turn, parsed)
        self.provider_operations.succeed(
            run_id=run_id,
            operation_key=request.operation_key,
            request_signature=request_signature,
            result=result,
        )
        return self._finish_from_result(thread, turn, result)

    def _persist_result(
        self,
        thread,
        turn,
        parsed: BaseModel,
    ) -> dict[str, Any]:
        patch = None
        if isinstance(parsed, Phase32ProviderCollaborationPatchResult):
            selection = turn.selection_anchor
            if selection is None:
                raise Phase32CollaborationExecutionError(
                    "A revise result requires an exact selection anchor"
                )
            patch_identity = {
                "thread_id": thread.thread_id,
                "turn_id": turn.turn_id,
                "source_signature": thread.scope.source_signature,
                "field_path": selection.field_path,
                "before_hash": selection.selected_text_hash,
                "replacement": parsed.replacement,
            }
            patch_id = f"p32-patch-{canonical_digest(patch_identity)}"
            patch = self.collaboration.write_patch(
                Phase32ArtifactPatchCandidate(
                    patch_id=patch_id,
                    thread_id=thread.thread_id,
                    turn_id=turn.turn_id,
                    run_id=thread.run_id,
                    creation_route_id=thread.creation_route_id,
                    route_revision=thread.route_revision,
                    stage_id=thread.stage_id,
                    artifact_kind=thread.artifact_kind,
                    source_artifact_ref=thread.scope.artifact_ref,
                    source_signature=thread.scope.source_signature,
                    effective_payload_digest=thread.scope.effective_payload_digest,
                    unit_ref=thread.scope.unit_ref,
                    operations=(
                        Phase32ArtifactPatchOperation(
                            field_path=selection.field_path,
                            before_hash=selection.selected_text_hash,
                            selection_anchor_id=selection.anchor_id,
                            replacement=parsed.replacement,
                            rationale=parsed.rationale,
                        ),
                    ),
                    context_receipt_ref=turn.context_receipt_ref,
                    provider_operation_ref=turn.provider_operation_ref,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        message_id = f"p32-message-assistant-{turn.turn_id}"
        message = self.collaboration.write_message(
            thread.run_id,
            Phase32CollaborationMessage(
                message_id=message_id,
                thread_id=thread.thread_id,
                turn_id=turn.turn_id,
                role="assistant",
                mode=turn.mode,
                content=parsed.response,
                context_receipt_ref=turn.context_receipt_ref,
                patch_candidate_ref=patch.patch_id if patch else "",
                plan=(
                    parsed.plan
                    if isinstance(parsed, Phase32ProviderCollaborationPlanResult)
                    else None
                ),
                source_refs=(thread.scope.artifact_ref,),
                created_at=_now(),
            ),
        )
        if patch is not None:
            self.collaboration.append_event(
                thread.run_id,
                thread.thread_id,
                "patch.ready",
                turn_id=turn.turn_id,
                payload={"patch_id": patch.patch_id},
            )
        return {
            "assistant_message_ref": message.message_id,
            "patch_candidate_ref": patch.patch_id if patch else "",
        }

    def _finish_from_result(self, thread, turn, result: dict[str, Any]):
        completed = self.collaboration.transition_turn(
            thread.run_id,
            thread.thread_id,
            turn.turn_id,
            "completed",
            assistant_message_ref=str(result.get("assistant_message_ref") or ""),
            patch_candidate_ref=str(result.get("patch_candidate_ref") or ""),
        )
        self.collaboration.append_event(
            thread.run_id,
            thread.thread_id,
            "turn.completed",
            turn_id=turn.turn_id,
            payload={"patch_candidate_ref": completed.patch_candidate_ref},
        )
        return completed

    def _reject_turn(
        self,
        thread,
        turn,
        diagnostic: dict[str, Any],
        *,
        request: Phase32ProviderRequest | None = None,
        request_signature: str = "",
    ):
        if request is not None:
            self.provider_operations.reject_contract(
                run_id=thread.run_id,
                operation_key=request.operation_key,
                request_signature=request_signature,
                diagnostic=diagnostic,
            )
        rejected = self.collaboration.transition_turn(
            thread.run_id,
            thread.thread_id,
            turn.turn_id,
            "contract_rejected",
            error=diagnostic,
        )
        self.collaboration.append_event(
            thread.run_id,
            thread.thread_id,
            "turn.failed",
            turn_id=turn.turn_id,
            payload=diagnostic,
        )
        return rejected

    def _fail_turn(self, thread, turn, *, code: str, message: str):
        failed = self.collaboration.transition_turn(
            thread.run_id,
            thread.thread_id,
            turn.turn_id,
            "failed",
            error={"code": code, "message": message},
        )
        self.collaboration.append_event(
            thread.run_id,
            thread.thread_id,
            "turn.failed",
            turn_id=turn.turn_id,
            payload={"code": code},
        )
        return failed


def _binding(thread, mode: str) -> Phase32StageProviderBindingSnapshot:
    model_type = _result_model(mode)
    schema = model_type.model_json_schema()
    prompt = _prompt_template(mode)
    task = Phase32ProviderTaskSnapshot(
        provider_task_kind="author_collaboration",
        artifact_kind=thread.artifact_kind,
        transport_task_name=f"author_collaboration.{mode}",
        prompt_template_id=f"author-collaboration-{mode}-v2",
        prompt_template=prompt,
        prompt_template_digest=prompt_digest(prompt),
        output_schema=schema,
        output_schema_digest=schema_digest(schema),
    )
    return Phase32StageProviderBindingSnapshot(
        workflow_id="author-collaboration-sidecar",
        creation_route_id=thread.creation_route_id,
        stage_id=thread.stage_id,
        execution=thread.provider_execution,
        task=task,
    )


def _request(thread, turn, material, binding) -> Phase32ProviderRequest:
    operation_key = f"{thread.run_id}:collaboration:{thread.thread_id}:{turn.turn_id}"
    binding_digest = canonical_digest(binding.model_dump(mode="json"))
    context = {
        "thread_identity": {
            "creation_route_id": thread.creation_route_id,
            "route_revision": thread.route_revision,
            "stage_id": thread.stage_id,
            "artifact_kind": thread.artifact_kind,
            "artifact_ref": thread.scope.artifact_ref,
            "effective_payload_digest": thread.scope.effective_payload_digest,
            "unit_ref": thread.scope.unit_ref,
        },
        "material": material,
    }
    base_prompt = (
        binding.task.prompt_template
        + PROMPT_SYSTEM_SPLIT
        + "以下是本轮冻结上下文。只使用给定来源，不补造未提供的事实：\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    policy = resolve_request_policy(
        binding.execution.provider_template,
        model=binding.execution.model_id,
        task_name=binding.task.transport_task_name,
    )
    rendered = ensure_structured_prompt(
        base_prompt,
        task_name=binding.task.transport_task_name,
        schema=binding.task.output_schema,
        policy=policy,
    )
    return Phase32ProviderRequest(
        operation_key=operation_key,
        run_id=thread.run_id,
        creation_route_id=thread.creation_route_id,
        route_revision=thread.route_revision,
        stage_id=thread.stage_id,
        provider_task_kind="author_collaboration",
        artifact_kind=thread.artifact_kind,
        provider_profile_id=binding.execution.provider_profile_id,
        provider_template_id=binding.execution.provider_template_id,
        model_id=binding.execution.model_id,
        provider_binding_digest=binding_digest,
        transport_task_name=binding.task.transport_task_name,
        rendered_prompt=rendered,
        rendered_prompt_digest=prompt_digest(rendered),
        output_schema=binding.task.output_schema,
        output_schema_digest=binding.task.output_schema_digest,
        context=context,
        direction="",
    )


def _result_model(mode: str) -> type[BaseModel]:
    if mode == "plan":
        return Phase32ProviderCollaborationPlanResult
    if mode == "revise":
        return Phase32ProviderCollaborationPatchResult
    return Phase32ProviderCollaborationDiscussResult


def _parse_result(mode: str, payload: dict[str, Any]) -> BaseModel:
    return _result_model(mode).model_validate(payload)


def _prompt_template(mode: str) -> str:
    shared = (
        "你是 Yotsuba Ink 的专业作者协作伙伴。当前对话绑定一个不可变的 Phase 32 来源快照。"
        "引用上下文要克制、可追溯；不得直接修改 Artifact、Canon、Wiki 或其他运行状态。"
    )
    if mode == "plan":
        return shared + "先澄清目标并输出可执行方案，不输出替换正文。"
    if mode == "revise":
        return shared + "只改写作者明确选中的文字，返回 replacement 与 rationale，不扩张改动范围。"
    return shared + "回答作者问题并指出依据；不生成补丁。"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32CollaborationExecutionError",
    "Phase32CollaborationExecutor",
]
