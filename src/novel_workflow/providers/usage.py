from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderUsageSummary(BaseModel):
    """Rebuildable projection of receipted Provider work for one Run."""

    model_config = ConfigDict(extra="forbid")

    provider_operations: int = Field(default=0, ge=0)
    returned_operations: int = Field(default=0, ge=0)
    succeeded_operations: int = Field(default=0, ge=0)
    contract_rejected_operations: int = Field(default=0, ge=0)
    failed_operations: int = Field(default=0, ge=0)
    pending_operations: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)


CostStatus = Literal["known", "unknown", "unavailable"]
BalanceStatus = Literal["unknown", "available", "insufficient", "unavailable"]
PricingEstimateBasis = Literal[
    "published_rates",
    "conservative_upper_bound",
    "fixed_output_estimate",
    "unavailable",
]


class Phase32ProviderPricingSnapshot(BaseModel):
    """The pricing inputs frozen into one Phase 32 Run binding.

    Pricing is deliberately a snapshot rather than a live catalog lookup. A
    resumed operation must use the exact same rates that were selected when
    the Run was created, otherwise a later catalog edit would rewrite history.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider_profile_id: str = Field(default="", max_length=240)
    provider_template_id: str = Field(default="", max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    currency: Literal["USD"] = "USD"
    input_usd_per_million_tokens: float | None = Field(default=None, ge=0)
    output_usd_per_million_tokens: float | None = Field(default=None, ge=0)
    fixed_output_usd: float | None = Field(default=None, ge=0)
    source: Literal["profile", "unavailable"] = "unavailable"
    source_url: str = Field(default="", max_length=2_000, exclude_if=lambda value: not value)
    verified_at: str = Field(default="", max_length=80, exclude_if=lambda value: not value)
    estimate_basis: PricingEstimateBasis = Field(
        default="unavailable",
        exclude_if=lambda value: value == "unavailable",
    )
    estimate_basis_note: str = Field(
        default="",
        max_length=1_000,
        exclude_if=lambda value: not value,
    )
    snapshot_ref: str = Field(
        default="",
        pattern=r"^(?:p32-provider-pricing-[a-f0-9]{64})?$",
    )

    @property
    def status(self) -> CostStatus:
        if self.source == "unavailable":
            return "unknown"
        if (
            self.input_usd_per_million_tokens is not None
            or self.output_usd_per_million_tokens is not None
            or self.fixed_output_usd is not None
        ):
            return "known"
        return "unknown"

    @model_validator(mode="after")
    def validate_snapshot_ref(self) -> "Phase32ProviderPricingSnapshot":
        rates = (
            self.input_usd_per_million_tokens,
            self.output_usd_per_million_tokens,
            self.fixed_output_usd,
        )
        if self.source == "profile":
            if not any(value is not None for value in rates):
                raise ValueError("Profile pricing requires at least one rate")
            if not self.source_url.startswith(("https://", "http://")):
                raise ValueError("Profile pricing requires an HTTP(S) source URL")
            try:
                verified = datetime.fromisoformat(self.verified_at)
            except ValueError as exc:
                raise ValueError("Profile pricing verification time must be ISO 8601") from exc
            if verified.tzinfo is None:
                raise ValueError("Profile pricing verification time must include a timezone")
            if self.estimate_basis == "unavailable" or not self.estimate_basis_note:
                raise ValueError("Profile pricing requires an explicit estimate basis")
        elif any(value is not None for value in rates):
            raise ValueError("Unavailable pricing cannot carry rates")
        if self.snapshot_ref:
            payload = self.model_dump(mode="json", exclude={"snapshot_ref"})
            digest = _pricing_digest(payload)
            if self.snapshot_ref != f"p32-provider-pricing-{digest}":
                raise ValueError("Provider pricing snapshot reference does not match its payload")
        return self


class Phase32ProviderCostBreakdown(BaseModel):
    """Rebuildable cost/balance summary for one provider/model pair."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    provider_profile_id: str = ""
    provider_template_id: str = ""
    model_id: str = ""
    operations: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    cost_status: CostStatus = "unknown"
    balance_status: BalanceStatus = "unknown"

    @model_validator(mode="after")
    def validate_cost_projection(self) -> "Phase32ProviderCostBreakdown":
        if self.cost_status == "known" and self.estimated_cost_usd is None:
            raise ValueError("Known Provider cost requires an estimated cost value")
        if self.estimated_cost_usd is not None and self.cost_status != "known":
            raise ValueError("Estimated Provider cost must be marked known")
        if self.balance_status == "insufficient" and self.operations == 0:
            raise ValueError("Insufficient balance requires at least one operation")
        return self


class Phase32ProviderUsageSummary(ProviderUsageSummary):
    """Phase 32 usage projection with explicit cost and balance semantics."""

    model_config = ConfigDict(extra="forbid")

    estimated_cost_usd: float | None = Field(default=None, ge=0)
    cost_status: CostStatus = "unknown"
    balance_status: BalanceStatus = "unknown"
    by_provider: tuple[Phase32ProviderCostBreakdown, ...] = ()

    @model_validator(mode="after")
    def validate_projection_consistency(self) -> "Phase32ProviderUsageSummary":
        if self.by_provider:
            operation_total = sum(item.operations for item in self.by_provider)
            if operation_total != self.provider_operations:
                raise ValueError(
                    "Provider usage operation count does not match its breakdown"
                )
        if self.cost_status == "known":
            if self.estimated_cost_usd is None:
                raise ValueError("Known Provider cost requires an estimated cost value")
            if self.by_provider and any(
                item.cost_status != "known" for item in self.by_provider
            ):
                raise ValueError("Known Provider total requires known breakdown costs")
            if self.by_provider:
                breakdown_total = round(
                    sum(item.estimated_cost_usd or 0 for item in self.by_provider),
                    12,
                )
                if breakdown_total != self.estimated_cost_usd:
                    raise ValueError(
                        "Provider usage cost does not match its breakdown total"
                    )
        elif self.estimated_cost_usd is not None:
            raise ValueError("Estimated Provider cost must be marked known")
        if self.by_provider and any(
            item.balance_status == "insufficient" for item in self.by_provider
        ) and self.balance_status != "insufficient":
            raise ValueError("Provider balance status must surface insufficient state")
        return self


def freeze_phase32_pricing_snapshot(
    *,
    provider_profile_id: str,
    provider_template_id: str,
    model_id: str,
    input_usd_per_million_tokens: float | None = None,
    output_usd_per_million_tokens: float | None = None,
    fixed_output_usd: float | None = None,
    source_url: str = "",
    verified_at: str = "",
    estimate_basis: PricingEstimateBasis = "unavailable",
    estimate_basis_note: str = "",
) -> dict[str, Any]:
    """Return a content-addressed JSON payload suitable for a frozen binding."""

    has_rate = any(
        value is not None
        for value in (
            input_usd_per_million_tokens,
            output_usd_per_million_tokens,
            fixed_output_usd,
        )
    )
    has_provenance = bool(
        source_url.strip()
        and verified_at.strip()
        and estimate_basis != "unavailable"
        and estimate_basis_note.strip()
    )
    use_profile_pricing = has_rate and has_provenance
    snapshot = Phase32ProviderPricingSnapshot(
        provider_profile_id=provider_profile_id,
        provider_template_id=provider_template_id,
        model_id=model_id,
        input_usd_per_million_tokens=(
            input_usd_per_million_tokens if use_profile_pricing else None
        ),
        output_usd_per_million_tokens=(
            output_usd_per_million_tokens if use_profile_pricing else None
        ),
        fixed_output_usd=fixed_output_usd if use_profile_pricing else None,
        source="profile" if use_profile_pricing else "unavailable",
        source_url=source_url if use_profile_pricing else "",
        verified_at=verified_at if use_profile_pricing else "",
        estimate_basis=estimate_basis if use_profile_pricing else "unavailable",
        estimate_basis_note=estimate_basis_note if use_profile_pricing else "",
    )
    payload = snapshot.model_dump(mode="json", exclude={"snapshot_ref"})
    digest = _pricing_digest(payload)
    return {**payload, "snapshot_ref": f"p32-provider-pricing-{digest}"}


class Phase32PricingReadinessError(ValueError):
    code = "phase32_provider_pricing_not_ready"

    def __init__(self, issue_codes: tuple[str, ...]) -> None:
        self.issue_codes = issue_codes
        super().__init__(
            "Phase 32 real Provider pricing is not ready: " + ", ".join(issue_codes)
        )


def ensure_phase32_text_pricing_ready(
    pricing: Phase32ProviderPricingSnapshot,
) -> None:
    """Reject a real text call unless its exact frozen rates are traceable."""

    issue_codes: list[str] = []
    if pricing.source != "profile":
        issue_codes.append("pricing_unavailable")
    if pricing.input_usd_per_million_tokens is None:
        issue_codes.append("input_rate_missing")
    if pricing.output_usd_per_million_tokens is None:
        issue_codes.append("output_rate_missing")
    if not pricing.source_url:
        issue_codes.append("pricing_source_missing")
    if not pricing.verified_at:
        issue_codes.append("pricing_verification_missing")
    if pricing.estimate_basis == "unavailable" or not pricing.estimate_basis_note:
        issue_codes.append("pricing_basis_missing")
    if issue_codes:
        raise Phase32PricingReadinessError(tuple(issue_codes))


def ensure_phase32_image_pricing_ready(
    pricing: Phase32ProviderPricingSnapshot,
) -> None:
    """Reject an image call unless one output has a traceable frozen price."""

    issue_codes: list[str] = []
    if pricing.source != "profile":
        issue_codes.append("pricing_unavailable")
    if pricing.fixed_output_usd is None:
        issue_codes.append("fixed_output_rate_missing")
    if not pricing.source_url:
        issue_codes.append("pricing_source_missing")
    if not pricing.verified_at:
        issue_codes.append("pricing_verification_missing")
    if pricing.estimate_basis == "unavailable" or not pricing.estimate_basis_note:
        issue_codes.append("pricing_basis_missing")
    if issue_codes:
        raise Phase32PricingReadinessError(tuple(issue_codes))


def phase32_pricing_snapshot(value: Any) -> Phase32ProviderPricingSnapshot:
    """Validate a binding snapshot, treating absent pricing as unknown."""

    if isinstance(value, Phase32ProviderPricingSnapshot):
        return value
    if not isinstance(value, dict):
        return Phase32ProviderPricingSnapshot(model_id="unknown")
    return Phase32ProviderPricingSnapshot.model_validate(value)


def estimate_phase32_cost(
    usage: dict[str, int],
    pricing: Phase32ProviderPricingSnapshot,
) -> float | None:
    """Calculate a deterministic estimate from the returned Provider usage."""

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if (
        isinstance(prompt_tokens, int)
        and prompt_tokens > 0
        and pricing.input_usd_per_million_tokens is None
        and pricing.fixed_output_usd is None
    ) or (
        isinstance(completion_tokens, int)
        and completion_tokens > 0
        and pricing.output_usd_per_million_tokens is None
        and pricing.fixed_output_usd is None
    ):
        return None
    cost = 0.0
    has_token_rate = False
    if pricing.input_usd_per_million_tokens is not None and prompt_tokens is not None:
        cost += prompt_tokens * pricing.input_usd_per_million_tokens / 1_000_000
        has_token_rate = True
    if pricing.output_usd_per_million_tokens is not None and completion_tokens is not None:
        cost += completion_tokens * pricing.output_usd_per_million_tokens / 1_000_000
        has_token_rate = True
    if has_token_rate:
        return round(cost, 12)
    if pricing.fixed_output_usd is not None:
        return round(pricing.fixed_output_usd, 12)
    return None


def balance_status_from_diagnostic(diagnostic: Any) -> BalanceStatus:
    """Map only the normalized public error code into a balance state."""

    if not isinstance(diagnostic, dict):
        return "unknown"
    code = str(diagnostic.get("code") or "").strip().lower()
    if code == "insufficient_balance":
        return "insufficient"
    return "unknown"


def _pricing_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def provider_usage_snapshot(provider: Any) -> dict[str, int]:
    return normalize_provider_usage(getattr(provider, "last_usage", None))


def normalize_provider_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    aliases = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
        "reasoning_tokens": ("reasoning_tokens",),
    }
    for key, candidates in aliases.items():
        raw = next((value.get(candidate) for candidate in candidates if candidate in value), None)
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number >= 0:
            result[key] = number
    if "total_tokens" not in result and result:
        result["total_tokens"] = result.get("prompt_tokens", 0) + result.get(
            "completion_tokens",
            0,
        )
    return result


def provider_total_tokens(provider: Any) -> int | None:
    usage = provider_usage_snapshot(provider)
    total = usage.get("total_tokens")
    return total if isinstance(total, int) and total > 0 else None


__all__ = [
    "BalanceStatus",
    "CostStatus",
    "Phase32ProviderCostBreakdown",
    "Phase32ProviderPricingSnapshot",
    "Phase32PricingReadinessError",
    "Phase32ProviderUsageSummary",
    "ProviderUsageSummary",
    "balance_status_from_diagnostic",
    "estimate_phase32_cost",
    "ensure_phase32_image_pricing_ready",
    "ensure_phase32_text_pricing_ready",
    "freeze_phase32_pricing_snapshot",
    "normalize_provider_usage",
    "phase32_pricing_snapshot",
    "provider_total_tokens",
    "provider_usage_snapshot",
]
