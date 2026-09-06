"""Durable idempotency records for amendment successor Runs."""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from novel_workflow.output_contracts.phase32_amendment_branch import (
    Phase32AmendmentBranchPlan,
    Phase32AmendmentBranchReceipt,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class Phase32AmendmentBranchStoreError(ValueError):
    code = "phase32_amendment_branch_store_invalid"


class Phase32AmendmentBranchIdempotencyConflict(Phase32AmendmentBranchStoreError):
    code = "phase32_amendment_branch_idempotency_conflict"


class Phase32AmendmentBranchStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def begin(self, plan: Phase32AmendmentBranchPlan) -> Phase32AmendmentBranchPlan:
        with self._lock:
            by_key = self.find_plan_by_idempotency_digest(
                plan.source_run_id,
                plan.idempotency_key_digest,
            )
            by_amendment = self.find_plan_for_amendment(
                plan.source_run_id,
                plan.amendment_id,
            )
            if (
                by_key is not None
                and by_amendment is not None
                and by_key.plan_id != by_amendment.plan_id
            ):
                raise Phase32AmendmentBranchIdempotencyConflict(
                    "Branch idempotency and amendment pointers resolve to different plans"
                )
            existing = by_key or by_amendment
            if existing is not None:
                if existing.command_digest != plan.command_digest:
                    raise Phase32AmendmentBranchIdempotencyConflict(
                        "Amendment already has another successor Run plan"
                    )
            else:
                path = self._plan_path(plan.source_run_id, plan.plan_id)
                if path.exists():
                    existing = self.read_plan(plan.source_run_id, plan.plan_id)
                    if existing != plan:
                        raise Phase32AmendmentBranchStoreError(
                            "Content-addressed amendment branch plan is not immutable"
                        )
                else:
                    atomic_write_json(path, plan.model_dump(mode="json"))
                    existing = plan
            atomic_write_json(
                self._amendment_plan_pointer_path(
                    plan.source_run_id,
                    plan.amendment_id,
                ),
                {"plan_id": existing.plan_id},
            )
            atomic_write_json(
                self._idempotency_path(plan.source_run_id, plan.idempotency_key_digest),
                {"plan_id": existing.plan_id},
            )
            return existing

    def read_plan(self, source_run_id: str, plan_id: str) -> Phase32AmendmentBranchPlan:
        try:
            return Phase32AmendmentBranchPlan.model_validate(
                read_json(self._plan_path(source_run_id, plan_id))
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32AmendmentBranchStoreError(
                "Malformed amendment branch plan"
            ) from exc

    def find_plan_by_idempotency_digest(
        self,
        source_run_id: str,
        key_digest: str,
    ) -> Phase32AmendmentBranchPlan | None:
        path = self._idempotency_path(source_run_id, key_digest)
        if not path.exists():
            return None
        try:
            pointer = read_json(path)
            return self.read_plan(source_run_id, str(pointer["plan_id"]))
        except Exception as exc:
            raise Phase32AmendmentBranchStoreError(
                "Malformed amendment branch idempotency pointer"
            ) from exc

    def find_plan_for_amendment(
        self,
        source_run_id: str,
        amendment_id: str,
    ) -> Phase32AmendmentBranchPlan | None:
        path = self._amendment_plan_pointer_path(source_run_id, amendment_id)
        if not path.exists():
            return None
        try:
            pointer = read_json(path)
            plan = self.read_plan(source_run_id, str(pointer["plan_id"]))
            if plan.amendment_id != amendment_id:
                raise ValueError("Amendment plan pointer identity mismatch")
            return plan
        except Exception as exc:
            raise Phase32AmendmentBranchStoreError(
                "Malformed amendment branch amendment pointer"
            ) from exc

    def complete(
        self,
        receipt: Phase32AmendmentBranchReceipt,
    ) -> Phase32AmendmentBranchReceipt:
        with self._lock:
            plan = self.find_plan_for_amendment(
                receipt.source_run_id,
                receipt.amendment_id,
            )
            if plan is None or plan.plan_id != receipt.plan_id:
                raise Phase32AmendmentBranchStoreError(
                    "Amendment branch receipt is not bound to its durable plan"
                )
            existing = self.receipt_for_amendment(
                receipt.source_run_id,
                receipt.amendment_id,
            )
            if existing is not None:
                if existing.model_copy(update={"branched_at": receipt.branched_at}) != receipt:
                    raise Phase32AmendmentBranchIdempotencyConflict(
                        "Amendment already resolved to another successor Run"
                    )
                return existing
            path = self._receipt_path(receipt.source_run_id, receipt.receipt_id)
            if path.exists():
                existing = self._read_receipt(receipt.source_run_id, receipt.receipt_id)
                if existing.model_copy(update={"branched_at": receipt.branched_at}) != receipt:
                    raise Phase32AmendmentBranchStoreError(
                        "Content-addressed amendment branch receipt is not immutable"
                    )
                receipt = existing
            else:
                atomic_write_json(path, receipt.model_dump(mode="json"))
            atomic_write_json(
                self._amendment_pointer_path(receipt.source_run_id, receipt.amendment_id),
                {"receipt_id": receipt.receipt_id},
            )
            return receipt

    def receipt_for_amendment(
        self,
        source_run_id: str,
        amendment_id: str,
    ) -> Phase32AmendmentBranchReceipt | None:
        path = self._amendment_pointer_path(source_run_id, amendment_id)
        if not path.exists():
            return None
        try:
            pointer = read_json(path)
            return self._read_receipt(source_run_id, str(pointer["receipt_id"]))
        except Exception as exc:
            raise Phase32AmendmentBranchStoreError(
                "Malformed amendment branch receipt pointer"
            ) from exc

    def _read_receipt(
        self,
        source_run_id: str,
        receipt_id: str,
    ) -> Phase32AmendmentBranchReceipt:
        return Phase32AmendmentBranchReceipt.model_validate(
            read_json(self._receipt_path(source_run_id, receipt_id))
        )

    def _run_dir(self, source_run_id: str) -> Path:
        return self.root / require_safe_id(source_run_id, label="source_run_id")

    def _plan_path(self, source_run_id: str, plan_id: str) -> Path:
        return self._run_dir(source_run_id) / "plans" / (
            require_safe_id(plan_id, label="plan_id") + ".json"
        )

    def _receipt_path(self, source_run_id: str, receipt_id: str) -> Path:
        return self._run_dir(source_run_id) / "receipts" / (
            require_safe_id(receipt_id, label="receipt_id") + ".json"
        )

    def _idempotency_path(self, source_run_id: str, digest: str) -> Path:
        return self._run_dir(source_run_id) / "idempotency" / f"{digest}.json"

    def _amendment_pointer_path(self, source_run_id: str, amendment_id: str) -> Path:
        return self._run_dir(source_run_id) / "resolved" / (
            require_safe_id(amendment_id, label="amendment_id") + ".json"
        )

    def _amendment_plan_pointer_path(
        self,
        source_run_id: str,
        amendment_id: str,
    ) -> Path:
        return self._run_dir(source_run_id) / "amendments" / (
            require_safe_id(amendment_id, label="amendment_id") + ".json"
        )


__all__ = [
    "Phase32AmendmentBranchIdempotencyConflict",
    "Phase32AmendmentBranchStore",
    "Phase32AmendmentBranchStoreError",
]
