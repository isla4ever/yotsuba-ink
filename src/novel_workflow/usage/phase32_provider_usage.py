"""Rebuildable usage/cost projections for Phase 32 Provider receipts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from novel_workflow.providers.usage import (
    Phase32ProviderCostBreakdown,
    Phase32ProviderUsageSummary,
)


def summarize_phase32_provider_receipts(
    receipts: Iterable[Any],
) -> Phase32ProviderUsageSummary:
    """Aggregate receipt-shaped records without owning receipt persistence."""

    items = tuple(receipts)
    groups: dict[tuple[str, str, str], list[Any]] = {}
    for receipt in items:
        key = (
            str(getattr(receipt, "provider_profile_id", "")),
            str(getattr(receipt, "provider_template_id", "")),
            str(getattr(receipt, "model_id", "")),
        )
        groups.setdefault(key, []).append(receipt)

    breakdowns: list[Phase32ProviderCostBreakdown] = []
    for (profile_id, template_id, model_id), grouped in sorted(groups.items()):
        costs = [getattr(item, "estimated_cost_usd", None) for item in grouped]
        known_costs = [cost for cost in costs if isinstance(cost, (int, float))]
        statuses = {str(getattr(item, "cost_status", "unknown")) for item in grouped}
        balance_states = {
            str(getattr(item, "balance_status", "unknown")) for item in grouped
        }
        breakdowns.append(
            Phase32ProviderCostBreakdown(
                provider_profile_id=profile_id,
                provider_template_id=template_id,
                model_id=model_id,
                operations=len(grouped),
                estimated_cost_usd=_known_cost_total(
                    statuses,
                    known_costs,
                    operation_count=len(grouped),
                ),
                cost_status=_cost_status(statuses, known_costs),
                balance_status=_balance_status(balance_states),
            )
        )

    known_costs = [
        getattr(item, "estimated_cost_usd", None)
        for item in items
        if isinstance(getattr(item, "estimated_cost_usd", None), (int, float))
    ]
    statuses = {str(getattr(item, "cost_status", "unknown")) for item in items}
    balance_states = {
        str(getattr(item, "balance_status", "unknown")) for item in items
    }
    return Phase32ProviderUsageSummary(
        provider_operations=len(items),
        returned_operations=sum(
            getattr(item, "status", "")
            in {"returned", "succeeded", "contract_rejected"}
            for item in items
        ),
        succeeded_operations=sum(getattr(item, "status", "") == "succeeded" for item in items),
        contract_rejected_operations=sum(
            getattr(item, "status", "") == "contract_rejected" for item in items
        ),
        failed_operations=0,
        pending_operations=sum(getattr(item, "status", "") == "pending" for item in items),
        prompt_tokens=sum(
            getattr(item, "usage", {}).get("prompt_tokens", 0) for item in items
        ),
        completion_tokens=sum(
            getattr(item, "usage", {}).get("completion_tokens", 0) for item in items
        ),
        total_tokens=sum(
            getattr(item, "usage", {}).get("total_tokens", 0) for item in items
        ),
        reasoning_tokens=sum(
            getattr(item, "usage", {}).get("reasoning_tokens", 0) for item in items
        ),
        estimated_cost_usd=_known_cost_total(
            statuses,
            known_costs,
            operation_count=len(items),
        ),
        cost_status=_cost_status(statuses, known_costs),
        balance_status=_balance_status(balance_states),
        by_provider=tuple(breakdowns),
    )


def _cost_status(statuses: set[str], known_costs: list[int | float]) -> str:
    if known_costs and statuses <= {"known"}:
        return "known"
    if "unavailable" in statuses:
        return "unavailable"
    return "unknown"


def _known_cost_total(
    statuses: set[str],
    known_costs: list[int | float],
    *,
    operation_count: int,
) -> float | None:
    if (
        operation_count > 0
        and statuses == {"known"}
        and len(known_costs) == operation_count
    ):
        return round(sum(known_costs), 12)
    return None


def _balance_status(states: set[str]) -> str:
    if "insufficient" in states:
        return "insufficient"
    if "unavailable" in states:
        return "unavailable"
    if states == {"available"}:
        return "available"
    return "unknown"


__all__ = ["summarize_phase32_provider_receipts"]
