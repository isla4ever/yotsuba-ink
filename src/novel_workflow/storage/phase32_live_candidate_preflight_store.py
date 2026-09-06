"""Immutable persistence for pricing attestations and zero-call preflight reports."""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover - production is POSIX; thread locking remains elsewhere.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32LiveCandidateAuthorization,
    Phase32LiveCandidateEnvironmentReport,
    Phase32PricingAttestation,
)


class Phase32LiveCandidatePreflightStoreError(ValueError):
    code = "phase32_live_candidate_preflight_store_invalid"


class Phase32LiveCandidatePreflightStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.attestations_root = root / "attestations"
        self.reports_root = root / "reports"
        self.authorizations_root = root / "authorizations"
        self.lock_root = root / ".locks"
        self.attestations_root.mkdir(parents=True, exist_ok=True)
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.authorizations_root.mkdir(parents=True, exist_ok=True)
        self.lock_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @contextmanager
    def pricing_guard(self, idempotency_key: str) -> Iterator[None]:
        require_safe_id(idempotency_key, label="idempotency_key")
        # All attestation keys mutate the same Provider profile. The process
        # lock must therefore follow the Provider authority, not the request.
        lock_name = hashlib.sha256(b"provider-deepseek-text").hexdigest()
        with self._lock:
            lock_path = self.lock_root / f"{lock_name}.lock"
            with lock_path.open("a+b") as handle:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def find_attestation(
        self,
        idempotency_key: str,
    ) -> Phase32PricingAttestation | None:
        safe_key = require_safe_id(idempotency_key, label="idempotency_key")
        path = self.attestations_root / f"{safe_key}.json"
        if not path.exists():
            return None
        return self._read_attestation(path, expected_key=safe_key)

    def write_attestation(
        self,
        attestation: Phase32PricingAttestation,
    ) -> Phase32PricingAttestation:
        safe_key = require_safe_id(
            attestation.idempotency_key,
            label="idempotency_key",
        )
        path = self.attestations_root / f"{safe_key}.json"
        if path.exists():
            existing = self._read_attestation(path, expected_key=safe_key)
            if existing != attestation:
                raise Phase32LiveCandidatePreflightStoreError(
                    "Pricing attestation idempotency key already has another payload"
                )
            return existing
        atomic_write_json(path, attestation.model_dump(mode="json"))
        return attestation

    def list_attestations(self) -> tuple[Phase32PricingAttestation, ...]:
        return tuple(
            sorted(
                (
                    self._read_attestation(path, expected_key=path.stem)
                    for path in self.attestations_root.glob("*.json")
                ),
                key=lambda item: (item.attested_at, item.attestation_ref),
            )
        )

    def latest_attestation(self) -> Phase32PricingAttestation | None:
        records = self.list_attestations()
        return records[-1] if records else None

    def write_report(
        self,
        report: Phase32LiveCandidateEnvironmentReport,
    ) -> Phase32LiveCandidateEnvironmentReport:
        path = self.reports_root / f"{report.report_ref}.json"
        with self._lock:
            if path.exists():
                existing = self._read_report(path)
                if existing != report:
                    raise Phase32LiveCandidatePreflightStoreError(
                        "Live candidate report identity is immutable"
                    )
                return existing
            atomic_write_json(path, report.model_dump(mode="json"))
        return report

    def read_report(self, report_ref: str) -> Phase32LiveCandidateEnvironmentReport:
        safe_ref = require_safe_id(report_ref, label="report_ref")
        if not safe_ref.startswith("p32-live-preflight-"):
            raise ValueError("Invalid live candidate report reference")
        path = self.reports_root / f"{safe_ref}.json"
        if not path.exists():
            raise FileNotFoundError(safe_ref)
        return self._read_report(path)

    def list_reports(self) -> tuple[Phase32LiveCandidateEnvironmentReport, ...]:
        return tuple(
            sorted(
                (self._read_report(path) for path in self.reports_root.glob("*.json")),
                key=lambda item: (item.observed_at, item.report_ref),
            )
        )

    def write_authorization(
        self,
        authorization: Phase32LiveCandidateAuthorization,
    ) -> Phase32LiveCandidateAuthorization:
        safe_run_id = require_safe_id(authorization.run_id, label="run_id")
        path = (
            self.authorizations_root
            / safe_run_id
            / f"{authorization.authorization_ref}.json"
        )
        with self._lock:
            if path.exists():
                existing = self._read_authorization(path)
                if existing != authorization:
                    raise Phase32LiveCandidatePreflightStoreError(
                        "Live candidate authorization identity is immutable"
                    )
                return existing
            atomic_write_json(path, authorization.model_dump(mode="json"))
        return authorization

    def list_authorizations(
        self,
        run_id: str,
    ) -> tuple[Phase32LiveCandidateAuthorization, ...]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.authorizations_root / safe_run_id
        if not directory.exists():
            return ()
        records = tuple(
            sorted(
                (
                    self._read_authorization(path)
                    for path in directory.glob("p32-live-candidate-auth-*.json")
                ),
                key=lambda item: (item.issued_at, item.authorization_ref),
            )
        )
        if any(item.run_id != safe_run_id for item in records):
            raise Phase32LiveCandidatePreflightStoreError(
                "Live candidate authorization belongs to another Run"
            )
        return records

    def latest_authorization(
        self,
        run_id: str,
    ) -> Phase32LiveCandidateAuthorization | None:
        records = self.list_authorizations(run_id)
        return records[-1] if records else None

    @staticmethod
    def _read_attestation(
        path: Path,
        *,
        expected_key: str,
    ) -> Phase32PricingAttestation:
        try:
            record = Phase32PricingAttestation.model_validate(read_json(path))
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32LiveCandidatePreflightStoreError(
                f"Malformed pricing attestation: {path.name}"
            ) from exc
        if record.idempotency_key != expected_key:
            raise Phase32LiveCandidatePreflightStoreError(
                "Pricing attestation storage identity differs"
            )
        return record

    @staticmethod
    def _read_report(path: Path) -> Phase32LiveCandidateEnvironmentReport:
        try:
            report = Phase32LiveCandidateEnvironmentReport.model_validate(
                read_json(path)
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32LiveCandidatePreflightStoreError(
                f"Malformed live candidate report: {path.name}"
            ) from exc
        if path.stem != report.report_ref:
            raise Phase32LiveCandidatePreflightStoreError(
                "Live candidate report storage identity differs"
            )
        return report

    @staticmethod
    def _read_authorization(path: Path) -> Phase32LiveCandidateAuthorization:
        try:
            authorization = Phase32LiveCandidateAuthorization.model_validate(
                read_json(path)
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32LiveCandidatePreflightStoreError(
                f"Malformed live candidate authorization: {path.name}"
            ) from exc
        if path.stem != authorization.authorization_ref:
            raise Phase32LiveCandidatePreflightStoreError(
                "Live candidate authorization storage identity differs"
            )
        return authorization


__all__ = [
    "Phase32LiveCandidatePreflightStore",
    "Phase32LiveCandidatePreflightStoreError",
]
