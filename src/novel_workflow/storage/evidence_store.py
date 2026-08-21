from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    run_id: str
    chapter_id: str
    chapter_version_id: str
    kind: Literal["fact", "character", "relationship", "foreshadow", "spine"]
    claim: str = Field(min_length=1, max_length=2000)
    spans: list[EvidenceSpan] = Field(min_length=1)
    created_at: str
    subject_id: str = ""
    property_key: str = ""
    value: str = ""
    epistemic_status: Literal[
        "fact", "rumour", "belief", "reveal", "refutation"
    ] = "fact"
    lifecycle: Literal["active", "supersedes", "resolves", "contradicted"] = "active"
    effective_from_chapter: int | None = Field(default=None, ge=1)
    effective_to_chapter: int | None = Field(default=None, ge=1)
    supersedes_fact_ids: list[str] = Field(default_factory=list, max_length=16)
    resolves_fact_ids: list[str] = Field(default_factory=list, max_length=16)


class EvidenceAttempt(BaseModel):
    """Durable recovery state for one accepted chapter Evidence operation."""

    model_config = ConfigDict(extra="forbid")

    operation_key: str = Field(min_length=1, max_length=1000)
    run_id: str
    chapter_id: str
    chapter_version_id: str
    chapter_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal[
        "pending", "succeeded", "retryable", "failed", "needs_action"
    ] = "pending"
    contract_error: str = Field(default="", max_length=2000)
    attempt: Literal[1, 2] = 1
    evidence_refs: list[str] = Field(default_factory=list, max_length=8)
    provider_receipt_ref: str = ""
    recovery_count: int = Field(default=0, ge=0)
    last_recovery_decision_id: str = ""
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def status_matches_payload(self) -> "EvidenceAttempt":
        if self.status == "succeeded" and not self.evidence_refs:
            raise ValueError("A succeeded Evidence attempt requires non-empty refs")
        if self.status != "succeeded" and self.evidence_refs:
            raise ValueError("Only a succeeded Evidence attempt may retain refs")
        if self.status in {"retryable", "failed", "needs_action"} and not self.contract_error:
            raise ValueError("A failed Evidence attempt requires a visible error")
        if self.status == "retryable" and self.attempt != 1:
            raise ValueError("Only the first Evidence attempt may be retryable")
        return self


class EvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(
        self,
        *,
        run_id: str,
        chapter_id: str,
        chapter_version_id: str,
        kind: Literal["fact", "character", "relationship", "foreshadow", "spine"],
        claim: str,
        spans: list[EvidenceSpan],
        subject_id: str = "",
        property_key: str = "",
        value: str = "",
        epistemic_status: Literal[
            "fact", "rumour", "belief", "reveal", "refutation"
        ] = "fact",
        lifecycle: Literal["active", "supersedes", "resolves", "contradicted"] = "active",
        effective_from_chapter: int | None = None,
        effective_to_chapter: int | None = None,
        supersedes_fact_ids: list[str] | None = None,
        resolves_fact_ids: list[str] | None = None,
    ) -> EvidenceRecord:
        signature = hashlib.sha256(
            json.dumps(
                {
                    "run_id": run_id,
                    "chapter_id": chapter_id,
                    "chapter_version_id": chapter_version_id,
                    "kind": kind,
                    "claim": claim,
                    "spans": [item.model_dump() for item in spans],
                    "subject_id": subject_id,
                    "property_key": property_key,
                    "value": value,
                    "epistemic_status": epistemic_status,
                    "lifecycle": lifecycle,
                    "effective_from_chapter": effective_from_chapter,
                    "effective_to_chapter": effective_to_chapter,
                    "supersedes_fact_ids": supersedes_fact_ids or [],
                    "resolves_fact_ids": resolves_fact_ids or [],
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        record = EvidenceRecord(
            evidence_id=f"evidence-{signature[:24]}",
            run_id=run_id,
            chapter_id=chapter_id,
            chapter_version_id=chapter_version_id,
            kind=kind,
            claim=claim,
            spans=spans,
            created_at=_now(),
            subject_id=subject_id,
            property_key=property_key,
            value=value,
            epistemic_status=epistemic_status,
            lifecycle=lifecycle,
            effective_from_chapter=effective_from_chapter,
            effective_to_chapter=effective_to_chapter,
            supersedes_fact_ids=supersedes_fact_ids or [],
            resolves_fact_ids=resolves_fact_ids or [],
        )
        path = self._path(run_id, record.evidence_id)
        with self._lock:
            if path.exists():
                return EvidenceRecord.model_validate(read_json(path))
            atomic_write_json(path, record.model_dump(mode="json"))
        return record

    def read(self, run_id: str, evidence_id: str) -> EvidenceRecord:
        return EvidenceRecord.model_validate(read_json(self._path(run_id, evidence_id)))

    def list(self, run_id: str) -> list[EvidenceRecord]:
        require_safe_id(run_id, label="run_id")
        return [EvidenceRecord.model_validate(read_json(path)) for path in sorted((self.root / run_id).glob("*.json"))]

    def begin_attempt(
        self,
        *,
        operation_key: str,
        run_id: str,
        chapter_id: str,
        chapter_version_id: str,
        chapter_content_hash: str,
    ) -> EvidenceAttempt:
        path = self._attempt_path(run_id, operation_key)
        with self._lock:
            if path.exists():
                existing = EvidenceAttempt.model_validate(read_json(path))
                expected = (
                    run_id,
                    chapter_id,
                    chapter_version_id,
                    chapter_content_hash,
                )
                actual = (
                    existing.run_id,
                    existing.chapter_id,
                    existing.chapter_version_id,
                    existing.chapter_content_hash,
                )
                if actual != expected:
                    raise ValueError(
                        "Evidence operation identity was reused for different accepted prose"
                    )
                return existing
            now = _now()
            attempt = EvidenceAttempt(
                operation_key=operation_key,
                run_id=run_id,
                chapter_id=chapter_id,
                chapter_version_id=chapter_version_id,
                chapter_content_hash=chapter_content_hash,
                created_at=now,
                updated_at=now,
            )
            atomic_write_json(path, attempt.model_dump(mode="json"))
            return attempt

    def update_attempt(
        self,
        run_id: str,
        operation_key: str,
        *,
        status: Literal[
            "pending", "succeeded", "retryable", "failed", "needs_action"
        ],
        attempt: Literal[1, 2],
        contract_error: str = "",
        evidence_refs: list[str] | None = None,
        provider_receipt_ref: str = "",
    ) -> EvidenceAttempt:
        path = self._attempt_path(run_id, operation_key)
        with self._lock:
            current = EvidenceAttempt.model_validate(read_json(path))
            updated = current.model_copy(
                update={
                    "status": status,
                    "attempt": attempt,
                    "contract_error": contract_error.strip(),
                    "evidence_refs": list(evidence_refs or []),
                    "provider_receipt_ref": provider_receipt_ref,
                    "updated_at": _now(),
                }
            )
            updated = EvidenceAttempt.model_validate(updated.model_dump(mode="json"))
            atomic_write_json(path, updated.model_dump(mode="json"))
            return updated

    def begin_recovery(
        self,
        run_id: str,
        operation_key: str,
        *,
        decision_id: str,
    ) -> EvidenceAttempt:
        path = self._attempt_path(run_id, operation_key)
        with self._lock:
            current = EvidenceAttempt.model_validate(read_json(path))
            if current.last_recovery_decision_id == decision_id:
                return current
            if current.status != "needs_action":
                raise ValueError("Evidence recovery requires a needs_action attempt")
            updated = current.model_copy(
                update={
                    "status": "pending",
                    "attempt": 1,
                    "contract_error": "",
                    "evidence_refs": [],
                    "provider_receipt_ref": "",
                    "recovery_count": current.recovery_count + 1,
                    "last_recovery_decision_id": decision_id,
                    "updated_at": _now(),
                }
            )
            updated = EvidenceAttempt.model_validate(updated.model_dump(mode="json"))
            atomic_write_json(path, updated.model_dump(mode="json"))
            return updated

    def read_attempt(self, run_id: str, operation_key: str) -> EvidenceAttempt:
        return EvidenceAttempt.model_validate(
            read_json(self._attempt_path(run_id, operation_key))
        )

    def list_attempts(self, run_id: str) -> list[EvidenceAttempt]:
        require_safe_id(run_id, label="run_id")
        directory = self.root / run_id / "attempts"
        if not directory.exists():
            return []
        return [
            EvidenceAttempt.model_validate(read_json(path))
            for path in sorted(directory.glob("*.json"))
        ]

    def _path(self, run_id: str, evidence_id: str) -> Path:
        require_safe_id(run_id, label="run_id")
        require_safe_id(evidence_id, label="evidence_id")
        return self.root / run_id / f"{evidence_id}.json"

    def _attempt_path(self, run_id: str, operation_key: str) -> Path:
        require_safe_id(run_id, label="run_id")
        digest = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()
        return self.root / run_id / "attempts" / f"{digest}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
