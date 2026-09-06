"""Formal versioned amendments for committed Phase 32 planning Artifacts."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from novel_workflow.orchestration.phase32_artifact_editing import (
    validate_phase32_artifact_payload,
)
from novel_workflow.orchestration.phase32_artifact_impact import (
    Phase32ArtifactImpactAnalyzer,
    is_phase32_planning_artifact_kind,
)
from novel_workflow.orchestration.phase32_stage_reference_validation import (
    Phase32StageReferenceError,
    validate_phase32_stage_references,
)
from novel_workflow.output_contracts.phase32_artifact_amendment import (
    AmendmentApplyScope,
    ArtifactImpactAnalysis,
    Phase32AmendmentApplyPlan,
    Phase32AmendmentApplyReceipt,
    Phase32ArtifactAmendment,
)
from novel_workflow.storage.phase32_artifact_amendment_store import (
    Phase32ArtifactAmendmentStore,
)
from novel_workflow.storage.phase32_artifact_store import (
    Phase32ArtifactRecord,
    Phase32ArtifactStore,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_event import create_route_run_event
from novel_workflow.storage.route_run_read_model import ArtifactRefProjection
from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32ArtifactAmendmentError(ValueError):
    code = "phase32_artifact_amendment_invalid"


class Phase32ArtifactAmendmentConflict(Phase32ArtifactAmendmentError):
    code = "phase32_artifact_amendment_conflict"


class Phase32ArtifactAmendmentBlocked(Phase32ArtifactAmendmentConflict):
    code = "phase32_artifact_amendment_references_blocked"


@dataclass(frozen=True, slots=True)
class Phase32AmendmentApplyOutcome:
    receipt: Phase32AmendmentApplyReceipt
    reused: bool


class Phase32ArtifactAmendmentService:
    """Derive impacts and advance one immutable Run authority on apply."""

    def __init__(
        self,
        repository: Phase32RunRepository,
        artifacts: Phase32ArtifactStore,
        amendments: Phase32ArtifactAmendmentStore,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.amendments = amendments
        self.impact_analyzer = Phase32ArtifactImpactAnalyzer(artifacts)
        self._lock = RLock()

    def create(
        self,
        run_id: str,
        stage_id: str,
        *,
        source_artifact_ref: str,
        proposed_payload: dict[str, Any],
        idempotency_key: str,
        author_note: str = "",
    ) -> tuple[Phase32ArtifactAmendment, ArtifactImpactAnalysis, bool]:
        key_digest = _idempotency_digest(idempotency_key)
        existing = self.amendments.find_amendment_by_idempotency_digest(
            run_id,
            key_digest,
        )
        if existing is not None:
            if (
                existing.source_stage_id != stage_id
                or existing.source_artifact_ref != source_artifact_ref
                or existing.author_note != author_note.strip()
                or existing.proposed_payload_digest
                != canonical_digest(proposed_payload)
            ):
                raise Phase32ArtifactAmendmentConflict(
                    "Amendment idempotency key was already used for another command"
                )
            return (
                existing,
                self.amendments.read_impact(run_id, existing.impact_id),
                True,
            )
        record = self.repository.read(run_id)
        stage = record.definition.stage(stage_id)
        source = self._current_planning_source(
            record,
            stage_id,
            source_artifact_ref,
        )
        validated = validate_phase32_artifact_payload(
            record.definition,
            stage,
            proposed_payload,
        )
        try:
            validate_phase32_stage_references(
                self.artifacts,
                record.definition,
                record.state.artifact_refs,
                stage_id,
                validated,
            )
        except Phase32StageReferenceError as exc:
            raise Phase32ArtifactAmendmentConflict(str(exc)) from exc
        payload = validated.model_dump(mode="json")
        proposed_digest = canonical_digest(payload)
        if proposed_digest == source.payload_digest:
            raise Phase32ArtifactAmendmentConflict(
                "Formal amendment must change the committed Artifact payload"
            )
        command = {
            "run_id": run_id,
            "creation_route_id": record.definition.creation_route_id,
            "route_revision": record.definition.route_revision,
            "definition_digest": record.definition.definition_digest,
            "source_stage_id": stage_id,
            "source_artifact_ref": source.artifact_ref,
            "source_payload_digest": source.payload_digest,
            "source_domain_revision": record.state.domain_revision,
            "proposed_payload_digest": proposed_digest,
            "author_note": author_note.strip(),
        }
        command_digest = canonical_digest(command)
        amendment_id = f"p32-amendment-{command_digest[:32]}"
        impact = self.impact_analyzer.analyze(
            record,
            amendment_id=amendment_id,
            source=source,
            proposed_payload=payload,
            proposed_payload_digest=proposed_digest,
        )
        amendment = Phase32ArtifactAmendment(
            amendment_id=amendment_id,
            command_digest=command_digest,
            idempotency_key_digest=key_digest,
            run_id=run_id,
            creation_route_id=record.definition.creation_route_id,
            route_revision=record.definition.route_revision,
            definition_digest=record.definition.definition_digest,
            source_stage_id=stage_id,
            artifact_kind=stage.artifact_kind,
            source_artifact_ref=source.artifact_ref,
            source_payload_digest=source.payload_digest,
            source_domain_revision=record.state.domain_revision,
            proposed_payload=payload,
            proposed_payload_digest=proposed_digest,
            impact_id=impact.impact_id,
            author_note=author_note.strip(),
            created_at=_now(),
        )
        stored, stored_impact = self.amendments.save_amendment(amendment, impact)
        return stored, stored_impact, False

    def impact(self, run_id: str, amendment_id: str) -> ArtifactImpactAnalysis:
        amendment = self.amendments.read_amendment(run_id, amendment_id)
        return self.amendments.read_impact(run_id, amendment.impact_id)

    def apply(
        self,
        run_id: str,
        amendment_id: str,
        *,
        scope: AmendmentApplyScope,
        idempotency_key: str,
    ) -> Phase32AmendmentApplyOutcome:
        with self._lock:
            existing_receipt = self.amendments.receipt_for_amendment(
                run_id,
                amendment_id,
            )
            if existing_receipt is not None:
                if existing_receipt.scope != scope:
                    raise Phase32ArtifactAmendmentConflict(
                        "Applied amendment cannot be replayed with another scope"
                    )
                return Phase32AmendmentApplyOutcome(existing_receipt, reused=True)

            amendment = self.amendments.read_amendment(run_id, amendment_id)
            impact = self.amendments.read_impact(run_id, amendment.impact_id)
            if impact.blocked_references:
                raise Phase32ArtifactAmendmentBlocked(
                    "Amendment removes stable refs used by committed or accepted Artifacts"
                )
            plan = self._apply_plan(
                amendment,
                impact,
                scope=scope,
                idempotency_key=idempotency_key,
            )
            plan = self.amendments.begin_apply(plan)
            if plan.amendment_id != amendment_id or plan.scope != scope:
                raise Phase32ArtifactAmendmentConflict(
                    "Apply idempotency key resolves to another amendment command"
                )

            current = self.repository.read(run_id)
            if current.read_model.active_amendment_id == amendment_id:
                receipt = self._recover_receipt(current, plan)
                return Phase32AmendmentApplyOutcome(receipt, reused=True)
            self._validate_apply_frontier(current, amendment)

            stage = current.definition.stage(amendment.source_stage_id)
            artifact = validate_phase32_artifact_payload(
                current.definition,
                stage,
                amendment.proposed_payload,
            )
            candidate = self.artifacts.save_candidate(
                run_id=run_id,
                creation_route_id=current.definition.creation_route_id,
                stage_id=stage.stage_id,
                artifact=artifact,
                source_operation_key=f"amendment:{amendment_id}",
            )
            committed = self.artifacts.commit_candidate(
                run_id=run_id,
                creation_route_id=current.definition.creation_route_id,
                stage_id=stage.stage_id,
                candidate_ref=candidate.artifact_ref,
            )
            if committed.artifact_ref != plan.expected_committed_artifact_ref:
                raise Phase32ArtifactAmendmentConflict(
                    "Committed amendment Artifact does not match its immutable apply plan"
                )
            event_id = f"amendment:{amendment_id}:applied"
            state, read_model = _project_apply(current, plan, committed, amendment_id)
            event = create_route_run_event(
                current.definition,
                event_id=event_id,
                sequence=len(self.repository.events(run_id)) + 1,
                occurred_at=_now(),
                type="artifact.committed",
                stage_id=stage.stage_id,
                artifact_kind=stage.artifact_kind,
                status="amended",
                payload={
                    "amendment_id": amendment_id,
                    "impact_id": impact.impact_id,
                    "scope": scope,
                    "previous_artifact_ref": amendment.source_artifact_ref,
                    "stale_stage_ids": list(plan.stale_stage_ids),
                    "historical_frozen_stage_ids": list(
                        plan.historical_frozen_stage_ids
                    ),
                },
                payload_ref=committed.artifact_ref,
            )
            projected = self.repository.commit_projection_with_event(
                run_id,
                state=state,
                read_model=read_model,
                event=event,
            )
            receipt = _receipt(projected, plan, event_id)
            return Phase32AmendmentApplyOutcome(
                self.amendments.complete_apply(receipt),
                reused=False,
            )

    def _current_planning_source(
        self,
        record: Phase32RunRecord,
        stage_id: str,
        source_artifact_ref: str,
    ) -> Phase32ArtifactRecord:
        stage = record.definition.stage(stage_id)
        if not is_phase32_planning_artifact_kind(stage.artifact_kind):
            raise Phase32ArtifactAmendmentConflict(
                "Formal amendment only accepts committed planning Artifacts"
            )
        if record.state.status not in {"completed", "failed"}:
            raise Phase32ArtifactAmendmentConflict(
                "Formal amendment requires a stable completed or failed Run frontier"
            )
        if record.read_model.pending_decisions:
            raise Phase32ArtifactAmendmentConflict(
                "Resolve the current stage decision before creating a formal amendment"
            )
        projection = record.read_model.artifact_refs.get(stage_id)
        if projection is None or projection.artifact_ref != source_artifact_ref:
            raise Phase32ArtifactAmendmentConflict(
                "Amendment source is not the current committed stage Artifact"
            )
        source = self.artifacts.read(record.definition.run_id, source_artifact_ref)
        if (
            source.status != "committed"
            or source.creation_route_id != record.definition.creation_route_id
            or source.stage_id != stage_id
            or source.artifact_kind != stage.artifact_kind
        ):
            raise Phase32ArtifactAmendmentConflict(
                "Amendment source does not match the frozen Run stage"
            )
        return source

    def _apply_plan(
        self,
        amendment: Phase32ArtifactAmendment,
        impact: ArtifactImpactAnalysis,
        *,
        scope: AmendmentApplyScope,
        idempotency_key: str,
    ) -> Phase32AmendmentApplyPlan:
        stale_stage_ids = (
            impact.affected_only_scope
            if scope == "affected_only"
            else impact.restart_from_stage_scope
        )
        if not stale_stage_ids:
            raise Phase32ArtifactAmendmentConflict(
                "Amendment has no downstream route frontier to repair"
            )
        historical_stage_ids = tuple(
            dict.fromkeys(target.stage_id for target in impact.historical_frozen)
        )
        expected_ref = (
            f"p32-{amendment.source_stage_id}-committed-"
            f"{amendment.proposed_payload_digest}"
        )
        command = {
            "run_id": amendment.run_id,
            "amendment_id": amendment.amendment_id,
            "impact_id": impact.impact_id,
            "scope": scope,
            "source_stage_id": amendment.source_stage_id,
            "source_artifact_ref": amendment.source_artifact_ref,
            "expected_committed_artifact_ref": expected_ref,
            "source_domain_revision": amendment.source_domain_revision,
            "stale_stage_ids": stale_stage_ids,
            "historical_frozen_stage_ids": historical_stage_ids,
            "active_stage_id": stale_stage_ids[0],
        }
        digest = canonical_digest(command)
        return Phase32AmendmentApplyPlan(
            plan_id=f"p32-amendment-plan-{digest[:32]}",
            command_digest=digest,
            idempotency_key_digest=_idempotency_digest(idempotency_key),
            created_at=_now(),
            **command,
        )

    @staticmethod
    def _validate_apply_frontier(
        current: Phase32RunRecord,
        amendment: Phase32ArtifactAmendment,
    ) -> None:
        if current.state.domain_revision != amendment.source_domain_revision:
            raise Phase32ArtifactAmendmentConflict(
                "Run domain revision changed after ImpactAnalysis"
            )
        projection = current.read_model.artifact_refs.get(amendment.source_stage_id)
        if (
            projection is None
            or projection.artifact_ref != amendment.source_artifact_ref
        ):
            raise Phase32ArtifactAmendmentConflict(
                "Current committed source changed after ImpactAnalysis"
            )
        if current.state.status not in {"completed", "failed"}:
            raise Phase32ArtifactAmendmentConflict(
                "Run frontier changed after ImpactAnalysis"
            )

    def _recover_receipt(
        self,
        current: Phase32RunRecord,
        plan: Phase32AmendmentApplyPlan,
    ) -> Phase32AmendmentApplyReceipt:
        projection = current.read_model.artifact_refs.get(plan.source_stage_id)
        event_id = f"amendment:{plan.amendment_id}:applied"
        if (
            current.state.domain_revision != plan.source_domain_revision + 1
            or projection is None
            or projection.artifact_ref != plan.expected_committed_artifact_ref
            or current.read_model.stale_stage_ids != plan.stale_stage_ids
            or not any(event.event_id == event_id for event in self.repository.events(plan.run_id))
        ):
            raise Phase32ArtifactAmendmentConflict(
                "Applied amendment projection does not match its durable plan"
            )
        return self.amendments.complete_apply(_receipt(current, plan, event_id))


def _project_apply(
    current: Phase32RunRecord,
    plan: Phase32AmendmentApplyPlan,
    committed: Phase32ArtifactRecord,
    amendment_id: str,
):
    stage_status = dict(current.state.stage_status)
    for stage_id in plan.stale_stage_ids:
        stage_status[stage_id] = "stale"
    state_artifacts = dict(current.state.artifact_refs)
    state_artifacts[plan.source_stage_id] = committed.artifact_ref
    state = current.state.model_copy(
        update={
            "status": "needs_action",
            "active_stage_id": plan.active_stage_id,
            "active_unit_ref": "",
            "stage_status": stage_status,
            "artifact_refs": state_artifacts,
            "active_amendment_id": amendment_id,
            "stale_stage_ids": plan.stale_stage_ids,
            "historical_frozen_stage_ids": plan.historical_frozen_stage_ids,
            "pending_decision_action": "",
            "pending_decision_redraft_count": 0,
            "domain_revision": current.state.domain_revision + 1,
        }
    ).validate_for_definition(current.definition)
    read_artifacts = dict(current.read_model.artifact_refs)
    read_artifacts[plan.source_stage_id] = ArtifactRefProjection(
        artifact_kind=committed.artifact_kind,
        artifact_ref=committed.artifact_ref,
    )
    read_model = current.read_model.model_copy(
        update={
            "status": "needs_action",
            "active_stage_id": plan.active_stage_id,
            "active_unit_ref": "",
            "stage_status": stage_status,
            "artifact_refs": read_artifacts,
            "pending_decisions": (),
            "active_amendment_id": amendment_id,
            "stale_stage_ids": plan.stale_stage_ids,
            "historical_frozen_stage_ids": plan.historical_frozen_stage_ids,
            "updated_at": _now(),
        }
    ).validate_for_definition(current.definition)
    return state, read_model


def _receipt(
    current: Phase32RunRecord,
    plan: Phase32AmendmentApplyPlan,
    event_id: str,
) -> Phase32AmendmentApplyReceipt:
    payload = {
        "plan_id": plan.plan_id,
        "run_id": plan.run_id,
        "amendment_id": plan.amendment_id,
        "scope": plan.scope,
        "previous_artifact_ref": plan.source_artifact_ref,
        "committed_artifact_ref": plan.expected_committed_artifact_ref,
        "domain_revision_before": plan.source_domain_revision,
        "domain_revision_after": current.state.domain_revision,
        "event_id": event_id,
    }
    digest = canonical_digest(payload)
    return Phase32AmendmentApplyReceipt(
        receipt_id=f"p32-amendment-receipt-{digest[:32]}",
        applied_at=_now(),
        **payload,
    )


def _idempotency_digest(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 240:
        raise Phase32ArtifactAmendmentError(
            "Amendment idempotency key must contain 1-240 characters"
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32AmendmentApplyOutcome",
    "Phase32ArtifactAmendmentBlocked",
    "Phase32ArtifactAmendmentConflict",
    "Phase32ArtifactAmendmentError",
    "Phase32ArtifactAmendmentService",
]
