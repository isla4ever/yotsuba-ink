"""Immutable persistence for redacted Phase 32 Provider readiness admissions."""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Literal

try:  # pragma: no cover - production runs on POSIX; thread lock is the fallback.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.providers.phase32_readiness_contract import (
    Phase32ProviderReadinessReport,
)
from novel_workflow.storage.atomic_json import atomic_write_json, read_json, require_safe_id
from novel_workflow.workflows.frozen_route_contract import canonical_digest


class Phase32ProviderReadinessAdmissionPolicy(BaseModel):
    """The exact release policy used to produce a persisted verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    policy_id: Literal["phase32-provider-readiness-admission.v1"] = (
        "phase32-provider-readiness-admission.v1"
    )
    require_canonical_workflow: Literal[True] = True
    require_text_only: Literal[True] = True
    required_model_id: str = Field(min_length=1, max_length=240)
    required_profile_kind: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]{1,79}$",
    )
    max_pricing_age_hours: int = Field(default=24, ge=1, le=24)
    max_admission_age_seconds: int = Field(default=900, ge=1, le=3_600)


class Phase32ProviderReadinessAdmission(BaseModel):
    """One content-addressed, secret-free configuration observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    architecture_version: Literal["phase32-routes-v1"] = "phase32-routes-v1"
    admission_ref: str = Field(pattern=r"^p32-provider-readiness-[a-f0-9]{64}$")
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
    definition_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: str = Field(min_length=1, max_length=80)
    expires_at: str = Field(min_length=1, max_length=80)
    policy: Phase32ProviderReadinessAdmissionPolicy
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    report: Phase32ProviderReadinessReport
    report_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    verdict: Literal["ready", "blocked"]

    @model_validator(mode="after")
    def validate_content_addressed_identity(self) -> "Phase32ProviderReadinessAdmission":
        observed_at = parse_readiness_timestamp(self.observed_at)
        expires_at = parse_readiness_timestamp(self.expires_at)
        expected_expiry = readiness_admission_expiry(
            observed_at=observed_at,
            policy=self.policy,
            report=self.report,
        )
        if expires_at != expected_expiry:
            raise ValueError(
                "Provider readiness admission expiry differs from its frozen policy"
            )
        if (
            self.report.run_id != self.run_id
            or self.report.definition_digest != self.definition_digest
            or self.report.observed_at != self.observed_at
        ):
            raise ValueError("Provider readiness report identity differs from admission")
        if (
            self.report.require_canonical_workflow
            != self.policy.require_canonical_workflow
            or self.report.require_text_only != self.policy.require_text_only
            or self.report.required_model_id != self.policy.required_model_id
            or self.report.required_profile_kind != self.policy.required_profile_kind
            or self.report.max_pricing_age_hours
            != self.policy.max_pricing_age_hours
        ):
            raise ValueError("Provider readiness report policy differs from admission")
        if self.policy_digest != canonical_digest(self.policy.model_dump(mode="json")):
            raise ValueError("Provider readiness policy digest does not match")
        if self.report_digest != canonical_digest(self.report.model_dump(mode="json")):
            raise ValueError("Provider readiness report digest does not match")
        expected_verdict = "ready" if self.report.ready else "blocked"
        if self.verdict != expected_verdict:
            raise ValueError("Provider readiness verdict differs from its report")
        expected_ref = readiness_admission_ref(
            self.model_dump(mode="json", exclude={"admission_ref"})
        )
        if self.admission_ref != expected_ref:
            raise ValueError("Provider readiness admission is not content addressed")
        _assert_redacted(self.model_dump(mode="json"))
        return self


class Phase32ProviderReadinessStoreError(ValueError):
    code = "phase32_provider_readiness_store_invalid"


class Phase32ProviderReadinessStore:
    """Store immutable observations and expose their latest chronological head."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_root = root / ".locks"
        self.lock_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def write(
        self,
        admission: Phase32ProviderReadinessAdmission,
    ) -> Phase32ProviderReadinessAdmission:
        try:
            admission = Phase32ProviderReadinessAdmission.model_validate(
                admission.model_dump(mode="json")
            )
        except Exception as exc:
            raise Phase32ProviderReadinessStoreError(
                "Provider readiness admission is invalid"
            ) from exc
        safe_run_id = require_safe_id(admission.run_id, label="run_id")
        with self._run_guard(safe_run_id):
            path = self._path(safe_run_id, admission.admission_ref)
            if path.exists():
                existing = self._read_path(path)
                if existing != admission:
                    raise Phase32ProviderReadinessStoreError(
                        "Provider readiness admission identity is immutable"
                    )
                return existing
            for existing in self.list(safe_run_id):
                if existing.observed_at == admission.observed_at:
                    raise Phase32ProviderReadinessStoreError(
                        "One Run cannot persist conflicting readiness observations "
                        "at the same instant"
                    )
            atomic_write_json(path, admission.model_dump(mode="json"))
            return admission

    def read(
        self,
        run_id: str,
        admission_ref: str,
    ) -> Phase32ProviderReadinessAdmission:
        path = self._path(run_id, admission_ref)
        if not path.exists():
            raise FileNotFoundError(admission_ref)
        admission = self._read_path(path)
        if admission.run_id != require_safe_id(run_id, label="run_id"):
            raise Phase32ProviderReadinessStoreError(
                "Provider readiness admission belongs to another Run"
            )
        if admission.admission_ref != require_safe_id(
            admission_ref,
            label="admission_ref",
        ):
            raise Phase32ProviderReadinessStoreError(
                "Provider readiness admission storage identity differs"
            )
        return admission

    def list(self, run_id: str) -> list[Phase32ProviderReadinessAdmission]:
        safe_run_id = require_safe_id(run_id, label="run_id")
        directory = self.root / safe_run_id
        if not directory.exists():
            return []
        admissions = [
            self._read_path(path)
            for path in directory.glob("p32-provider-readiness-*.json")
        ]
        for admission in admissions:
            if admission.run_id != safe_run_id:
                raise Phase32ProviderReadinessStoreError(
                    "Provider readiness admission belongs to another Run"
                )
        return sorted(
            admissions,
            key=lambda item: (parse_readiness_timestamp(item.observed_at), item.admission_ref),
        )

    def latest(self, run_id: str) -> Phase32ProviderReadinessAdmission | None:
        admissions = self.list(run_id)
        return admissions[-1] if admissions else None

    def _path(self, run_id: str, admission_ref: str) -> Path:
        safe_run_id = require_safe_id(run_id, label="run_id")
        safe_ref = require_safe_id(admission_ref, label="admission_ref")
        if not safe_ref.startswith("p32-provider-readiness-"):
            raise ValueError("Invalid Provider readiness admission reference")
        return self.root / safe_run_id / f"{safe_ref}.json"

    @staticmethod
    def _read_path(path: Path) -> Phase32ProviderReadinessAdmission:
        try:
            return Phase32ProviderReadinessAdmission.model_validate(read_json(path))
        except Exception as exc:
            raise Phase32ProviderReadinessStoreError(
                f"Malformed Phase 32 Provider readiness admission: {path.name}"
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


def readiness_admission_ref(value: dict[str, object]) -> str:
    return f"p32-provider-readiness-{canonical_digest(value)}"


def readiness_admission_expiry(
    *,
    observed_at: datetime,
    policy: Phase32ProviderReadinessAdmissionPolicy,
    report: Phase32ProviderReadinessReport,
) -> datetime:
    """Derive the non-extendable TTL/pricing freshness boundary."""

    if observed_at.tzinfo is None:
        raise ValueError("Provider readiness observation must include a timezone")
    observed_at = observed_at.astimezone(timezone.utc)
    expiry = observed_at + timedelta(seconds=policy.max_admission_age_seconds)
    pricing_ages = tuple(stage.pricing_age_hours for stage in report.stages)
    if not pricing_ages or any(age is None for age in pricing_ages):
        return observed_at
    remaining_pricing_hours = max(
        0.0,
        policy.max_pricing_age_hours
        - max(age for age in pricing_ages if age is not None),
    )
    # The report deliberately stores only a rounded age, so round the
    # remaining window down rather than accidentally extending freshness.
    remaining_pricing_seconds = int(remaining_pricing_hours * 3_600)
    return min(
        expiry,
        observed_at + timedelta(seconds=remaining_pricing_seconds),
    )


def parse_readiness_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Provider readiness timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("Provider readiness timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _assert_redacted(value: object) -> None:
    forbidden_keys = {
        "api_key",
        "base_url",
        "headers",
        "payload",
        "prompt",
        "request",
        "secret_ref",
        "secret_value",
        "source_url",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in forbidden_keys:
                raise ValueError("Provider readiness admission contains sensitive fields")
            _assert_redacted(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_redacted(nested)


__all__ = [
    "Phase32ProviderReadinessAdmission",
    "Phase32ProviderReadinessAdmissionPolicy",
    "Phase32ProviderReadinessStore",
    "Phase32ProviderReadinessStoreError",
    "parse_readiness_timestamp",
    "readiness_admission_expiry",
    "readiness_admission_ref",
]
