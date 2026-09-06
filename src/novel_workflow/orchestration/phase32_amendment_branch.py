"""Resolve an applied amendment through one idempotent successor Run."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

from novel_workflow.output_contracts.phase32_amendment_branch import (
    Phase32AmendmentBranchPlan,
    Phase32AmendmentBranchReceipt,
)
from novel_workflow.output_contracts.phase32_artifact_amendment import (
    Phase32AmendmentApplyReceipt,
)
from novel_workflow.storage.phase32_amendment_branch_store import (
    Phase32AmendmentBranchStore,
)
from novel_workflow.storage.phase32_artifact_amendment_store import (
    Phase32ArtifactAmendmentStore,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_project_catalog_store import (
    Phase32ProjectCatalogStore,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_event import create_route_run_event
from novel_workflow.storage.route_run_read_model import (
    ArtifactRefProjection,
    initial_route_run_read_model,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.graph_run_definition import (
    GraphRunDefinition,
    freeze_graph_run_definition,
)


class Phase32AmendmentBranchError(ValueError):
    code = "phase32_amendment_branch_invalid"


class Phase32AmendmentBranchConflict(Phase32AmendmentBranchError):
    code = "phase32_amendment_branch_conflict"


@dataclass(frozen=True, slots=True)
class Phase32AmendmentBranchOutcome:
    receipt: Phase32AmendmentBranchReceipt
    target: Phase32RunRecord
    reused: bool


class Phase32AmendmentBranchService:
    def __init__(
        self,
        repository: Phase32RunRepository,
        artifacts: Phase32ArtifactStore,
        amendments: Phase32ArtifactAmendmentStore,
        branches: Phase32AmendmentBranchStore,
        projects: Phase32ProjectCatalogStore,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.amendments = amendments
        self.branches = branches
        self.projects = projects
        self.clock = clock or _now
        self._lock = RLock()

    def branch(
        self,
        source_run_id: str,
        amendment_id: str,
        *,
        apply_receipt_id: str,
        source_domain_revision: int,
        idempotency_key: str,
    ) -> Phase32AmendmentBranchOutcome:
        key_digest = _key_digest(idempotency_key)
        command_digest = canonical_digest(
            {
                "source_run_id": source_run_id,
                "amendment_id": amendment_id,
                "apply_receipt_id": apply_receipt_id,
                "source_domain_revision": source_domain_revision,
                "idempotency_key_digest": key_digest,
            }
        )
        with self._lock:
            completed = self.branches.receipt_for_amendment(
                source_run_id,
                amendment_id,
            )
            if completed is not None:
                self._validate_replay(
                    completed,
                    apply_receipt_id=apply_receipt_id,
                    source_domain_revision=source_domain_revision,
                )
                target = self._validate_completed_receipt(completed)
                return Phase32AmendmentBranchOutcome(
                    completed,
                    target,
                    reused=True,
                )

            existing_plan = self.branches.find_plan_by_idempotency_digest(
                source_run_id,
                key_digest,
            )
            if existing_plan is None:
                plan = self._build_plan(
                    source_run_id,
                    amendment_id,
                    apply_receipt_id=apply_receipt_id,
                    source_domain_revision=source_domain_revision,
                    idempotency_key_digest=key_digest,
                    command_digest=command_digest,
                )
                plan = self.branches.begin(plan)
            else:
                if existing_plan.command_digest != command_digest:
                    raise Phase32AmendmentBranchConflict(
                        "Branch idempotency key resolves to another command"
                    )
                plan = existing_plan
            target = self._materialize(plan)
            receipt = self.branches.complete(self._receipt(plan))
            return Phase32AmendmentBranchOutcome(receipt, target, reused=False)

    def receipt(
        self,
        source_run_id: str,
        amendment_id: str,
    ) -> Phase32AmendmentBranchReceipt | None:
        receipt = self.branches.receipt_for_amendment(source_run_id, amendment_id)
        if receipt is not None:
            self._validate_completed_receipt(receipt)
        return receipt

    def apply_receipt(
        self,
        source_run_id: str,
        amendment_id: str,
    ) -> Phase32AmendmentApplyReceipt | None:
        """Restore the exact authority required by the branch command."""

        return self.amendments.receipt_for_amendment(source_run_id, amendment_id)

    def _build_plan(
        self,
        source_run_id: str,
        amendment_id: str,
        *,
        apply_receipt_id: str,
        source_domain_revision: int,
        idempotency_key_digest: str,
        command_digest: str,
    ) -> Phase32AmendmentBranchPlan:
        source = self.repository.read(source_run_id)
        if (
            source.state.status != "needs_action"
            or source.state.active_amendment_id != amendment_id
            or source.state.domain_revision != source_domain_revision
        ):
            raise Phase32AmendmentBranchConflict(
                "Branch command does not match the active stale amendment frontier"
            )
        if source.read_model.pending_decisions:
            raise Phase32AmendmentBranchConflict(
                "Resolve pending decisions before branching an amendment"
            )
        apply_receipt = self.amendments.receipt_for_amendment(
            source_run_id,
            amendment_id,
        )
        if apply_receipt is None or apply_receipt.receipt_id != apply_receipt_id:
            raise Phase32AmendmentBranchConflict(
                "Branch command does not match the amendment apply receipt"
            )
        apply_plan = self.amendments.read_plan(source_run_id, apply_receipt.plan_id)
        if (
            apply_plan.amendment_id != amendment_id
            or apply_receipt.domain_revision_after != source_domain_revision
            or apply_plan.stale_stage_ids != source.state.stale_stage_ids
        ):
            raise Phase32AmendmentBranchConflict(
                "Applied amendment plan drifted from the stale Run projection"
            )
        project = self.projects.get(source.definition.project_id)
        if project.run_ids[-1] != source_run_id:
            raise Phase32AmendmentBranchConflict(
                "Only the Project's latest Run can create an amendment successor"
            )

        frontier_stage_id = apply_plan.active_stage_id
        frontier_ordinal = source.definition.stage(frontier_stage_id).ordinal
        inherited_stage_ids = source.definition.stage_ids[:frontier_ordinal]
        inherited_refs: dict[str, str] = {}
        for stage_id in inherited_stage_ids:
            projection = source.read_model.artifact_refs.get(stage_id)
            if projection is None:
                raise Phase32AmendmentBranchConflict(
                    f"Amendment branch is missing committed predecessor {stage_id}"
                )
            inherited_refs[stage_id] = projection.artifact_ref
        target_run_id = f"run-amend-{command_digest[:24]}"
        created_at = self.clock()
        target_definition = _target_definition(
            source.definition,
            target_run_id=target_run_id,
            created_at=created_at,
        )
        values = {
            "command_digest": command_digest,
            "idempotency_key_digest": idempotency_key_digest,
            "source_run_id": source_run_id,
            "target_run_id": target_run_id,
            "project_id": source.definition.project_id,
            "amendment_id": amendment_id,
            "impact_id": apply_plan.impact_id,
            "apply_receipt_id": apply_receipt_id,
            "source_definition_digest": source.definition.definition_digest,
            "source_domain_revision": source_domain_revision,
            "frontier_stage_id": frontier_stage_id,
            "inherited_stage_ids": inherited_stage_ids,
            "inherited_artifact_refs": inherited_refs,
            "target_created_at": created_at,
            "target_definition_digest": target_definition.definition_digest,
        }
        digest = canonical_digest(values)
        return Phase32AmendmentBranchPlan(
            plan_id=f"p32-amendment-branch-plan-{digest[:32]}",
            **values,
        )

    def _materialize(self, plan: Phase32AmendmentBranchPlan) -> Phase32RunRecord:
        source = self.repository.read(plan.source_run_id)
        if source.definition.definition_digest != plan.source_definition_digest:
            raise Phase32AmendmentBranchConflict(
                "Amendment branch source definition has changed"
            )
        project = self.projects.get(plan.project_id)
        target_is_lineaged = _lineage_contains_edge(
            project.run_ids,
            plan.source_run_id,
            plan.target_run_id,
        )
        if not target_is_lineaged and project.run_ids[-1] != plan.source_run_id:
            raise Phase32AmendmentBranchConflict(
                "Project lineage advanced to another Run before branch recovery"
            )
        definition = _target_definition(
            source.definition,
            target_run_id=plan.target_run_id,
            created_at=plan.target_created_at,
        )
        if definition.definition_digest != plan.target_definition_digest:
            raise Phase32AmendmentBranchConflict(
                "Target Run definition does not match its immutable branch plan"
            )
        imported: dict[str, str] = {}
        for stage_id in plan.inherited_stage_ids:
            source_ref = plan.inherited_artifact_refs[stage_id]
            copied = self.artifacts.copy_committed(
                source_run_id=plan.source_run_id,
                target_run_id=plan.target_run_id,
                creation_route_id=definition.creation_route_id,
                stage_id=stage_id,
                source_artifact_ref=source_ref,
                source_operation_key=f"amendment-branch:{plan.plan_id}:{source_ref}",
            )
            imported[stage_id] = copied.artifact_ref
        target = self._create_target(definition, plan, imported)
        target_event_id = f"{plan.plan_id}:seeded"
        self._append_event_once(
            plan.target_run_id,
            target_event_id,
            lambda sequence: create_route_run_event(
                definition,
                event_id=target_event_id,
                sequence=sequence,
                occurred_at=plan.target_created_at,
                type="run.branched",
                status="amendment_branch_seeded",
                payload={
                    "source_run_id": plan.source_run_id,
                    "amendment_id": plan.amendment_id,
                    "apply_receipt_id": plan.apply_receipt_id,
                    "frontier_stage_id": plan.frontier_stage_id,
                    "imported_artifact_refs": imported,
                },
            ),
        )
        self.projects.append_run(
            plan.project_id,
            source_run_id=plan.source_run_id,
            target_run_id=plan.target_run_id,
        )
        self._append_source_event(source, plan)
        return target

    def _create_target(
        self,
        definition: GraphRunDefinition,
        plan: Phase32AmendmentBranchPlan,
        imported: dict[str, str],
    ) -> Phase32RunRecord:
        stage_status = {stage_id: "locked" for stage_id in definition.stage_ids}
        for stage_id in plan.inherited_stage_ids:
            stage_status[stage_id] = "completed"
        stage_status[plan.frontier_stage_id] = "available"
        state = initial_route_run_state(definition).model_copy(
            update={
                "active_stage_id": plan.frontier_stage_id,
                "stage_status": stage_status,
                "artifact_refs": imported,
            }
        ).validate_for_definition(definition)
        artifact_refs = {
            stage_id: ArtifactRefProjection(
                artifact_kind=definition.stage(stage_id).artifact_kind,
                artifact_ref=artifact_ref,
            )
            for stage_id, artifact_ref in imported.items()
        }
        read_model = initial_route_run_read_model(
            definition,
            updated_at=plan.target_created_at,
        ).model_copy(
            update={
                "active_stage_id": plan.frontier_stage_id,
                "stage_status": stage_status,
                "artifact_refs": artifact_refs,
            }
        ).validate_for_definition(definition)
        try:
            return self.repository.create(
                definition,
                state=state,
                read_model=read_model,
            )
        except FileExistsError:
            existing = self.repository.read(definition.run_id)
            if (
                existing.definition != definition
                or existing.state != state
                or existing.read_model != read_model
            ):
                raise Phase32AmendmentBranchConflict(
                    "Target Run exists outside the amendment branch recovery plan"
                )
            return existing

    def _append_source_event(
        self,
        source: Phase32RunRecord,
        plan: Phase32AmendmentBranchPlan,
    ) -> None:
        event_id = f"{plan.plan_id}:source"
        self._append_event_once(
            plan.source_run_id,
            event_id,
            lambda sequence: create_route_run_event(
                source.definition,
                event_id=event_id,
                sequence=sequence,
                occurred_at=plan.target_created_at,
                type="run.branched",
                status="amendment_branched",
                payload={
                    "amendment_id": plan.amendment_id,
                    "target_run_id": plan.target_run_id,
                    "frontier_stage_id": plan.frontier_stage_id,
                },
            ),
        )

    def _append_event_once(
        self,
        run_id: str,
        event_id: str,
        factory: Callable[[int], object],
    ) -> None:
        events = self.repository.events(run_id)
        if any(event.event_id == event_id for event in events):
            return
        self.repository.append_event(factory(len(events) + 1))

    def _receipt(self, plan: Phase32AmendmentBranchPlan) -> Phase32AmendmentBranchReceipt:
        values = {
            "plan_id": plan.plan_id,
            "source_run_id": plan.source_run_id,
            "target_run_id": plan.target_run_id,
            "project_id": plan.project_id,
            "amendment_id": plan.amendment_id,
            "apply_receipt_id": plan.apply_receipt_id,
            "source_domain_revision": plan.source_domain_revision,
            "target_definition_digest": plan.target_definition_digest,
            "frontier_stage_id": plan.frontier_stage_id,
            "imported_artifact_refs": plan.inherited_artifact_refs,
            "source_event_id": f"{plan.plan_id}:source",
            "target_event_id": f"{plan.plan_id}:seeded",
        }
        digest = canonical_digest(values)
        return Phase32AmendmentBranchReceipt(
            receipt_id=f"p32-amendment-branch-receipt-{digest[:32]}",
            branched_at=self.clock(),
            **values,
        )

    @staticmethod
    def _validate_replay(
        receipt: Phase32AmendmentBranchReceipt,
        *,
        apply_receipt_id: str,
        source_domain_revision: int,
    ) -> None:
        if (
            receipt.apply_receipt_id != apply_receipt_id
            or receipt.source_domain_revision != source_domain_revision
        ):
            raise Phase32AmendmentBranchConflict(
                "Applied amendment was already branched with another command"
            )

    def _validate_completed_receipt(
        self,
        receipt: Phase32AmendmentBranchReceipt,
    ) -> Phase32RunRecord:
        plan = self.branches.read_plan(receipt.source_run_id, receipt.plan_id)
        if (
            plan.amendment_id != receipt.amendment_id
            or plan.target_run_id != receipt.target_run_id
            or plan.target_definition_digest != receipt.target_definition_digest
            or plan.inherited_artifact_refs != receipt.imported_artifact_refs
        ):
            raise Phase32AmendmentBranchConflict(
                "Completed amendment branch receipt drifted from its durable plan"
            )
        target = self.repository.read(receipt.target_run_id)
        if (
            target.definition.project_id != receipt.project_id
            or target.definition.definition_digest != receipt.target_definition_digest
        ):
            raise Phase32AmendmentBranchConflict(
                "Completed amendment branch target does not match its receipt"
            )
        for stage_id, artifact_ref in receipt.imported_artifact_refs.items():
            copied = self.artifacts.read(receipt.target_run_id, artifact_ref)
            if copied.status != "committed" or copied.stage_id != stage_id:
                raise Phase32AmendmentBranchConflict(
                    "Completed amendment branch inherited Artifact is not committed"
                )
        project = self.projects.get(receipt.project_id)
        if not _lineage_contains_edge(
            project.run_ids,
            receipt.source_run_id,
            receipt.target_run_id,
        ):
            raise Phase32AmendmentBranchConflict(
                "Completed amendment branch is missing from Project lineage"
            )
        source_events = self.repository.events(receipt.source_run_id)
        target_events = self.repository.events(receipt.target_run_id)
        if not _has_branch_event(
            source_events,
            event_id=receipt.source_event_id,
            expected_payload={
                "amendment_id": receipt.amendment_id,
                "target_run_id": receipt.target_run_id,
                "frontier_stage_id": receipt.frontier_stage_id,
            },
        ) or not _has_branch_event(
            target_events,
            event_id=receipt.target_event_id,
            expected_payload={
                "source_run_id": receipt.source_run_id,
                "amendment_id": receipt.amendment_id,
                "apply_receipt_id": receipt.apply_receipt_id,
                "frontier_stage_id": receipt.frontier_stage_id,
                "imported_artifact_refs": receipt.imported_artifact_refs,
            },
        ):
            raise Phase32AmendmentBranchConflict(
                "Completed amendment branch provenance events are incomplete"
            )
        return target


def _target_definition(
    source: GraphRunDefinition,
    *,
    target_run_id: str,
    created_at: str,
) -> GraphRunDefinition:
    return freeze_graph_run_definition(
        run_id=target_run_id,
        project_id=source.project_id,
        workflow_id=source.workflow_id,
        workflow_revision=source.workflow_revision,
        workflow_digest=source.workflow_digest,
        route_contract=source.route_contract,
        scale_profile=source.scale_profile,
        inputs=source.inputs,
        provider_bindings_by_stage=source.provider_bindings_by_stage,
        export_profile=source.export_profile,
        created_at=created_at,
    )


def _key_digest(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise Phase32AmendmentBranchError("Branch idempotency key cannot be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _lineage_contains_edge(
    run_ids: tuple[str, ...],
    source_run_id: str,
    target_run_id: str,
) -> bool:
    try:
        target_index = run_ids.index(target_run_id)
    except ValueError:
        return False
    return target_index > 0 and run_ids[target_index - 1] == source_run_id


def _has_branch_event(
    events: list[object],
    *,
    event_id: str,
    expected_payload: dict[str, object],
) -> bool:
    for event in events:
        if getattr(event, "event_id", "") != event_id:
            continue
        if getattr(event, "type", "") != "run.branched":
            return False
        payload = getattr(event, "payload", None)
        return isinstance(payload, dict) and all(
            payload.get(key) == value for key, value in expected_payload.items()
        )
    return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Phase32AmendmentBranchConflict",
    "Phase32AmendmentBranchError",
    "Phase32AmendmentBranchOutcome",
    "Phase32AmendmentBranchService",
]
