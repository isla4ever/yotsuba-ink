"""Recoverable image sub-operations for one Phase 32 Cover proposal."""

from __future__ import annotations

import os
from uuid import uuid4

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    CoverArtifact,
    CoverCandidate,
    CoverCandidateProposal,
    CoverProposal,
)
from novel_workflow.providers.phase32_contract import (
    Phase32CoverImageRequest,
    Phase32ImageProviderExecutionSnapshot,
    Phase32ProviderGateway,
)
from novel_workflow.storage.cover_asset_store import CoverAssetRecord, CoverAssetStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationLeaseConflict,
    Phase32ProviderOperationReceipt,
    Phase32ProviderOperationReceiptConflict,
    Phase32ProviderOperationRetryExhausted,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


class Phase32CoverGenerationError(ValueError):
    def __init__(self, message: str, *, code: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class Phase32CoverGenerator:
    """Turn a text proposal into immutable, receipted cover image assets."""

    def __init__(
        self,
        *,
        gateway: Phase32ProviderGateway,
        provider_operations: Phase32ProviderOperationStore,
        provider_inputs: Phase32ProviderInputStore,
        cover_assets: CoverAssetStore,
        lease_seconds: int,
        max_transport_attempts: int,
    ) -> None:
        self.gateway = gateway
        self.provider_operations = provider_operations
        self.provider_inputs = provider_inputs
        self.cover_assets = cover_assets
        self.lease_seconds = lease_seconds
        self.max_transport_attempts = max_transport_attempts

    async def materialize(
        self,
        *,
        definition: GraphRunDefinition,
        proposal: CoverProposal,
        binding: Phase32ImageProviderExecutionSnapshot | None,
        proposal_operation_key: str,
        generation_attempt: int,
    ) -> CoverArtifact:
        if binding is None:
            raise Phase32CoverGenerationError(
                "Cover generation requires a frozen image Provider binding",
                code="cover_image_binding_missing",
            )
        if len(proposal.candidates) != binding.candidate_count:
            raise Phase32CoverGenerationError(
                "Cover proposal candidate count does not match the frozen image binding",
                code="provider_contract_failed",
            )
        candidates: list[CoverCandidate] = []
        for candidate_index, candidate in enumerate(proposal.candidates, start=1):
            asset = await self._materialize_candidate(
                definition=definition,
                binding=binding,
                proposal=candidate,
                candidate_index=candidate_index,
                proposal_operation_key=proposal_operation_key,
                generation_attempt=generation_attempt,
            )
            candidates.append(
                CoverCandidate(
                    asset_ref=asset.asset_id,
                    alt_text=candidate.alt_text,
                    visual_notes=candidate.visual_notes,
                )
            )
        return CoverArtifact(brief=proposal.brief, candidates=tuple(candidates))

    async def _materialize_candidate(
        self,
        *,
        definition: GraphRunDefinition,
        binding: Phase32ImageProviderExecutionSnapshot,
        proposal: CoverCandidateProposal,
        candidate_index: int,
        proposal_operation_key: str,
        generation_attempt: int,
    ) -> CoverAssetRecord:
        operation_key = f"{proposal_operation_key}:image:{candidate_index}"
        request = Phase32CoverImageRequest(
            operation_key=operation_key,
            run_id=definition.run_id,
            creation_route_id=definition.creation_route_id,
            route_revision=definition.route_contract.route_revision,
            candidate_index=candidate_index,
            generation_attempt=generation_attempt,
            provider_profile_id=binding.provider_profile_id,
            provider_template_id=binding.provider_template_id,
            model_id=binding.model_id,
            provider_binding_digest=canonical_digest(binding.model_dump(mode="json")),
            size=binding.size,
            quality=binding.quality,
            prompt=proposal.image_prompt,
        )
        request_payload = request.model_dump(mode="json")
        request_signature = provider_request_signature(request_payload)
        input_snapshot = self.provider_inputs.write(
            run_id=definition.run_id,
            operation_key=operation_key,
            stage_id="cover",
            request=request_payload,
        )
        receipt = self.provider_operations.begin(
            run_id=definition.run_id,
            operation_key=operation_key,
            stage_id="cover",
            request_signature=request_signature,
            provider_input_ref=input_snapshot.provider_input_ref,
            provider_profile_id=binding.provider_profile_id,
            provider_template_id=binding.provider_template_id,
            model_id=binding.model_id,
            pricing_snapshot_ref=binding.pricing_snapshot.snapshot_ref,
        )
        if receipt.status == "succeeded":
            return self._asset_from_receipt(
                definition.run_id,
                receipt,
                candidate_index=candidate_index,
                generation_attempt=generation_attempt,
            )
        if receipt.status == "contract_rejected":
            raise Phase32CoverGenerationError(
                "Cover image output was rejected by the immutable asset contract",
                code="cover_image_contract_failed",
            )

        lease_owner = f"phase32-cover:{os.getpid()}:{uuid4().hex}"
        if receipt.status == "pending":
            try:
                receipt = self.provider_operations.claim_pending(
                    run_id=definition.run_id,
                    operation_key=operation_key,
                    request_signature=request_signature,
                    lease_owner=lease_owner,
                    lease_seconds=self.lease_seconds,
                    max_transport_attempts=self.max_transport_attempts,
                )
            except (Phase32ProviderOperationLeaseConflict, Phase32ProviderOperationRetryExhausted) as exc:
                raise Phase32CoverGenerationError(
                    "Cover image operation is unavailable for recovery",
                    code="provider_transport_failed",
                    retryable=True,
                ) from exc

        if receipt.status == "pending":
            recovered = self.cover_assets.find_by_operation(definition.run_id, operation_key)
            if recovered is None:
                try:
                    image = await self.gateway.generate_cover_image(request, binding=binding)
                except Exception as exc:
                    try:
                        self.provider_operations.release_pending(
                            run_id=definition.run_id,
                            operation_key=operation_key,
                            request_signature=request_signature,
                            lease_owner=lease_owner,
                            diagnostic={"code": _public_transport_code(exc)},
                        )
                    except Phase32ProviderOperationReceiptConflict:
                        pass
                    raise Phase32CoverGenerationError(
                        "Cover image Provider transport failed",
                        code="provider_transport_failed",
                        retryable=True,
                    ) from exc
                try:
                    recovered = self.cover_assets.save(
                        definition.run_id,
                        operation_key=operation_key,
                        candidate_index=candidate_index,
                        generation_attempt=generation_attempt,
                        image=image,
                        expected_ratio=_expected_ratio(binding.size),
                    )
                except Exception as exc:
                    diagnostic = {"code": "cover_asset_contract_rejected"}
                    self.provider_operations.record_return(
                        run_id=definition.run_id,
                        operation_key=operation_key,
                        request_signature=request_signature,
                        raw_provider_payload={"candidate_index": candidate_index},
                        usage=getattr(image, "usage", {}),
                        diagnostic=diagnostic,
                        pricing_snapshot=binding.pricing_snapshot,
                        lease_owner=lease_owner,
                    )
                    self.provider_operations.reject_contract(
                        run_id=definition.run_id,
                        operation_key=operation_key,
                        request_signature=request_signature,
                        diagnostic=diagnostic,
                    )
                    raise Phase32CoverGenerationError(
                        "Generated cover bytes do not satisfy the immutable asset contract",
                        code="cover_image_contract_failed",
                    ) from exc
            receipt = self.provider_operations.record_return(
                run_id=definition.run_id,
                operation_key=operation_key,
                request_signature=request_signature,
                raw_provider_payload=_asset_receipt_payload(recovered),
                usage=recovered.usage,
                diagnostic={
                    "code": "",
                    "asset_ref": recovered.asset_id,
                    "width": recovered.width,
                    "height": recovered.height,
                },
                pricing_snapshot=binding.pricing_snapshot,
                lease_owner=lease_owner,
            )

        asset = self._asset_from_receipt(
            definition.run_id,
            receipt,
            candidate_index=candidate_index,
            generation_attempt=generation_attempt,
        )
        self.provider_operations.succeed(
            run_id=definition.run_id,
            operation_key=operation_key,
            request_signature=request_signature,
            result={"asset_ref": asset.asset_id},
        )
        return asset

    def _asset_from_receipt(
        self,
        run_id: str,
        receipt: Phase32ProviderOperationReceipt,
        *,
        candidate_index: int,
        generation_attempt: int,
    ) -> CoverAssetRecord:
        source = receipt.result if receipt.status == "succeeded" else receipt.raw_provider_payload
        asset_ref = str((source or {}).get("asset_ref") or "")
        if not asset_ref:
            raise Phase32CoverGenerationError(
                "Cover image receipt has no immutable asset reference",
                code="cover_image_recovery_failed",
            )
        try:
            asset = self.cover_assets.read(run_id, asset_ref)
            if (
                asset.operation_key != receipt.operation_key
                or asset.candidate_index != candidate_index
                or asset.generation_attempt != generation_attempt
            ):
                raise ValueError("Cover asset identity does not match its Provider operation")
            return asset
        except Exception as exc:
            raise Phase32CoverGenerationError(
                "Cover image receipt cannot recover its immutable asset",
                code="cover_image_recovery_failed",
            ) from exc


def _asset_receipt_payload(asset: CoverAssetRecord) -> dict[str, object]:
    return {
        "asset_ref": asset.asset_id,
        "sha256": asset.sha256,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "provider_asset_id": asset.provider_asset_id,
    }


def _expected_ratio(size: str) -> float:
    width, height = (int(value) for value in size.lower().split("x", 1))
    return width / height


def _public_transport_code(error: Exception) -> str:
    code = str(getattr(error, "code", "")).strip().lower()
    return code if code in {
        "insufficient_balance",
        "authentication_failed",
        "endpoint_or_model_unavailable",
        "rate_limited",
        "timeout",
        "network_error",
        "service_unavailable",
    } else "provider_transport_failed"


__all__ = ["Phase32CoverGenerationError", "Phase32CoverGenerator"]
