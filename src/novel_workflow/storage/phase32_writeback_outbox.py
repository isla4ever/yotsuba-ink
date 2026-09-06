"""Durable Phase 32 writeback intent and Canon/Wiki reconciliation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.memory.phase32_wiki_projection import Phase32WikiProjectionStore
from novel_workflow.output_contracts.phase32_writeback import (
    Phase32CanonFact,
    Phase32WritebackReceipt,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.storage.phase32_evidence_store import phase32_now
from novel_workflow.workflows.route_specs import CreationRouteId


class Phase32WritebackIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt: Phase32WritebackReceipt
    facts: tuple[Phase32CanonFact, ...] = Field(default=(), max_length=8)


class Phase32WritebackOutbox:
    def __init__(
        self,
        root: Path,
        *,
        canon: Phase32CanonStore,
        wiki: Phase32WikiProjectionStore,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.canon = canon
        self.wiki = wiki
        self._lock = RLock()

    def begin(
        self,
        *,
        run_id: str,
        creation_route_id: CreationRouteId,
        stage_id: str,
        unit_ref: str,
        source_artifact_ref: str,
        source_payload_digest: str,
        source_text_digest: str,
    ) -> Phase32WritebackIntent:
        safe_run_id = require_safe_id(run_id, label="run_id")
        identity = "|".join(
            (safe_run_id, stage_id, unit_ref, source_artifact_ref, source_text_digest)
        )
        receipt_ref = f"p32-writeback-{hashlib.sha256(identity.encode()).hexdigest()}"
        now = phase32_now()
        receipt = Phase32WritebackReceipt(
            receipt_ref=receipt_ref,
            run_id=safe_run_id,
            creation_route_id=creation_route_id,
            stage_id=stage_id,
            unit_ref=unit_ref,
            source_artifact_ref=source_artifact_ref,
            source_payload_digest=source_payload_digest,
            source_text_digest=source_text_digest,
            status="pending_evidence",
            created_at=now,
            updated_at=now,
        )
        intent = Phase32WritebackIntent(receipt=receipt)
        path = self._path(safe_run_id, receipt_ref)
        with self._lock:
            if path.exists():
                existing = self._read_path(path)
                if _source_identity(existing.receipt) != _source_identity(receipt):
                    raise ValueError("Writeback receipt identity was reused")
                return existing
            atomic_write_json(path, intent.model_dump(mode="json"))
        return intent

    def attach_evidence(
        self,
        *,
        run_id: str,
        receipt_ref: str,
        evidence_refs: tuple[str, ...],
        facts: tuple[Phase32CanonFact, ...],
        provider_operation_refs: tuple[str, ...],
    ) -> Phase32WritebackIntent:
        with self._lock:
            current = self.read(run_id, receipt_ref)
            transaction_seed = {
                "source_artifact_ref": current.receipt.source_artifact_ref,
                "evidence_refs": evidence_refs,
                "fact_refs": tuple(fact.fact_ref for fact in facts),
            }
            from novel_workflow.workflows.frozen_route_contract import canonical_digest

            transaction_ref = f"p32-canon-{canonical_digest(transaction_seed)}"
            if current.receipt.transaction_ref:
                expected = (
                    current.receipt.evidence_refs,
                    current.receipt.fact_refs,
                    current.receipt.transaction_ref,
                    current.facts,
                )
                actual = (
                    evidence_refs,
                    tuple(fact.fact_ref for fact in facts),
                    transaction_ref,
                    facts,
                )
                if expected != actual:
                    raise ValueError("Attached writeback Evidence is immutable")
                return current
            updated = Phase32WritebackIntent(
                receipt=current.receipt.model_copy(
                    update={
                        "status": "queued",
                        "evidence_refs": evidence_refs,
                        "fact_refs": tuple(fact.fact_ref for fact in facts),
                        "transaction_ref": transaction_ref,
                        "provider_operation_refs": provider_operation_refs,
                        "error_code": "",
                        "error_message": "",
                        "updated_at": phase32_now(),
                    }
                ),
                facts=facts,
            )
            self._write(updated)
            return updated

    def flush(self, run_id: str, receipt_ref: str) -> Phase32WritebackIntent:
        with self._lock:
            current = self.read(run_id, receipt_ref)
            if current.receipt.status == "committed":
                return current
            if not current.receipt.transaction_ref:
                raise ValueError("Writeback cannot flush before Evidence is attached")
            if current.receipt.status == "cancelled":
                raise ValueError("Cancelled writeback cannot be flushed")
            try:
                self.canon.commit(
                    run_id=run_id,
                    transaction_ref=current.receipt.transaction_ref,
                    source_artifact_ref=current.receipt.source_artifact_ref,
                    facts=current.facts,
                )
                current = current.model_copy(
                    update={
                        "receipt": current.receipt.model_copy(
                            update={
                                "status": "canon_committed",
                                "error_code": "",
                                "error_message": "",
                                "updated_at": phase32_now(),
                            }
                        )
                    }
                )
                self._write(current)
                self.wiki.project(
                    run_id=run_id,
                    transaction_ref=current.receipt.transaction_ref,
                    source_artifact_ref=current.receipt.source_artifact_ref,
                    facts=current.facts,
                )
            except Exception as exc:
                failed = current.model_copy(
                    update={
                        "receipt": current.receipt.model_copy(
                            update={
                                "status": "needs_action",
                                "error_code": "writeback_commit_failed",
                                "error_message": str(exc)[:2_000],
                                "updated_at": phase32_now(),
                            }
                        )
                    }
                )
                self._write(failed)
                return failed
            committed = current.model_copy(
                update={
                    "receipt": current.receipt.model_copy(
                        update={
                            "status": "committed",
                            "error_code": "",
                            "error_message": "",
                            "updated_at": phase32_now(),
                        }
                    )
                }
            )
            self._write(committed)
            return committed

    def mark_needs_action(
        self,
        *,
        run_id: str,
        receipt_ref: str,
        error_code: str,
        error_message: str,
        provider_operation_refs: tuple[str, ...],
    ) -> Phase32WritebackIntent:
        with self._lock:
            current = self.read(run_id, receipt_ref)
            updated = current.model_copy(
                update={
                    "receipt": current.receipt.model_copy(
                        update={
                            "status": "needs_action",
                            "provider_operation_refs": provider_operation_refs,
                            "error_code": error_code,
                            "error_message": error_message[:2_000],
                            "updated_at": phase32_now(),
                        }
                    )
                }
            )
            self._write(updated)
            return updated

    def begin_recovery(self, run_id: str, receipt_ref: str) -> Phase32WritebackIntent:
        with self._lock:
            current = self.read(run_id, receipt_ref)
            if current.receipt.status != "needs_action":
                raise ValueError("Writeback recovery requires needs_action status")
            status = "queued" if current.receipt.transaction_ref else "pending_evidence"
            updated = current.model_copy(
                update={
                    "receipt": current.receipt.model_copy(
                        update={
                            "status": status,
                            "recovery_count": current.receipt.recovery_count + 1,
                            "error_code": "",
                            "error_message": "",
                            "updated_at": phase32_now(),
                        }
                    )
                }
            )
            self._write(updated)
            return updated

    def cancel(self, run_id: str, receipt_ref: str) -> Phase32WritebackIntent:
        with self._lock:
            current = self.read(run_id, receipt_ref)
            if current.receipt.status == "committed":
                return current
            updated = current.model_copy(
                update={
                    "receipt": current.receipt.model_copy(
                        update={
                            "status": "cancelled",
                            "error_code": current.receipt.error_code or "cancelled",
                            "error_message": current.receipt.error_message,
                            "updated_at": phase32_now(),
                        }
                    )
                }
            )
            self._write(updated)
            return updated

    def read(self, run_id: str, receipt_ref: str) -> Phase32WritebackIntent:
        return self._read_path(self._path(run_id, receipt_ref))

    def list(self, run_id: str) -> tuple[Phase32WritebackIntent, ...]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return ()
        return tuple(self._read_path(path) for path in sorted(directory.glob("*.json")))

    def pending(self, run_id: str) -> tuple[Phase32WritebackIntent, ...]:
        return tuple(
            item for item in self.list(run_id)
            if item.receipt.status not in {"committed", "cancelled"}
        )

    def _path(self, run_id: str, receipt_ref: str) -> Path:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(receipt_ref, label="receipt_ref")
        return self.root / safe_run_id / f"{safe_ref}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32WritebackIntent:
        return Phase32WritebackIntent.model_validate(read_json(path))

    def _write(self, intent: Phase32WritebackIntent) -> None:
        atomic_write_json(
            self._path(intent.receipt.run_id, intent.receipt.receipt_ref),
            intent.model_dump(mode="json"),
        )


def _source_identity(receipt: Phase32WritebackReceipt) -> tuple[str, ...]:
    return (
        receipt.run_id,
        receipt.creation_route_id,
        receipt.stage_id,
        receipt.unit_ref,
        receipt.source_artifact_ref,
        receipt.source_payload_digest,
        receipt.source_text_digest,
    )


__all__ = ["Phase32WritebackIntent", "Phase32WritebackOutbox"]
