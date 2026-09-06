"""Export and cold-verify private exact-12 Phase 32 release evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.memory.phase32_wiki_projection import Phase32WikiProjectionStore
from novel_workflow.orchestration.phase32_release_evidence_validation import (
    build_release_summary,
)
from novel_workflow.output_contracts.phase32_release_evidence import (
    Phase32ContinuityEvidenceBundle,
    build_phase32_continuity_evidence_bundle,
)
from novel_workflow.providers.phase32_contract import (
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_evidence_store import Phase32EvidenceStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceipt,
    Phase32ProviderOperationStore,
)
from novel_workflow.storage.phase32_provider_attempt_ledger import (
    public_transport_error_code,
)
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessStore,
)
from novel_workflow.storage.phase32_quality_report_store import Phase32QualityReportStore
from novel_workflow.storage.phase32_release_evidence_store import (
    Phase32ReleaseEvidenceStore,
)
from novel_workflow.storage.phase32_run_budget_store import Phase32RunBudgetStore
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.phase32_writeback_outbox import Phase32WritebackOutbox
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition


Clock = Callable[[], datetime]


class Phase32ReleaseEvidenceError(ValueError):
    code = "phase32_release_evidence_invalid"

    def __init__(self, issue_codes: tuple[str, ...]) -> None:
        self.issue_codes = issue_codes
        super().__init__(
            "Phase 32 release evidence is blocked: " + ", ".join(issue_codes)
        )


@dataclass(frozen=True, slots=True)
class Phase32ReleaseEvidenceVerification:
    bundle: Phase32ContinuityEvidenceBundle
    issue_codes: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.issue_codes


class Phase32ReleaseEvidenceService:
    """Project one redacted bundle from the existing production authorities."""

    def __init__(
        self,
        *,
        repository: Phase32RunRepository,
        readiness: Phase32ProviderReadinessStore,
        budgets: Phase32RunBudgetStore,
        provider_inputs: Phase32ProviderInputStore,
        provider_operations: Phase32ProviderOperationStore,
        artifacts: Phase32ArtifactStore,
        evidence: Phase32EvidenceStore,
        outbox: Phase32WritebackOutbox,
        canon: Phase32CanonStore,
        wiki: Phase32WikiProjectionStore,
        quality_reports: Phase32QualityReportStore,
        bundles: Phase32ReleaseEvidenceStore,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.readiness = readiness
        self.budgets = budgets
        self.provider_inputs = provider_inputs
        self.provider_operations = provider_operations
        self.artifacts = artifacts
        self.evidence = evidence
        self.outbox = outbox
        self.canon = canon
        self.wiki = wiki
        self.quality_reports = quality_reports
        self.bundles = bundles
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def export(self, run_id: str) -> Phase32ContinuityEvidenceBundle:
        generated_at = _utc(self.clock()).isoformat()
        payload = self._snapshot(run_id, generated_at=generated_at)
        return self.bundles.write(build_phase32_continuity_evidence_bundle(payload))

    def verify(
        self,
        run_id: str,
        bundle_ref: str,
    ) -> Phase32ReleaseEvidenceVerification:
        bundle = self.bundles.read(run_id, bundle_ref)
        expected = build_phase32_continuity_evidence_bundle(
            self._snapshot(run_id, generated_at=bundle.generated_at)
        )
        issues = list(bundle.summary.issue_codes)
        if bundle.model_dump(mode="json") != expected.model_dump(mode="json"):
            issues.append("evidence_authority_drift")
        return Phase32ReleaseEvidenceVerification(
            bundle=bundle,
            issue_codes=tuple(dict.fromkeys(issues)),
        )

    def require_valid(
        self,
        run_id: str,
        bundle_ref: str,
    ) -> Phase32ContinuityEvidenceBundle:
        verification = self.verify(run_id, bundle_ref)
        if not verification.valid:
            raise Phase32ReleaseEvidenceError(verification.issue_codes)
        return verification.bundle

    def _snapshot(self, run_id: str, *, generated_at: str) -> dict[str, Any]:
        record = self.repository.read(run_id)
        definition = record.definition
        readiness = tuple(
            item.model_dump(mode="json") for item in self.readiness.list(run_id)
        )
        try:
            authorization_model = self.budgets.read_authorization(run_id)
        except FileNotFoundError:
            authorization_model = None
        admissions_models = tuple(self.budgets.list_admissions(run_id))
        receipts_models = tuple(self.provider_operations.list(run_id))
        events_models = tuple(self.repository.events(run_id))
        artifacts_models = tuple(self.artifacts.list(run_id))
        evidence_models = tuple(self.evidence.list(run_id))
        writeback_models = tuple(self.outbox.list(run_id))
        canon_models = tuple(self.canon.transactions(run_id))
        wiki_models = tuple(self.wiki.list(run_id))
        quality_models = tuple(self.quality_reports.list(run_id))

        summary = build_release_summary(
            definition=definition,
            record=record,
            generated_at=generated_at,
            readiness_store=self.readiness,
            authorization=authorization_model,
            admissions=admissions_models,
            receipts=receipts_models,
            provider_inputs=self.provider_inputs,
            events=events_models,
            artifacts=artifacts_models,
            evidence=evidence_models,
            writebacks=writeback_models,
            canon=canon_models,
            wiki=wiki_models,
            quality_reports=quality_models,
        )
        return {
            "format_version": "phase32-continuity-evidence.v1",
            "generated_at": generated_at,
            "run_id": run_id,
            "definition_digest": definition.definition_digest,
            "definition": _definition_projection(definition),
            "readiness_admissions": readiness,
            "budget_authorization": (
                authorization_model.model_dump(mode="json")
                if authorization_model is not None
                else None
            ),
            "budget_admissions": tuple(
                item.model_dump(mode="json") for item in admissions_models
            ),
            "transport_attempt_events": tuple(
                event.model_dump(mode="json")
                for receipt in receipts_models
                for event in receipt.transport_attempt_events
            ),
            "provider_receipts": tuple(
                _receipt_projection(item) for item in receipts_models
            ),
            "run_events": tuple(_event_projection(item) for item in events_models),
            "artifacts": tuple(
                {
                    "artifact_ref": item.artifact_ref,
                    "run_id": item.run_id,
                    "stage_id": item.stage_id,
                    "artifact_kind": item.artifact_kind,
                    "status": item.status,
                    "payload_digest": item.payload_digest,
                    "source_operation_key": item.source_operation_key,
                    "record_digest": canonical_digest(item.model_dump(mode="json")),
                }
                for item in artifacts_models
            ),
            "evidence_records": tuple(
                {
                    "evidence_ref": item.evidence_ref,
                    "run_id": item.run_id,
                    "stage_id": item.stage_id,
                    "unit_ref": item.unit_ref,
                    "source_artifact_ref": item.source_artifact_ref,
                    "source_payload_digest": item.source_payload_digest,
                    "source_text_digest": item.source_text_digest,
                    "kind": item.kind,
                    "record_digest": canonical_digest(item.model_dump(mode="json")),
                }
                for item in evidence_models
            ),
            "writebacks": tuple(
                _writeback_projection(item.receipt) for item in writeback_models
            ),
            "canon_transactions": tuple(
                {
                    "transaction_ref": item.transaction_ref,
                    "run_id": item.run_id,
                    "source_artifact_ref": item.source_artifact_ref,
                    "fact_refs": tuple(fact.fact_ref for fact in item.facts),
                    "transaction_digest": canonical_digest(item.model_dump(mode="json")),
                }
                for item in canon_models
            ),
            "wiki_transactions": tuple(
                {
                    "transaction_ref": item.transaction_ref,
                    "source_artifact_ref": item.source_artifact_ref,
                    "fact_refs": tuple(fact.fact_ref for fact in item.facts),
                    "projection_digest": canonical_digest(item.model_dump(mode="json")),
                }
                for item in wiki_models
            ),
            "quality_reports": tuple(
                {
                    "report_ref": item.report_ref,
                    "report_digest": item.report_digest,
                    "run_id": item.run_id,
                    "sequence": item.sequence,
                    "evidence_scope": item.evidence_scope,
                    "source_digest": item.source_snapshot.source_digest,
                    "accepted_prefix_complete": item.source_snapshot.accepted_prefix_complete,
                    "structure_contract": item.structure_contract,
                    "deterministic_blocker_count": len(item.deterministic_blockers),
                    "literary_warning_count": len(item.literary_warnings),
                    "cold_read_outcome": item.cold_read.outcome,
                }
                for item in quality_models
            ),
            "summary": summary.model_dump(mode="json"),
        }


def _definition_projection(definition: GraphRunDefinition) -> dict[str, Any]:
    bindings = []
    for frozen in definition.provider_bindings_by_stage:
        binding = Phase32StageProviderBindingSnapshot.model_validate(frozen.binding.payload)
        execution = binding.execution
        bindings.append(
            {
                "stage_id": frozen.stage_id,
                "binding_digest": frozen.binding.payload_digest,
                "provider_profile_id": execution.provider_profile_id,
                "provider_template_id": execution.provider_template_id,
                "model_id": execution.model_id,
                "pricing_snapshot_ref": execution.pricing_snapshot.snapshot_ref,
                "image_execution_bound": binding.image_execution is not None,
            }
        )
    return {
        "architecture_version": definition.architecture_version,
        "run_id": definition.run_id,
        "project_id": definition.project_id,
        "workflow_id": definition.workflow_id,
        "workflow_revision": definition.workflow_revision,
        "workflow_digest": definition.workflow_digest,
        "creation_route_id": definition.creation_route_id,
        "route_revision": definition.route_revision,
        "route_manifest_digest": definition.route_contract.route_manifest_digest,
        "review_policy_digest": definition.route_contract.review_policy_digest,
        "stage_manifest": tuple(
            {
                "stage_id": stage.stage_id,
                "artifact_kind": stage.artifact_kind,
                "unitization": stage.unitization,
            }
            for stage in definition.route_contract.route_manifest.stages
        ),
        "scale_contract_id": definition.scale_profile.contract_id,
        "scale_payload_digest": definition.scale_profile.payload_digest,
        "profile_kind": definition.scale_profile.payload.get("profile_kind"),
        "inputs_contract_id": definition.inputs.contract_id,
        "inputs_payload_digest": definition.inputs.payload_digest,
        "provider_bindings": tuple(bindings),
        "export_profile": definition.export_profile,
        "created_at": definition.created_at,
        "definition_digest": definition.definition_digest,
    }


def _receipt_projection(receipt: Phase32ProviderOperationReceipt) -> dict[str, Any]:
    raw_diagnostic_code = receipt.diagnostic.get("code")
    diagnostic_code = (
        public_transport_error_code(raw_diagnostic_code)
        if raw_diagnostic_code
        else ""
    )
    return {
        "receipt_ref": receipt.receipt_ref,
        "run_id": receipt.run_id,
        "operation_key": receipt.operation_key,
        "stage_id": receipt.stage_id,
        "request_signature": receipt.request_signature,
        "provider_input_ref": receipt.provider_input_ref,
        "provider_profile_id": receipt.provider_profile_id,
        "provider_template_id": receipt.provider_template_id,
        "model_id": receipt.model_id,
        "pricing_snapshot_ref": receipt.pricing_snapshot_ref,
        "transport_attempts": receipt.transport_attempts,
        "transport_admission_refs": receipt.transport_admission_refs,
        "budget_definition_digest": receipt.budget_definition_digest,
        "budget_authorization_ref": receipt.budget_authorization_ref,
        "status": receipt.status,
        "usage": receipt.usage,
        "estimated_cost_usd": receipt.estimated_cost_usd,
        "cost_status": receipt.cost_status,
        "balance_status": receipt.balance_status,
        "diagnostic_code": diagnostic_code,
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
        "receipt_digest": canonical_digest(receipt.model_dump(mode="json")),
    }


def _event_projection(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "sequence": event.sequence,
        "occurred_at": event.occurred_at,
        "run_id": event.run_id,
        "type": event.type,
        "stage_id": event.stage_id,
        "unit_ref": event.unit_ref,
        "artifact_kind": event.artifact_kind,
        "node_id": event.node_id,
        "status": event.status,
        "payload_ref": event.payload_ref,
        "checkpoint_id": event.checkpoint_id,
        "event_digest": canonical_digest(event.model_dump(mode="json")),
    }


def _writeback_projection(receipt: Any) -> dict[str, Any]:
    return {
        "receipt_ref": receipt.receipt_ref,
        "run_id": receipt.run_id,
        "stage_id": receipt.stage_id,
        "unit_ref": receipt.unit_ref,
        "source_artifact_ref": receipt.source_artifact_ref,
        "source_payload_digest": receipt.source_payload_digest,
        "source_text_digest": receipt.source_text_digest,
        "status": receipt.status,
        "evidence_refs": receipt.evidence_refs,
        "fact_refs": receipt.fact_refs,
        "transaction_ref": receipt.transaction_ref,
        "provider_operation_refs": receipt.provider_operation_refs,
        "recovery_count": receipt.recovery_count,
        "error_code": (
            public_transport_error_code(receipt.error_code)
            if receipt.error_code
            else ""
        ),
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
        "receipt_digest": canonical_digest(receipt.model_dump(mode="json")),
    }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Release evidence clock must include a timezone")
    return value.astimezone(timezone.utc)


__all__ = [
    "Phase32ReleaseEvidenceError",
    "Phase32ReleaseEvidenceService",
    "Phase32ReleaseEvidenceVerification",
]
