from __future__ import annotations

from typing import TYPE_CHECKING

from novel_workflow.output_contracts.provider_tasks import ChapterEvidenceResult
from novel_workflow.runtime.graph.chapter_evidence_contract import (
    EvidenceFailure,
    EvidenceStateBinding,
    bind_evidence_spans,
    evidence_failure_from_exception,
    evidence_failure_from_receipt,
    project_evidence_state_bindings,
)
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    compile_provider_input,
)
from novel_workflow.storage.evidence_store import EvidenceSpan

if TYPE_CHECKING:
    from novel_workflow.runtime.graph.stage_executor import StageExecutor


async def execute_evidence_request(
    executor: StageExecutor,
    request: ChapterEvidenceRequest,
) -> tuple[
    ChapterEvidenceResult | None,
    list[list[EvidenceSpan]] | None,
    list[EvidenceStateBinding] | None,
    EvidenceFailure | None,
]:
    operations = executor.operations
    receipt = operations.begin_provider(
        run_id=request.run_id,
        operation_key=request.operation_key,
        kind="chapter_evidence",
        provider_profile_id=request.binding.provider_profile_id,
        model=request.binding.model,
        provider_input=compile_provider_input(request),
    )
    if receipt.status in {"failed", "contract_rejected"}:
        return None, None, None, evidence_failure_from_receipt(receipt)

    response = None
    try:
        if receipt.status == "succeeded":
            result = ChapterEvidenceResult.model_validate(receipt.result)
        else:
            if receipt.status == "provider_returned":
                provider_result = receipt.provider_result
            else:
                response = await executor.provider.extract_chapter_evidence(request)
                provider_result = response.payload
                operations.record_provider_return(
                    request.run_id,
                    request.operation_key,
                    provider_result,
                    usage=response.usage,
                    diagnostic=response.diagnostic,
                )
            result = ChapterEvidenceResult.model_validate(provider_result)
        state_bindings = project_evidence_state_bindings(result, request.context)
        bound_spans = bind_evidence_spans(request.content, result)
    except Exception as exc:
        diagnostic = (
            response.diagnostic
            if response is not None
            else getattr(exc, "diagnostic", {})
        )
        current = operations.read(request.run_id, request.operation_key)
        if current.status == "pending":
            operations.fail(
                request.run_id,
                request.operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=(
                    response.usage
                    if response is not None
                    else getattr(exc, "usage", {})
                ),
                diagnostic=diagnostic,
            )
        elif current.status == "provider_returned":
            operations.reject_provider_contract(
                request.run_id,
                request.operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                diagnostic=diagnostic,
            )
        return None, None, None, evidence_failure_from_exception(exc, diagnostic)

    if receipt.status in {"pending", "provider_returned"}:
        operations.accept_provider_result(
            request.run_id,
            request.operation_key,
            result.model_dump(mode="json"),
        )
    return result, bound_spans, state_bindings, None


__all__ = ["execute_evidence_request"]
