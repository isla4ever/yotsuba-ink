"""Zero-call environment gate before a private Phase 32 live candidate Run."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from novel_workflow.providers.usage import freeze_phase32_pricing_snapshot
from novel_workflow.storage.phase32_live_candidate_preflight_store import (
    Phase32LiveCandidatePreflightStore,
)
from novel_workflow.storage.provider_profile_store import (
    ProviderProfileStore,
    ProviderProfileStoreConflict,
)
from novel_workflow.usage.phase32_live_candidate_preflight_contract import (
    Phase32LiveCandidateEnvironmentReport,
    Phase32PricingAttestation,
    Phase32PricingAttestationCommand,
    build_live_candidate_environment_report,
    build_pricing_attestation,
)
from novel_workflow.workflows.definition_schemas import (
    ProviderModelPricing,
    ProviderProfile,
)
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.templates import (
    DEEPSEEK_PRICING_SOURCE_URL,
    DEEPSEEK_PRO_MODEL,
    DEEPSEEK_PROVIDER_ID,
)


Clock = Callable[[], datetime]
SecretResolver = Callable[[str], str | None]
_MAX_PRICING_AGE_HOURS = 24
_DEEPSEEK_TEMPLATE_ID = "deepseek-text"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class Phase32LiveCandidatePreflightError(ValueError):
    code = "phase32_live_candidate_preflight_failed"


class Phase32LiveCandidatePreflightService:
    """Refresh auditable pricing and emit a persisted, non-billable report."""

    def __init__(
        self,
        *,
        profiles: ProviderProfileStore,
        store: Phase32LiveCandidatePreflightStore,
        secret_resolver: SecretResolver,
        clock: Clock | None = None,
    ) -> None:
        self.profiles = profiles
        self.store = store
        self.secret_resolver = secret_resolver
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def attest_pricing(
        self,
        command: Phase32PricingAttestationCommand,
    ) -> Phase32PricingAttestation:
        """Apply one compare-and-swap pricing refresh without Provider IO."""

        command_digest = canonical_digest(command.model_dump(mode="json"))
        with self.store.pricing_guard(command.idempotency_key):
            existing = self.store.find_attestation(command.idempotency_key)
            if existing is not None:
                if existing.command_digest != command_digest:
                    raise Phase32LiveCandidatePreflightError(
                        "Pricing idempotency key already belongs to another command"
                    )
                return self._reconcile_attestation(existing)

            now = _utc(self.clock())
            _require_current_official_attestation(command, now=now)
            profile = self._read_profile()
            before_digest = _profile_digest(profile)
            latest = self.store.latest_attestation()
            if latest is not None and before_digest != latest.profile_after_digest:
                if before_digest == latest.profile_before_digest:
                    raise Phase32LiveCandidatePreflightError(
                        "A recorded pricing transition still requires recovery"
                    )
                raise Phase32LiveCandidatePreflightError(
                    "Provider profile diverged from the latest pricing authority"
                )
            if before_digest != command.expected_profile_digest:
                raise Phase32LiveCandidatePreflightError(
                    "Provider profile changed after the pricing command was prepared"
                )
            _require_profile_identity(profile)
            updated = _updated_profile(profile, command)
            after_digest = _profile_digest(updated)
            attestation = build_pricing_attestation(
                command,
                attested_at=now.isoformat(),
                profile_after_digest=after_digest,
            )
            # Persist intent first. If the process exits before the catalog
            # write, an identical replay completes the recorded transition.
            self.store.write_attestation(attestation)
            self._write_profile_cas(profile, updated)
            if _profile_digest(self._read_profile()) != after_digest:
                raise Phase32LiveCandidatePreflightError(
                    "Provider pricing refresh did not persist its expected profile"
                )
            return attestation

    def assess_environment(self) -> Phase32LiveCandidateEnvironmentReport:
        """Persist a redacted report; this method cannot contact a Provider."""

        observed_at = _utc(self.clock())
        issues: list[str] = []
        profile: ProviderProfile | None = None
        try:
            profile = self._read_profile()
        except Exception:
            issues.append("provider_profile_unreadable")

        profile_digest = ""
        template_id = ""
        pricing_snapshot_ref = ""
        source_digest = ""
        pricing_verified_at = ""
        pricing_age_hours: float | None = None
        input_rate: float | None = None
        output_rate: float | None = None
        latest = self.store.latest_attestation()
        attestation_ref = latest.attestation_ref if latest is not None else ""

        if profile is not None:
            profile_digest = _profile_digest(profile)
            template_id = profile.template_id
            try:
                _require_profile_identity(profile)
            except Phase32LiveCandidatePreflightError:
                issues.append("provider_profile_identity_mismatch")
            pricing = profile.model_pricing.get(DEEPSEEK_PRO_MODEL)
            if pricing is None:
                issues.append("pricing_missing")
            else:
                input_rate = pricing.input_usd_per_million_tokens
                output_rate = pricing.output_usd_per_million_tokens
                pricing_verified_at = pricing.verified_at
                source_digest = canonical_digest({"source_url": pricing.source_url})
                if (
                    input_rate is None
                    or input_rate <= 0
                    or output_rate is None
                    or output_rate <= 0
                    or pricing.estimate_basis != "conservative_upper_bound"
                ):
                    issues.append("pricing_not_conservative")
                if not _same_url(pricing.source_url, DEEPSEEK_PRICING_SOURCE_URL):
                    issues.append("pricing_source_mismatch")
                try:
                    verified_at = _utc(datetime.fromisoformat(pricing.verified_at))
                except (TypeError, ValueError):
                    issues.append("pricing_verification_invalid")
                else:
                    age_seconds = (observed_at - verified_at).total_seconds()
                    if age_seconds < 0:
                        issues.append("pricing_verification_in_future")
                    else:
                        pricing_age_hours = round(age_seconds / 3_600, 6)
                        if pricing_age_hours > _MAX_PRICING_AGE_HOURS:
                            issues.append("pricing_verification_stale")
                snapshot = freeze_phase32_pricing_snapshot(
                    provider_profile_id=profile.id,
                    provider_template_id=profile.template_id,
                    model_id=DEEPSEEK_PRO_MODEL,
                    input_usd_per_million_tokens=input_rate,
                    output_usd_per_million_tokens=output_rate,
                    fixed_output_usd=pricing.fixed_output_usd,
                    source_url=pricing.source_url,
                    verified_at=pricing.verified_at,
                    estimate_basis=pricing.estimate_basis,
                    estimate_basis_note=pricing.estimate_basis_note,
                )
                pricing_snapshot_ref = str(snapshot["snapshot_ref"])

        if latest is None:
            issues.append("pricing_attestation_missing")
        elif profile is not None and (
            pricing is None
            or latest.profile_after_digest != profile_digest
            or latest.provider_profile_id != profile.id
            or latest.provider_template_id != profile.template_id
            or latest.model_id != DEEPSEEK_PRO_MODEL
            or latest.input_usd_per_million_tokens != input_rate
            or latest.output_usd_per_million_tokens != output_rate
            or latest.verified_at != pricing_verified_at
            or latest.source_url != pricing.source_url
        ):
            issues.append("pricing_attestation_profile_drift")

        secret_configured = False
        try:
            secret = self.secret_resolver(DEEPSEEK_PROVIDER_ID)
            secret_configured = isinstance(secret, str) and bool(secret.strip())
        except Exception:
            pass
        if not secret_configured:
            issues.append("provider_secret_missing")

        issue_codes = tuple(dict.fromkeys(issues))
        ready = not issue_codes
        payload: dict[str, object] = {
            "report_version": "phase32-live-candidate-preflight.v1",
            "observed_at": observed_at.isoformat(),
            "provider_profile_id": DEEPSEEK_PROVIDER_ID,
            "provider_template_id": template_id,
            "model_id": DEEPSEEK_PRO_MODEL,
            "profile_digest": profile_digest,
            "pricing_attestation_ref": attestation_ref,
            "pricing_snapshot_ref": pricing_snapshot_ref,
            "pricing_source_digest": source_digest,
            "pricing_verified_at": pricing_verified_at,
            "pricing_age_hours": pricing_age_hours,
            "input_usd_per_million_tokens": input_rate,
            "output_usd_per_million_tokens": output_rate,
            "secret_configured": secret_configured,
            "issue_codes": issue_codes,
            "verdict": "ready_for_budget_authorization" if ready else "blocked",
            "next_gate": "explicit_run_budget" if ready else "refresh_environment",
            "billable_call_count": 0,
        }
        return self.store.write_report(build_live_candidate_environment_report(payload))

    def require_current_report(
        self,
        report_ref: str,
    ) -> Phase32LiveCandidateEnvironmentReport:
        """Revalidate one persisted report without creating Provider IO."""

        try:
            report = self.store.read_report(report_ref)
        except FileNotFoundError as exc:
            raise Phase32LiveCandidatePreflightError(
                "Live candidate environment report is missing"
            ) from exc
        verified_at = _utc(datetime.fromisoformat(report.pricing_verified_at))
        now = _utc(self.clock())
        if now < verified_at or (now - verified_at).total_seconds() > 86_400:
            raise Phase32LiveCandidatePreflightError(
                "Live candidate pricing is no longer current"
            )
        latest = self.store.latest_attestation()
        current = self._read_profile()
        if (
            report.verdict != "ready_for_budget_authorization"
            or report.billable_call_count != 0
            or not report.secret_configured
            or latest is None
            or latest.attestation_ref != report.pricing_attestation_ref
            or _profile_digest(current) != report.profile_digest
        ):
            raise Phase32LiveCandidatePreflightError(
                "Live candidate environment authority has drifted"
            )
        try:
            secret = self.secret_resolver(DEEPSEEK_PROVIDER_ID)
        except Exception as exc:
            raise Phase32LiveCandidatePreflightError(
                "Live candidate Provider secret is unavailable"
            ) from exc
        if not isinstance(secret, str) or not secret.strip():
            raise Phase32LiveCandidatePreflightError(
                "Live candidate Provider secret is unavailable"
            )
        return report

    def _reconcile_attestation(
        self,
        attestation: Phase32PricingAttestation,
    ) -> Phase32PricingAttestation:
        profile = self._read_profile()
        current_digest = _profile_digest(profile)
        if current_digest == attestation.profile_after_digest:
            return attestation
        if current_digest != attestation.profile_before_digest:
            raise Phase32LiveCandidatePreflightError(
                "Provider profile diverged from the recorded pricing transition"
            )
        _require_profile_identity(profile)
        updated = _updated_profile(profile, attestation)
        if _profile_digest(updated) != attestation.profile_after_digest:
            raise Phase32LiveCandidatePreflightError(
                "Recorded pricing transition cannot be reconstructed"
            )
        self._write_profile_cas(profile, updated)
        return attestation

    def _read_profile(self) -> ProviderProfile:
        return ProviderProfile.model_validate(
            self.profiles.read(DEEPSEEK_PROVIDER_ID)
        )

    def _write_profile_cas(
        self,
        current: ProviderProfile,
        updated: ProviderProfile,
    ) -> None:
        try:
            self.profiles.write_if_current(
                current.id,
                expected=current.model_dump(mode="json"),
                data=updated.model_dump(mode="json"),
            )
        except ProviderProfileStoreConflict as exc:
            raise Phase32LiveCandidatePreflightError(
                "Provider profile changed during pricing compare-and-swap"
            ) from exc


def _require_current_official_attestation(
    command: Phase32PricingAttestationCommand,
    *,
    now: datetime,
) -> None:
    if not _same_url(command.source_url, DEEPSEEK_PRICING_SOURCE_URL):
        raise Phase32LiveCandidatePreflightError(
            "Continuity pricing must cite the official DeepSeek pricing page"
        )
    verified_at = _utc(datetime.fromisoformat(command.verified_at))
    age_seconds = (now - verified_at).total_seconds()
    if age_seconds < 0:
        raise Phase32LiveCandidatePreflightError(
            "Pricing verification time cannot be in the future"
        )
    if age_seconds > _MAX_PRICING_AGE_HOURS * 3_600:
        raise Phase32LiveCandidatePreflightError(
            "Pricing attestation is already stale"
        )


def _require_profile_identity(profile: ProviderProfile) -> None:
    if (
        profile.id != DEEPSEEK_PROVIDER_ID
        or profile.kind != "openai-compatible"
        or profile.template_id != _DEEPSEEK_TEMPLATE_ID
        or profile.base_url.rstrip("/") != _DEEPSEEK_BASE_URL
        or not profile.enabled
        or DEEPSEEK_PRO_MODEL not in profile.model_options
    ):
        raise Phase32LiveCandidatePreflightError(
            "Provider profile does not match the official live candidate identity"
        )


def _updated_profile(
    profile: ProviderProfile,
    source: Phase32PricingAttestationCommand | Phase32PricingAttestation,
) -> ProviderProfile:
    pricing = ProviderModelPricing(
        input_usd_per_million_tokens=source.input_usd_per_million_tokens,
        output_usd_per_million_tokens=source.output_usd_per_million_tokens,
        fixed_output_usd=None,
        source_url=source.source_url,
        verified_at=source.verified_at,
        estimate_basis=source.estimate_basis,
        estimate_basis_note=source.estimate_basis_note,
    )
    return profile.model_copy(
        update={
            "model_pricing": {
                **profile.model_pricing,
                DEEPSEEK_PRO_MODEL: pricing,
            }
        }
    )


def _profile_digest(profile: ProviderProfile) -> str:
    return canonical_digest(profile.model_dump(mode="json"))


def _same_url(left: str, right: str) -> bool:
    return left.strip().rstrip("/") == right.strip().rstrip("/")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Live candidate preflight clock must include a timezone")
    return value.astimezone(timezone.utc)


__all__ = [
    "Phase32LiveCandidatePreflightError",
    "Phase32LiveCandidatePreflightService",
]
