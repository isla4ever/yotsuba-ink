"""Durable immutable Run budget authorizations and operation admissions."""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover - production is POSIX; the thread lock remains elsewhere.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.usage.phase32_run_budget import AdmissionTransaction
from novel_workflow.usage.phase32_run_budget_contract import (
    Phase32ProviderBudgetAdmission,
    Phase32RunBudgetAuthorization,
)


class Phase32RunBudgetStoreError(ValueError):
    code = "phase32_run_budget_store_invalid"


class Phase32RunBudgetStore:
    """Persist one authorization and one grant per operation transport attempt."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_root = root / ".locks"
        self.lock_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save_authorization(
        self,
        authorization: Phase32RunBudgetAuthorization,
    ) -> Phase32RunBudgetAuthorization:
        safe_run_id = require_safe_id(authorization.run_id, label="run_id")
        with self._run_guard(safe_run_id):
            path = self._authorization_path(safe_run_id)
            if path.exists():
                existing = self.read_authorization(safe_run_id)
                if existing != authorization:
                    raise Phase32RunBudgetStoreError(
                        "Run budget authorization is immutable"
                    )
                return existing
            atomic_write_json(path, authorization.model_dump(mode="json"))
            return authorization

    def read_authorization(self, run_id: str) -> Phase32RunBudgetAuthorization:
        safe_run_id = require_safe_id(run_id, label="run_id")
        try:
            authorization = Phase32RunBudgetAuthorization.model_validate(
                read_json(self._authorization_path(safe_run_id))
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32RunBudgetStoreError(
                f"Malformed Phase 32 Run budget authorization: {safe_run_id}"
            ) from exc
        if authorization.run_id != safe_run_id:
            raise Phase32RunBudgetStoreError(
                "Run budget authorization storage identity differs"
            )
        return authorization

    def find_admission(
        self,
        run_id: str,
        operation_key: str,
        transport_attempt: int = 1,
    ) -> Phase32ProviderBudgetAdmission | None:
        try:
            return self.read_admission(run_id, operation_key, transport_attempt)
        except FileNotFoundError:
            return None

    def read_admission(
        self,
        run_id: str,
        operation_key: str,
        transport_attempt: int = 1,
    ) -> Phase32ProviderBudgetAdmission:
        safe_run_id = require_safe_id(run_id, label="run_id")
        try:
            admission = Phase32ProviderBudgetAdmission.model_validate(
                read_json(
                    self._admission_path(
                        safe_run_id,
                        operation_key,
                        transport_attempt,
                    )
                )
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise Phase32RunBudgetStoreError(
                "Malformed Phase 32 Provider budget admission"
            ) from exc
        if (
            admission.run_id != safe_run_id
            or admission.operation_key != operation_key
            or admission.transport_attempt != transport_attempt
        ):
            raise Phase32RunBudgetStoreError(
                "Provider budget admission storage identity differs"
            )
        return admission

    def list_admissions(self, run_id: str) -> list[Phase32ProviderBudgetAdmission]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id / "admissions"
        if not directory.exists():
            return []
        admissions = [self._read_admission_path(path) for path in sorted(directory.glob("*.json"))]
        admission_keys: set[tuple[str, int]] = set()
        for admission in admissions:
            if admission.run_id != safe_run_id:
                raise Phase32RunBudgetStoreError(
                    "Provider budget admission belongs to another Run"
                )
            admission_key = (admission.operation_key, admission.transport_attempt)
            if admission_key in admission_keys:
                raise Phase32RunBudgetStoreError(
                    "Provider operation has duplicate budget admissions"
                )
            admission_keys.add(admission_key)
        return sorted(
            admissions,
            key=lambda item: (item.operation_key, item.transport_attempt),
        )

    def transact_admission(
        self,
        *,
        run_id: str,
        operation_key: str,
        transaction: AdmissionTransaction,
    ) -> tuple[Phase32ProviderBudgetAdmission, bool]:
        """Evaluate and persist one admission while serializing the whole Run."""

        safe_run_id = require_safe_id(run_id, label="run_id")
        _require_operation_key(operation_key)
        with self._run_guard(safe_run_id):
            authorization = self.read_authorization(safe_run_id)
            admissions = tuple(self.list_admissions(safe_run_id))
            proposed = transaction(authorization, admissions)
            if (
                proposed.run_id != safe_run_id
                or proposed.operation_key != operation_key
                or proposed.authorization_ref != authorization.authorization_ref
                or proposed.definition_digest != authorization.definition_digest
            ):
                raise Phase32RunBudgetStoreError(
                    "Budget admission transaction returned a mismatched record"
                )
            existing = next(
                (
                    admission
                    for admission in admissions
                    if admission.operation_key == operation_key
                    and admission.transport_attempt == proposed.transport_attempt
                ),
                None,
            )
            if existing is not None:
                if proposed != existing:
                    raise Phase32RunBudgetStoreError(
                        "Provider budget admission is immutable"
                    )
                return existing, True
            atomic_write_json(
                self._admission_path(
                    safe_run_id,
                    operation_key,
                    proposed.transport_attempt,
                ),
                proposed.model_dump(mode="json"),
            )
            return proposed, False

    def _authorization_path(self, run_id: str) -> Path:
        return self.root / run_id / "authorization.json"

    def _admission_path(
        self,
        run_id: str,
        operation_key: str,
        transport_attempt: int,
    ) -> Path:
        _require_operation_key(operation_key)
        if isinstance(transport_attempt, bool) or transport_attempt <= 0:
            raise ValueError("Provider transport attempt must be positive")
        identity = f"{operation_key}\0{transport_attempt}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.root / run_id / "admissions" / f"{digest}.json"

    @staticmethod
    def _read_admission_path(path: Path) -> Phase32ProviderBudgetAdmission:
        try:
            return Phase32ProviderBudgetAdmission.model_validate(read_json(path))
        except Exception as exc:
            raise Phase32RunBudgetStoreError(
                f"Malformed Phase 32 Provider budget admission: {path.name}"
            ) from exc

    @contextmanager
    def _run_guard(self, run_id: str) -> Iterator[None]:
        lock_name = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        lock_path = self.lock_root / f"{lock_name}.lock"
        with self._lock:
            with lock_path.open("a+", encoding="utf-8") as handle:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _require_operation_key(value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError("Provider operation key is required")


__all__ = ["Phase32RunBudgetStore", "Phase32RunBudgetStoreError"]
