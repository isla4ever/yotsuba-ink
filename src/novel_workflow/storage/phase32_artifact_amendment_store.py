"""Durable idempotency records for formal Phase 32 Artifact amendments."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from novel_workflow.output_contracts.phase32_artifact_amendment import (
    ArtifactImpactAnalysis,
    Phase32AmendmentApplyPlan,
    Phase32AmendmentApplyReceipt,
    Phase32ArtifactAmendment,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32ArtifactAmendmentStoreError(ValueError):
    code = "phase32_artifact_amendment_store_invalid"


class Phase32ArtifactAmendmentIdempotencyConflict(
    Phase32ArtifactAmendmentStoreError
):
    code = "phase32_artifact_amendment_idempotency_conflict"


class Phase32ArtifactAmendmentStore:
    """Keep amendment commands, impacts, plans and receipts immutable."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def save_amendment(
        self,
        amendment: Phase32ArtifactAmendment,
        impact: ArtifactImpactAnalysis,
    ) -> tuple[Phase32ArtifactAmendment, ArtifactImpactAnalysis]:
        if (
            amendment.run_id != impact.run_id
            or amendment.amendment_id != impact.amendment_id
            or amendment.impact_id != impact.impact_id
            or amendment.source_stage_id != impact.source_stage_id
            or amendment.proposed_payload_digest != impact.proposed_payload_digest
        ):
            raise Phase32ArtifactAmendmentStoreError(
                "Amendment and ImpactAnalysis identities differ"
            )
        with self._lock:
            existing_by_key = self.find_amendment_by_idempotency_digest(
                amendment.run_id,
                amendment.idempotency_key_digest,
            )
            if existing_by_key is not None:
                if existing_by_key.command_digest != amendment.command_digest:
                    raise Phase32ArtifactAmendmentIdempotencyConflict(
                        "Amendment idempotency key was already used for another command"
                    )
                return existing_by_key, self.read_impact(
                    amendment.run_id,
                    existing_by_key.impact_id,
                )

            amendment_path = self._amendment_path(
                amendment.run_id,
                amendment.amendment_id,
            )
            if amendment_path.exists():
                existing = self.read_amendment(
                    amendment.run_id,
                    amendment.amendment_id,
                )
                if existing.command_digest != amendment.command_digest:
                    raise Phase32ArtifactAmendmentStoreError(
                        "Content-addressed amendment identity is not immutable"
                    )
                stored_impact = self.read_impact(amendment.run_id, existing.impact_id)
            else:
                atomic_write_json(
                    self._impact_path(amendment.run_id, impact.impact_id),
                    impact.model_dump(mode="json"),
                )
                atomic_write_json(amendment_path, amendment.model_dump(mode="json"))
                existing = amendment
                stored_impact = impact
            atomic_write_json(
                self._amendment_idempotency_path(
                    amendment.run_id,
                    amendment.idempotency_key_digest,
                ),
                {"amendment_id": existing.amendment_id},
            )
            return existing, stored_impact

    def read_amendment(
        self,
        run_id: str,
        amendment_id: str,
    ) -> Phase32ArtifactAmendment:
        try:
            return Phase32ArtifactAmendment.model_validate(
                read_json(self._amendment_path(run_id, amendment_id))
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ArtifactAmendmentStoreError(
                "Malformed Phase 32 Artifact amendment record"
            ) from exc

    def read_impact(self, run_id: str, impact_id: str) -> ArtifactImpactAnalysis:
        try:
            return ArtifactImpactAnalysis.model_validate(
                read_json(self._impact_path(run_id, impact_id))
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ArtifactAmendmentStoreError(
                "Malformed Phase 32 amendment ImpactAnalysis"
            ) from exc

    def find_amendment_by_idempotency_digest(
        self,
        run_id: str,
        key_digest: str,
    ) -> Phase32ArtifactAmendment | None:
        path = self._amendment_idempotency_path(run_id, key_digest)
        if not path.exists():
            return None
        try:
            pointer = read_json(path)
            return self.read_amendment(run_id, str(pointer["amendment_id"]))
        except Exception as exc:
            raise Phase32ArtifactAmendmentStoreError(
                "Malformed amendment idempotency pointer"
            ) from exc

    def begin_apply(
        self,
        plan: Phase32AmendmentApplyPlan,
    ) -> Phase32AmendmentApplyPlan:
        with self._lock:
            existing_by_key = self.find_plan_by_idempotency_digest(
                plan.run_id,
                plan.idempotency_key_digest,
            )
            if existing_by_key is not None:
                if existing_by_key.command_digest != plan.command_digest:
                    raise Phase32ArtifactAmendmentIdempotencyConflict(
                        "Apply idempotency key was already used for another command"
                    )
                return existing_by_key
            path = self._plan_path(plan.run_id, plan.plan_id)
            if path.exists():
                existing = self.read_plan(plan.run_id, plan.plan_id)
                if existing.command_digest != plan.command_digest:
                    raise Phase32ArtifactAmendmentStoreError(
                        "Content-addressed amendment apply plan is not immutable"
                    )
            else:
                atomic_write_json(path, plan.model_dump(mode="json"))
                existing = plan
            atomic_write_json(
                self._apply_idempotency_path(
                    plan.run_id,
                    plan.idempotency_key_digest,
                ),
                {"plan_id": existing.plan_id},
            )
            return existing

    def read_plan(self, run_id: str, plan_id: str) -> Phase32AmendmentApplyPlan:
        try:
            return Phase32AmendmentApplyPlan.model_validate(
                read_json(self._plan_path(run_id, plan_id))
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32ArtifactAmendmentStoreError(
                "Malformed Phase 32 amendment apply plan"
            ) from exc

    def find_plan_by_idempotency_digest(
        self,
        run_id: str,
        key_digest: str,
    ) -> Phase32AmendmentApplyPlan | None:
        path = self._apply_idempotency_path(run_id, key_digest)
        if not path.exists():
            return None
        try:
            pointer = read_json(path)
            return self.read_plan(run_id, str(pointer["plan_id"]))
        except Exception as exc:
            raise Phase32ArtifactAmendmentStoreError(
                "Malformed amendment apply idempotency pointer"
            ) from exc

    def complete_apply(
        self,
        receipt: Phase32AmendmentApplyReceipt,
    ) -> Phase32AmendmentApplyReceipt:
        with self._lock:
            existing = self.receipt_for_amendment(
                receipt.run_id,
                receipt.amendment_id,
            )
            if existing is not None:
                if existing != receipt:
                    raise Phase32ArtifactAmendmentIdempotencyConflict(
                        "Amendment already has a different apply receipt"
                    )
                return existing
            receipt_path = self._receipt_path(receipt.run_id, receipt.receipt_id)
            if receipt_path.exists():
                try:
                    stored = Phase32AmendmentApplyReceipt.model_validate(
                        read_json(receipt_path)
                    )
                except Exception as exc:
                    raise Phase32ArtifactAmendmentStoreError(
                        "Malformed amendment apply receipt"
                    ) from exc
                if stored.model_dump(exclude={"applied_at"}) != receipt.model_dump(
                    exclude={"applied_at"}
                ):
                    raise Phase32ArtifactAmendmentIdempotencyConflict(
                        "Content-addressed amendment receipt is not immutable"
                    )
                receipt = stored
            else:
                atomic_write_json(receipt_path, receipt.model_dump(mode="json"))
            atomic_write_json(
                self._applied_pointer_path(receipt.run_id, receipt.amendment_id),
                {"receipt_id": receipt.receipt_id},
            )
            return receipt

    def receipt_for_amendment(
        self,
        run_id: str,
        amendment_id: str,
    ) -> Phase32AmendmentApplyReceipt | None:
        path = self._applied_pointer_path(run_id, amendment_id)
        if not path.exists():
            return None
        try:
            pointer = read_json(path)
            receipt_id = str(pointer["receipt_id"])
            return Phase32AmendmentApplyReceipt.model_validate(
                read_json(self._receipt_path(run_id, receipt_id))
            )
        except Exception as exc:
            raise Phase32ArtifactAmendmentStoreError(
                "Malformed amendment apply receipt pointer"
            ) from exc

    def _run_dir(self, run_id: str) -> Path:
        return self.root / require_safe_id(run_id, label="run_id")

    def _amendment_path(self, run_id: str, amendment_id: str) -> Path:
        return self._run_dir(run_id) / "amendments" / (
            require_safe_id(amendment_id, label="amendment_id") + ".json"
        )

    def _impact_path(self, run_id: str, impact_id: str) -> Path:
        return self._run_dir(run_id) / "impacts" / (
            require_safe_id(impact_id, label="impact_id") + ".json"
        )

    def _plan_path(self, run_id: str, plan_id: str) -> Path:
        return self._run_dir(run_id) / "plans" / (
            require_safe_id(plan_id, label="plan_id") + ".json"
        )

    def _receipt_path(self, run_id: str, receipt_id: str) -> Path:
        return self._run_dir(run_id) / "receipts" / (
            require_safe_id(receipt_id, label="receipt_id") + ".json"
        )

    def _amendment_idempotency_path(self, run_id: str, digest: str) -> Path:
        return self._run_dir(run_id) / "idempotency" / "create" / f"{digest}.json"

    def _apply_idempotency_path(self, run_id: str, digest: str) -> Path:
        return self._run_dir(run_id) / "idempotency" / "apply" / f"{digest}.json"

    def _applied_pointer_path(self, run_id: str, amendment_id: str) -> Path:
        return self._run_dir(run_id) / "applied" / (
            require_safe_id(amendment_id, label="amendment_id") + ".json"
        )


__all__ = [
    "Phase32ArtifactAmendmentIdempotencyConflict",
    "Phase32ArtifactAmendmentStore",
    "Phase32ArtifactAmendmentStoreError",
]
