"""Provider/Artifact adapter for the dormant Phase 32 route graph.

The graph owns routing, review interrupts and checkpoints.  This module owns
the narrow boundary between a frozen Provider binding and one validated core
Artifact.  It deliberately does not import the legacy Provider request or
Artifact contracts.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from novel_workflow.orchestration.phase32_artifact_editing import (
    validate_phase32_artifact_payload,
)
from novel_workflow.orchestration.phase32_stage_reference_validation import (
    Phase32StageReferenceError,
    validate_phase32_stage_references,
)
from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
    Phase32TextOperationAdmission,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderGateway,
    Phase32ProviderRequest,
    Phase32ProviderReadinessGate,
    Phase32ProviderResponse,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    BookDeliveryArtifact,
    CoverArtifact,
    CoverProposal,
    ScriptDeliveryArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    DetailPlanIndexArtifact,
    Phase32CoreArtifact,
    SceneDeckArtifact,
    SectionPlanArtifact,
)
from novel_workflow.runtime.graph.route_graph import (
    RouteGraphDriver,
    RouteStageCandidate,
)
from novel_workflow.runtime.graph.phase32_provider_input import (
    Phase32ProviderContextError,
    compile_phase32_provider_request,
    compile_phase32_stage_context,
)
from novel_workflow.runtime.graph.phase32_cover_generation import (
    Phase32CoverGenerationError,
    Phase32CoverGenerator,
)
from novel_workflow.runtime.graph.route_run_state import RouteRunStateSnapshot
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationAttemptFenceConflict,
    Phase32ProviderOperationLeaseConflict,
    Phase32ProviderOperationReceipt,
    Phase32ProviderOperationReceiptConflict,
    Phase32ProviderOperationRetryExhausted,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.route_compiler import CompiledRouteStage
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.workflow_ids import is_image_acceptance_deferred_workflow_id

if TYPE_CHECKING:
    from novel_workflow.orchestration.phase32_writeback import Phase32WritebackService
    from novel_workflow.output_contracts.phase32_writeback import Phase32WritebackReceipt


class Phase32DriverError(ValueError):
    code = "phase32_driver_invalid"

    def __init__(
        self,
        message: str,
        *,
        code: str = "phase32_driver_invalid",
        stage_id: str = "",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage_id = stage_id
        self.retryable = retryable


class Phase32RouteDriver(RouteGraphDriver):
    """Validate Provider output and persist one route Artifact at a time."""

    def __init__(
        self,
        artifact_store: Phase32ArtifactStore,
        gateway: Phase32ProviderGateway,
        *,
        provider_operations: Phase32ProviderOperationStore | None = None,
        provider_inputs: Phase32ProviderInputStore | None = None,
        cover_assets: CoverAssetStore | None = None,
        exports: ExportStore | None = None,
        writeback: "Phase32WritebackService | None" = None,
        text_operation_admission: Phase32TextOperationAdmission | None = None,
        provider_lease_seconds: int = 120,
        provider_max_transport_attempts: int = 3,
    ) -> None:
        self.artifact_store = artifact_store
        self.gateway = gateway
        existing_inputs = provider_operations.provider_inputs if provider_operations else None
        self.provider_inputs = provider_inputs or existing_inputs or Phase32ProviderInputStore(
            artifact_store.root / ".provider_inputs"
        )
        self.provider_operations = provider_operations or Phase32ProviderOperationStore(
            artifact_store.root / ".provider_operations",
            provider_inputs=self.provider_inputs,
        )
        self.provider_operations.attach_provider_inputs(self.provider_inputs)
        self.cover_assets = cover_assets or CoverAssetStore(
            artifact_store.root.parent / "cover_assets"
        )
        self.exports = exports or ExportStore(artifact_store.root.parent / "exports")
        self.writeback = writeback
        self.text_operation_admission = text_operation_admission
        self.provider_lease_seconds = provider_lease_seconds
        self.provider_max_transport_attempts = provider_max_transport_attempts
        self.cover_generator = Phase32CoverGenerator(
            gateway=self.gateway,
            provider_operations=self.provider_operations,
            provider_inputs=self.provider_inputs,
            cover_assets=self.cover_assets,
            lease_seconds=self.provider_lease_seconds,
            max_transport_attempts=self.provider_max_transport_attempts,
        )

    def sequential_unit_refs(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
    ) -> tuple[str, ...]:
        """Resolve sequential prose units from their committed planning authority."""

        if definition.creation_route_id == "screenplay_sample" and stage.stage_id == "script":
            try:
                scene_deck = SceneDeckArtifact.model_validate(
                    _read_committed(
                        self.artifact_store,
                        definition,
                        state,
                        "scene_deck",
                    )
                )
            except Exception as exc:
                raise Phase32DriverError(
                    "Script unit order requires a committed Scene Deck",
                    stage_id=stage.stage_id,
                ) from exc
            return tuple(scene.scene_ref for scene in scene_deck.scenes)
        if definition.creation_route_id == "short_novel" and stage.stage_id == "text":
            try:
                section_plan = SectionPlanArtifact.model_validate(
                    _read_committed(
                        self.artifact_store,
                        definition,
                        state,
                        "section_plan",
                    )
                )
            except Exception as exc:
                raise Phase32DriverError(
                    "Short prose unit order requires a committed Section Plan",
                    stage_id=stage.stage_id,
                ) from exc
            return tuple(unit.unit_ref for unit in section_plan.units)
        if definition.creation_route_id == "long_novel" and stage.stage_id == "text":
            try:
                detail = DetailPlanIndexArtifact.model_validate(
                    _read_committed(
                        self.artifact_store,
                        definition,
                        state,
                        "rolling_detail",
                    )
                )
            except Exception as exc:
                raise Phase32DriverError(
                    "Chapter order requires a committed Rolling Detail Artifact",
                    stage_id=stage.stage_id,
                ) from exc
            return tuple(
                chapter.chapter_ref
                for window in detail.windows
                for chapter in window.chapters
            )
        return ()

    async def generate_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        direction: str = "",
    ) -> RouteStageCandidate:
        if stage.provider_task_kind is None:
            raise Phase32DriverError(
                f"Deterministic stage {stage.stage_id} cannot call a Provider"
            )
        binding_digest, binding = _provider_binding(definition, stage.stage_id)
        operation_key = _operation_key(definition, state, stage, direction)
        try:
            context = compile_phase32_stage_context(
                artifact_store=self.artifact_store,
                definition=definition,
                state=state,
                stage=stage,
            )
        except Phase32ProviderContextError as exc:
            raise Phase32DriverError(
                str(exc),
                stage_id=stage.stage_id,
            ) from exc
        request = compile_phase32_provider_request(
            definition=definition,
            state=state,
            stage=stage,
            binding=binding,
            binding_digest=binding_digest,
            operation_key=operation_key,
            context=context,
            direction=direction,
        )
        if isinstance(self.gateway, Phase32ProviderReadinessGate):
            self.gateway.ensure_ready(binding)
        request_payload = request.model_dump(mode="json")
        request_signature = provider_request_signature(request_payload)
        execution = binding.execution
        pricing = execution.pricing_snapshot
        self._require_text_operation_run(definition, stage.stage_id)
        try:
            input_snapshot = self.provider_inputs.write(
                run_id=definition.run_id,
                operation_key=operation_key,
                stage_id=stage.stage_id,
                request=request_payload,
            )
        except Exception as exc:
            raise Phase32DriverError(
                f"Provider input snapshot failed for {definition.creation_route_id}/{stage.stage_id}"
            ) from exc
        receipt = self.provider_operations.begin(
            run_id=definition.run_id,
            operation_key=operation_key,
            stage_id=stage.stage_id,
            request_signature=request_signature,
            provider_input_ref=input_snapshot.provider_input_ref,
            provider_profile_id=execution.provider_profile_id,
            provider_template_id=execution.provider_template_id,
            model_id=execution.model_id,
            pricing_snapshot_ref=pricing.snapshot_ref,
        )
        lease_owner = f"phase32-driver:{os.getpid()}:{uuid4().hex}"
        if receipt.status == "succeeded":
            return self._candidate_from_succeeded_receipt(
                definition=definition,
                state=state,
                stage=stage,
                receipt=receipt,
            )
        if receipt.status == "contract_rejected":
            raise Phase32DriverError(
                f"Provider contract was rejected for {definition.creation_route_id}/{stage.stage_id}",
                code="provider_contract_failed",
                stage_id=stage.stage_id,
            )
        admission_fence: Phase32ProviderOperationAdmissionFence | None = None
        if receipt.status == "pending":
            admission_fence = self._admit_text_operation(
                definition=definition,
                stage=stage,
                request=request,
                binding=binding,
                request_signature=request_signature,
            )
            try:
                receipt = self.provider_operations.claim_pending(
                    run_id=definition.run_id,
                    operation_key=operation_key,
                    request_signature=request_signature,
                    lease_owner=lease_owner,
                    admission_fence=admission_fence,
                    lease_seconds=self.provider_lease_seconds,
                    max_transport_attempts=self.provider_max_transport_attempts,
                )
            except (
                Phase32ProviderOperationAttemptFenceConflict,
                Phase32ProviderOperationLeaseConflict,
            ) as exc:
                raise Phase32DriverError(
                    f"Provider operation is already running for {definition.creation_route_id}/{stage.stage_id}",
                    code="provider_transport_failed",
                    stage_id=stage.stage_id,
                    retryable=True,
                ) from exc
            except Phase32ProviderOperationRetryExhausted as exc:
                raise Phase32DriverError(
                    f"Provider transport retry limit reached for {definition.creation_route_id}/{stage.stage_id}",
                    code="provider_transport_failed",
                    stage_id=stage.stage_id,
                    retryable=True,
                ) from exc
        if receipt.status == "pending":
            try:
                raw_response = await self.gateway.generate(request, binding=binding)
            except Exception as exc:
                try:
                    diagnostic_code = _public_transport_code(exc)
                    self.provider_operations.release_pending(
                        run_id=definition.run_id,
                        operation_key=operation_key,
                        request_signature=request_signature,
                        lease_owner=lease_owner,
                        claimed_transport_attempt=receipt.transport_attempts,
                        diagnostic={"code": diagnostic_code},
                    )
                except Phase32ProviderOperationReceiptConflict:
                    # Preserve the transport error as the primary failure.  A
                    # competing process may already have reclaimed the lease.
                    pass
                # A transport failure is deliberately retryable.  The pending
                # receipt remains the single operation identity for the retry.
                raise Phase32DriverError(
                    f"Provider transport failed for {definition.creation_route_id}/{stage.stage_id}",
                    code="provider_transport_failed",
                    stage_id=stage.stage_id,
                    retryable=True,
                ) from exc
            try:
                response = Phase32ProviderResponse.model_validate(raw_response)
            except Exception as exc:
                # Preserve even an envelope-level malformed return as a
                # contract rejection when a payload-shaped object is present.
                raw_payload = _raw_payload(raw_response)
                diagnostic = {
                    "code": "provider_response_invalid",
                    "stage_id": stage.stage_id,
                }
                try:
                    self.provider_operations.record_return(
                        run_id=definition.run_id,
                        operation_key=operation_key,
                        request_signature=request_signature,
                        raw_provider_payload=raw_payload,
                        diagnostic=diagnostic,
                        pricing_snapshot=pricing,
                        lease_owner=lease_owner,
                        claimed_transport_attempt=receipt.transport_attempts,
                    )
                    self.provider_operations.reject_contract(
                        run_id=definition.run_id,
                        operation_key=operation_key,
                        request_signature=request_signature,
                        diagnostic=diagnostic,
                    )
                except Phase32ProviderOperationReceiptConflict as receipt_exc:
                    raise Phase32DriverError(
                        f"Provider receipt conflict for {definition.creation_route_id}/{stage.stage_id}"
                    ) from receipt_exc
                raise Phase32DriverError(
                    f"Provider response contract is invalid for {definition.creation_route_id}/{stage.stage_id}",
                    code="provider_contract_failed",
                    stage_id=stage.stage_id,
                ) from exc
            try:
                receipt = self.provider_operations.record_return(
                    run_id=definition.run_id,
                    operation_key=operation_key,
                    request_signature=request_signature,
                    raw_provider_payload=response.payload,
                    usage=response.usage,
                    diagnostic=response.diagnostic,
                    pricing_snapshot=pricing,
                    lease_owner=lease_owner,
                    claimed_transport_attempt=receipt.transport_attempts,
                )
            except Phase32ProviderOperationReceiptConflict as exc:
                raise Phase32DriverError(
                    f"Provider receipt conflict for {definition.creation_route_id}/{stage.stage_id}"
                ) from exc
        try:
            return await self._candidate_from_returned_receipt(
                definition=definition,
                state=state,
                stage=stage,
                receipt=receipt,
                request_signature=request_signature,
                operation_key=operation_key,
            )
        except Phase32DriverError:
            raise
        except Exception as exc:
            raise Phase32DriverError(
                f"Provider operation failed for {definition.creation_route_id}/{stage.stage_id}"
            ) from exc

    def _require_text_operation_run(
        self,
        definition: GraphRunDefinition,
        stage_id: str,
    ) -> None:
        if not _requires_text_operation_admission(definition):
            return
        if self.text_operation_admission is None:
            raise Phase32DriverError(
                "Continuity acceptance requires a persisted text-operation admission",
                code="phase32_text_operation_admission_required",
                stage_id=stage_id,
            )
        try:
            self.text_operation_admission.require_run(definition)
        except Exception as exc:
            raise Phase32DriverError(
                "Continuity acceptance Run admission was denied",
                code=getattr(
                    exc,
                    "code",
                    "phase32_text_operation_admission_denied",
                ),
                stage_id=stage_id,
            ) from exc

    def _admit_text_operation(
        self,
        *,
        definition: GraphRunDefinition,
        stage: CompiledRouteStage,
        request: Phase32ProviderRequest,
        binding: Phase32StageProviderBindingSnapshot,
        request_signature: str,
    ) -> Phase32ProviderOperationAdmissionFence | None:
        if not _requires_text_operation_admission(definition):
            return None
        if self.text_operation_admission is None:  # guarded before receipt creation
            raise Phase32DriverError(
                "Continuity acceptance requires a persisted text-operation admission",
                code="phase32_text_operation_admission_required",
                stage_id=stage.stage_id,
            )
        try:
            grant = self.text_operation_admission.admit_text_operation(
                definition=definition,
                request=request,
                binding=binding,
                request_signature=request_signature,
                max_transport_attempts=self.provider_max_transport_attempts,
            )
            return Phase32ProviderOperationAdmissionFence.model_validate(
                grant,
                from_attributes=True,
            )
        except Exception as exc:
            raise Phase32DriverError(
                "Continuity acceptance Provider operation exceeded its admission",
                code=getattr(
                    exc,
                    "code",
                    "phase32_text_operation_admission_denied",
                ),
                stage_id=stage.stage_id,
            ) from exc

    def _candidate_from_succeeded_receipt(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        receipt: Phase32ProviderOperationReceipt,
    ) -> RouteStageCandidate:
        result = receipt.result or {}
        artifact_ref = str(result.get("artifact_ref") or "")
        unit_ref = str(result.get("unit_ref") or "")
        if not artifact_ref:
            raise Phase32DriverError(
                f"Succeeded Provider receipt has no candidate for {definition.creation_route_id}/{stage.stage_id}"
            )
        try:
            record = self.artifact_store.read(definition.run_id, artifact_ref)
            if (
                record.status != "candidate"
                or record.stage_id != stage.stage_id
                or record.source_operation_key != receipt.operation_key
            ):
                raise ValueError("Receipt candidate identity does not match the Artifact")
            artifact = _parse_artifact(definition, stage, record.payload)
            _validate_stage_references(
                self.artifact_store,
                definition,
                state,
                stage,
                artifact,
            )
            _validate_cover_assets(
                self.cover_assets,
                definition.run_id,
                stage,
                artifact,
            )
            if _unit_ref(stage, artifact) != unit_ref:
                raise ValueError("Receipt candidate unit ref does not match the Artifact")
        except Exception as exc:
            raise Phase32DriverError(
                f"Succeeded Provider receipt cannot recover {definition.creation_route_id}/{stage.stage_id}"
            ) from exc
        return RouteStageCandidate(artifact_ref=artifact_ref, unit_ref=unit_ref)

    async def _candidate_from_returned_receipt(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        receipt: Phase32ProviderOperationReceipt,
        request_signature: str,
        operation_key: str,
    ) -> RouteStageCandidate:
        if receipt.raw_provider_payload is None:
            raise Phase32DriverError(
                f"Provider receipt has no returned payload for {definition.creation_route_id}/{stage.stage_id}"
            )
        try:
            if stage.stage_id == "cover":
                proposal = CoverProposal.model_validate(receipt.raw_provider_payload)
                _, binding = _provider_binding(definition, stage.stage_id)
                if (
                    binding.image_execution is not None
                    and len(proposal.candidates) != binding.image_execution.candidate_count
                ):
                    raise ValueError(
                        "Cover proposal does not match the frozen image candidate count"
                    )
            else:
                proposal = None
                artifact = _parse_artifact(definition, stage, receipt.raw_provider_payload)
        except Exception as exc:
            self.provider_operations.reject_contract(
                run_id=definition.run_id,
                operation_key=operation_key,
                request_signature=request_signature,
                diagnostic=_artifact_rejection_diagnostic(receipt.diagnostic, stage.stage_id),
            )
            raise Phase32DriverError(
                f"Artifact payload does not satisfy {definition.creation_route_id}/{stage.stage_id}",
                code="provider_contract_failed",
                stage_id=stage.stage_id,
            ) from exc
        try:
            if proposal is not None:
                if is_image_acceptance_deferred_workflow_id(definition.workflow_id):
                    artifact = CoverArtifact(
                        brief=proposal.brief,
                        image_acceptance_status="image_deferred",
                    )
                else:
                    artifact = await self.cover_generator.materialize(
                        definition=definition,
                        proposal=proposal,
                        binding=binding.image_execution,
                        proposal_operation_key=operation_key,
                        generation_attempt=_generation_attempt(state, stage),
                    )
            _validate_stage_references(
                self.artifact_store,
                definition,
                state,
                stage,
                artifact,
            )
            _validate_cover_assets(
                self.cover_assets,
                definition.run_id,
                stage,
                artifact,
            )
        except Phase32CoverGenerationError as exc:
            raise Phase32DriverError(
                str(exc),
                code=exc.code,
                stage_id=stage.stage_id,
                retryable=exc.retryable,
            ) from exc
        except Phase32DriverError:
            self.provider_operations.reject_contract(
                run_id=definition.run_id,
                operation_key=operation_key,
                request_signature=request_signature,
                diagnostic=_artifact_rejection_diagnostic(receipt.diagnostic, stage.stage_id),
            )
            raise
        try:
            record = self.artifact_store.save_candidate(
                run_id=definition.run_id,
                creation_route_id=definition.creation_route_id,
                stage_id=stage.stage_id,
                artifact=artifact,
                source_operation_key=operation_key,
            )
            unit_ref = _unit_ref(stage, artifact)
            self.provider_operations.succeed(
                run_id=definition.run_id,
                operation_key=operation_key,
                request_signature=request_signature,
                result={"artifact_ref": record.artifact_ref, "unit_ref": unit_ref},
            )
        except Phase32DriverError:
            raise
        except Exception as exc:
            raise Phase32DriverError(
                f"Provider Artifact persistence failed for {definition.creation_route_id}/{stage.stage_id}"
            ) from exc
        return RouteStageCandidate(artifact_ref=record.artifact_ref, unit_ref=unit_ref)

    async def validate_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        candidate: RouteStageCandidate,
    ) -> None:
        if not candidate.artifact_ref:
            raise Phase32DriverError(f"Stage {stage.stage_id} has no candidate Artifact")
        try:
            record = self.artifact_store.read(definition.run_id, candidate.artifact_ref)
            if (
                record.creation_route_id != definition.creation_route_id
                or record.stage_id != stage.stage_id
                or record.status != "candidate"
                or record.artifact_kind != stage.artifact_kind
            ):
                raise ValueError("Candidate identity does not match the frozen stage")
            artifact = _parse_artifact(definition, stage, record.payload)
            _validate_stage_references(
                self.artifact_store,
                definition,
                state,
                stage,
                artifact,
            )
            _validate_cover_assets(
                self.cover_assets,
                definition.run_id,
                stage,
                artifact,
            )
            if _unit_ref(stage, artifact) != candidate.unit_ref:
                raise ValueError("Candidate unit ref does not match its Artifact")
        except Exception as exc:
            raise Phase32DriverError(
                f"Candidate validation failed for {definition.creation_route_id}/{stage.stage_id}"
            ) from exc

    async def commit_stage(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        candidate: RouteStageCandidate,
    ) -> str:
        if stage.stage_id != definition.route_contract.route_manifest.terminal_stage_id:
            if not candidate.artifact_ref:
                raise Phase32DriverError(f"Stage {stage.stage_id} has no candidate Artifact")
            try:
                if stage.stage_id == "cover":
                    record = self.artifact_store.read(
                        definition.run_id,
                        candidate.artifact_ref,
                    )
                    cover = CoverArtifact.model_validate(record.payload)
                    _validate_cover_assets(
                        self.cover_assets,
                        definition.run_id,
                        stage,
                        cover,
                    )
                    if (
                        cover.image_acceptance_status != "image_deferred"
                        and not cover.selected_asset_ref
                    ):
                        raise ValueError("Cover acceptance requires a selected asset")
                return self.artifact_store.commit_candidate(
                    run_id=definition.run_id,
                    creation_route_id=definition.creation_route_id,
                    stage_id=stage.stage_id,
                    candidate_ref=candidate.artifact_ref,
                ).artifact_ref
            except Exception as exc:
                raise Phase32DriverError(
                    f"Cannot commit Artifact for {definition.creation_route_id}/{stage.stage_id}"
                ) from exc
        try:
            delivery = _build_delivery_artifact(self.artifact_store, definition, state)
            record = self.artifact_store.save_deterministic(
                run_id=definition.run_id,
                creation_route_id=definition.creation_route_id,
                stage_id=stage.stage_id,
                artifact=delivery,
            )
            if isinstance(delivery, ScriptDeliveryArtifact):
                scene_records = [
                    self.artifact_store.read(definition.run_id, artifact_ref)
                    for artifact_ref in delivery.scene_version_refs
                ]
                self.exports.materialize_script_delivery(
                    definition.run_id,
                    record,
                    scene_records,
                )
            elif isinstance(delivery, BookDeliveryArtifact):
                chapter_records = [
                    self.artifact_store.read(definition.run_id, artifact_ref)
                    for artifact_ref in delivery.chapter_version_refs
                ]
                self.exports.materialize_book_delivery(
                    definition.run_id,
                    record,
                    chapter_records,
                    cover_asset=self.cover_assets.content(
                        definition.run_id,
                        delivery.cover_asset_ref,
                    ),
                )
            return record.artifact_ref
        except Phase32DriverError:
            raise
        except Exception as exc:
            raise Phase32DriverError(
                f"Cannot build deterministic delivery for {definition.creation_route_id}"
            ) from exc

    async def commit_writeback(
        self,
        *,
        definition: GraphRunDefinition,
        state: RouteRunStateSnapshot,
        stage: CompiledRouteStage,
        artifact_ref: str,
        unit_ref: str,
        retry: bool = False,
    ) -> "Phase32WritebackReceipt | None":
        if stage.stage_id not in {"script", "text"}:
            return None
        if self.writeback is None:
            return None
        return await self.writeback.commit(
            definition=definition,
            state=state,
            stage=stage,
            artifact_ref=artifact_ref,
            unit_ref=unit_ref,
            retry=retry,
        )

    def cancel_writeback(self, run_id: str, receipt_ref: str) -> None:
        if self.writeback is None:
            raise ValueError("Phase 32 writeback is not configured")
        self.writeback.cancel(run_id, receipt_ref)


def _provider_binding(
    definition: GraphRunDefinition,
    stage_id: str,
) -> tuple[str, Phase32StageProviderBindingSnapshot]:
    for entry in definition.provider_bindings_by_stage:
        if entry.stage_id == stage_id:
            try:
                return (
                    entry.binding.payload_digest,
                    Phase32StageProviderBindingSnapshot.model_validate(
                        entry.binding.payload
                    ),
                )
            except Exception as exc:
                raise Phase32DriverError(
                    f"Frozen Provider binding is invalid for stage {stage_id}"
                ) from exc
    raise Phase32DriverError(f"No frozen Provider binding for stage {stage_id}")


def _operation_key(
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    stage: CompiledRouteStage,
    direction: str,
) -> str:
    direction_digest = canonical_digest({"direction": direction.strip()})[:16]
    attempt = (
        state.stage_attempts.get(stage.stage_id, 0)
        + state.pending_decision_redraft_count
        + 1
    )
    if state.active_unit_ref:
        unit_digest = canonical_digest({"unit_ref": state.active_unit_ref})[:16]
        return (
            f"{definition.run_id}:{stage.stage_id}:{unit_digest}:"
            f"{attempt}:{direction_digest}"
        )
    return f"{definition.run_id}:{stage.stage_id}:{attempt}:{direction_digest}"


def _generation_attempt(
    state: RouteRunStateSnapshot,
    stage: CompiledRouteStage,
) -> int:
    return (
        state.stage_attempts.get(stage.stage_id, 0)
        + state.pending_decision_redraft_count
        + 1
    )


def _parse_artifact(
    definition: GraphRunDefinition,
    stage: CompiledRouteStage,
    payload: dict[str, Any],
) -> Phase32CoreArtifact:
    try:
        return validate_phase32_artifact_payload(definition, stage, payload)
    except Exception as exc:
        raise Phase32DriverError(
            f"Artifact payload does not satisfy {definition.creation_route_id}/{stage.stage_id}",
            code="provider_contract_failed",
            stage_id=stage.stage_id,
        ) from exc


def _validate_stage_references(
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    stage: CompiledRouteStage,
    artifact: Phase32CoreArtifact,
) -> None:
    try:
        validate_phase32_stage_references(
            artifact_store,
            definition,
            state.artifact_refs,
            stage.stage_id,
            artifact,
            active_unit_ref=state.active_unit_ref,
        )
    except Phase32StageReferenceError as exc:
        raise Phase32DriverError(
            str(exc),
            code="provider_contract_failed",
            stage_id=stage.stage_id,
        ) from exc


def _validate_cover_assets(
    cover_assets: CoverAssetStore,
    run_id: str,
    stage: CompiledRouteStage,
    artifact: Phase32CoreArtifact,
) -> None:
    if stage.stage_id != "cover" or not isinstance(artifact, CoverArtifact):
        return
    for candidate in artifact.candidates:
        try:
            cover_assets.read(run_id, candidate.asset_ref)
        except Exception as exc:
            raise Phase32DriverError(
                "Cover Artifact references an unavailable immutable asset",
                code="cover_asset_missing",
                stage_id=stage.stage_id,
            ) from exc


def _artifact_rejection_diagnostic(
    diagnostic: dict[str, Any],
    stage_id: str,
) -> dict[str, Any]:
    provider_code = str(diagnostic.get("code") or "")
    result = {
        **diagnostic,
        "code": "artifact_contract_rejected",
        "stage_id": stage_id,
    }
    if provider_code:
        result["provider_code"] = provider_code
    return result


def _unit_ref(stage: CompiledRouteStage, artifact: Phase32CoreArtifact) -> str:
    # Bounded-unit planning stages commit one aggregate root. Their child order
    # is author-editable and therefore cannot be used as the graph cursor.
    if stage.unitization != "sequential_units":
        return ""
    for field in ("unit_ref", "scene_ref", "chapter_ref", "window_ref", "volume_ref", "part_ref"):
        value = getattr(artifact, field, None)
        if isinstance(value, str) and value:
            return value
    for collection_name, ref_name in (
        ("units", "unit_ref"),
        ("scenes", "scene_ref"),
        ("windows", "window_ref"),
        ("volumes", "volume_ref"),
        ("parts", "part_ref"),
        ("characters", "subject_ref"),
    ):
        collection = getattr(artifact, collection_name, ())
        if collection:
            value = getattr(collection[0], ref_name, "")
            if value:
                return str(value)
    raise Phase32DriverError(f"Unitized stage {stage.stage_id} returned no unit ref")


def _raw_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("payload"), dict):
        return dict(value["payload"])
    payload = getattr(value, "payload", None)
    return dict(payload) if isinstance(payload, dict) else {}


def _public_transport_code(error: Exception) -> str:
    """Keep only stable public codes in durable receipts."""

    code = str(getattr(error, "code", "")).strip().lower()
    return (
        code
        if code in {
            "insufficient_balance",
            "authentication_failed",
            "endpoint_or_model_unavailable",
            "rate_limited",
            "timeout",
            "network_error",
            "service_unavailable",
        }
        else "provider_transport_failed"
    )


def _build_delivery_artifact(
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
) -> Phase32CoreArtifact:
    inputs = definition.inputs.payload
    author = str(inputs.get("author") or "")
    version_note = str(inputs.get("version_note") or "Phase 32 delivery")
    profile = definition.export_profile
    if definition.creation_route_id == "screenplay_sample":
        progress = state.sequential_progress("script")
        if progress is None or not progress.complete:
            raise Phase32DriverError(
                "Cannot export before every frozen Script scene is accepted"
            )
        version_refs = tuple(
            progress.committed_artifact_refs[scene_ref]
            for scene_ref in progress.ordered_unit_refs
        )
        for scene_ref, artifact_ref in zip(
            progress.ordered_unit_refs,
            version_refs,
            strict=True,
        ):
            record = artifact_store.read(definition.run_id, artifact_ref)
            if (
                record.status != "committed"
                or record.stage_id != "script"
                or record.creation_route_id != definition.creation_route_id
                or record.payload.get("scene_ref") != scene_ref
            ):
                raise Phase32DriverError(
                    "Script delivery references a non-accepted Scene version"
                )
        brief = _read_committed(artifact_store, definition, state, "brief")
        return ScriptDeliveryArtifact(
            title=str(brief["title"]),
            author=author,
            version_note=version_note,
            formats=(profile,),
            scene_refs=progress.ordered_unit_refs,
            scene_version_refs=version_refs,
        )
    cover = _read_committed(artifact_store, definition, state, "cover")
    brief = _read_committed(artifact_store, definition, state, "brief")
    selected_cover = cover.get("selected_asset_ref")
    if not selected_cover:
        raise Phase32DriverError("A selected cover asset is required before export")
    progress = state.sequential_progress("text")
    if progress is None or not progress.complete:
        raise Phase32DriverError(
            "Cannot export before every frozen prose unit is accepted"
        )
    chapter_refs = progress.ordered_unit_refs
    chapter_version_refs = tuple(
        progress.committed_artifact_refs[unit_ref] for unit_ref in chapter_refs
    )
    volume_refs: tuple[str, ...] = ()
    identity_field = "unit_ref"
    if definition.creation_route_id == "long_novel":
        volumes = _read_committed(artifact_store, definition, state, "volumes")
        volume_refs = tuple(
            str(item["volume_ref"]) for item in volumes.get("volumes", ())
        )
        identity_field = "chapter_ref"
    for unit_ref in chapter_refs:
        record = artifact_store.read(
            definition.run_id,
            progress.committed_artifact_refs[unit_ref],
        )
        if (
            record.status != "committed"
            or record.stage_id != "text"
            or record.creation_route_id != definition.creation_route_id
            or record.payload.get(identity_field) != unit_ref
        ):
            raise Phase32DriverError(
                "Book delivery references a non-accepted prose version"
            )
    return BookDeliveryArtifact(
        title=str(brief["title"]),
        author=author,
        version_note=version_note,
        formats=(profile,),
        chapter_refs=chapter_refs,
        chapter_version_refs=chapter_version_refs,
        volume_refs=volume_refs,
        cover_asset_ref=str(selected_cover),
    )


def _read_committed(
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    stage_id: str,
) -> dict[str, Any]:
    ref = state.artifact_refs.get(stage_id, "")
    if not ref:
        raise Phase32DriverError(f"Cannot export before {stage_id} is committed")
    record: Phase32ArtifactRecord = artifact_store.read(definition.run_id, ref)
    if record.status != "committed" or record.stage_id != stage_id:
        raise Phase32DriverError(f"Artifact {stage_id} is not committed")
    return record.payload


def _requires_text_operation_admission(definition: GraphRunDefinition) -> bool:
    return definition.scale_profile.payload.get("profile_kind") == "continuity_acceptance"


__all__ = [
    "Phase32DriverError",
    "Phase32RouteDriver",
]
