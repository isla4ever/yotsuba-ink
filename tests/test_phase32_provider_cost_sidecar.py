from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.phase32_contract import Phase32ProviderRequest
from novel_workflow.providers.usage import (
    Phase32ProviderCostBreakdown,
    Phase32ProviderPricingSnapshot,
    Phase32ProviderUsageSummary,
    Phase32PricingReadinessError,
    ensure_phase32_text_pricing_ready,
    estimate_phase32_cost,
    freeze_phase32_pricing_snapshot,
)
from novel_workflow.runtime.graph.phase32_driver import (
    Phase32DriverError,
    Phase32RouteDriver,
)
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationReceipt,
    Phase32ProviderOperationReceiptConflict,
    Phase32ProviderOperationStore,
    provider_request_signature,
)
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from novel_workflow.workflows.templates import (
    DEEPSEEK_FLASH_MODEL,
    DEEPSEEK_PRICING_SOURCE_URL,
    default_provider_profiles,
)
from tests.test_phase32_route_graph import _definition


def _signature(operation_key: str = "run-1:brief:1") -> str:
    return provider_request_signature(
        {"operation_key": operation_key, "run_id": "run-1", "stage_id": "brief"}
    )


def _pricing(*, output_rate: float = 0.28) -> dict[str, object]:
    return freeze_phase32_pricing_snapshot(
        provider_profile_id="deepseek",
        provider_template_id="deepseek-text",
        model_id="deepseek-chat",
        input_usd_per_million_tokens=0.14,
        output_usd_per_million_tokens=output_rate,
        source_url="https://provider.example/pricing",
        verified_at="2026-08-23T12:00:00+08:00",
        estimate_basis="published_rates",
        estimate_basis_note="Public test rates for the exact model.",
    )


def test_default_deepseek_flash_pricing_matches_verified_official_rates() -> None:
    deepseek = next(
        profile
        for profile in default_provider_profiles()
        if profile.id == "provider-deepseek-text"
    )
    pricing = deepseek.model_pricing[DEEPSEEK_FLASH_MODEL]

    assert pricing.input_usd_per_million_tokens == 0.44
    assert pricing.output_usd_per_million_tokens == 1.32
    assert pricing.source_url == DEEPSEEK_PRICING_SOURCE_URL
    assert pricing.verified_at == "2026-08-26T11:43:02+08:00"
    assert pricing.estimate_basis == "conservative_upper_bound"


def test_phase32_pricing_snapshot_is_content_addressed_and_usage_based() -> None:
    pricing = Phase32ProviderPricingSnapshot.model_validate(_pricing())
    assert pricing.snapshot_ref.startswith("p32-provider-pricing-")
    assert pricing.status == "known"
    assert pricing.source_url == "https://provider.example/pricing"
    ensure_phase32_text_pricing_ready(pricing)
    assert estimate_phase32_cost(
        {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}, pricing
    ) == 0.28


def test_receipt_costs_a_validated_pricing_snapshot_model(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    pricing = Phase32ProviderPricingSnapshot.model_validate(_pricing())
    signature = _signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
        pricing_snapshot_ref=pricing.snapshot_ref,
    )

    returned = store.record_return(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        raw_provider_payload={"payload": "redacted-test-payload"},
        usage={"prompt_tokens": 1_000_000, "completion_tokens": 500_000},
        pricing_snapshot=pricing,
    )

    assert returned.estimated_cost_usd == 0.28
    assert returned.cost_status == "known"


def test_missing_pricing_is_unknown_and_never_fabricates_zero() -> None:
    pricing = Phase32ProviderPricingSnapshot(model_id="deepseek-chat")
    assert pricing.status == "unknown"
    assert estimate_phase32_cost({"total_tokens": 20}, pricing) is None
    with pytest.raises(Phase32PricingReadinessError) as exc:
        ensure_phase32_text_pricing_ready(pricing)
    assert "pricing_unavailable" in exc.value.issue_codes


def test_rates_without_provenance_are_not_frozen_as_known_pricing() -> None:
    pricing = Phase32ProviderPricingSnapshot.model_validate(
        freeze_phase32_pricing_snapshot(
            provider_profile_id="deepseek",
            provider_template_id="deepseek-text",
            model_id="deepseek-chat",
            input_usd_per_million_tokens=0.14,
            output_usd_per_million_tokens=0.28,
        )
    )

    assert pricing.source == "unavailable"
    assert pricing.input_usd_per_million_tokens is None
    assert pricing.output_usd_per_million_tokens is None


def test_receipt_persists_cost_and_rebuilds_provider_breakdown(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    pricing = _pricing()
    signature = _signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
        provider_profile_id="deepseek",
        provider_template_id="deepseek-text",
        model_id="deepseek-chat",
        pricing_snapshot_ref=str(pricing["snapshot_ref"]),
    )
    returned = store.record_return(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        raw_provider_payload={"payload": "redacted-test-payload"},
        usage={"prompt_tokens": 1_000_000, "completion_tokens": 500_000},
        pricing_snapshot=pricing,
    )
    assert returned.estimated_cost_usd == 0.28
    assert returned.cost_status == "known"

    summary = store.usage_summary("run-1")
    assert summary.estimated_cost_usd == 0.28
    assert summary.cost_status == "known"
    assert summary.by_provider[0].model_id == "deepseek-chat"
    assert summary.by_provider[0].estimated_cost_usd == 0.28


def test_usage_summary_keeps_partial_zero_cost_in_breakdown_without_fabricating_total(
    tmp_path: Path,
) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    text_signature = _signature("run-1:text:1")
    store.begin(
        run_id="run-1",
        operation_key="run-1:text:1",
        stage_id="text",
        request_signature=text_signature,
        provider_profile_id="text-provider",
        provider_template_id="text-template",
        model_id="text-model",
    )
    store.record_return(
        run_id="run-1",
        operation_key="run-1:text:1",
        request_signature=text_signature,
        raw_provider_payload={"content": "fixture"},
        usage={},
    )

    image_pricing = freeze_phase32_pricing_snapshot(
        provider_profile_id="image-provider",
        provider_template_id="image-template",
        model_id="image-model",
        fixed_output_usd=0,
        source_url="https://provider.example/image-pricing",
        verified_at="2026-08-24T12:00:00+08:00",
        estimate_basis="fixed_output_estimate",
        estimate_basis_note="Zero-cost deterministic fixture image.",
    )
    image_signature = _signature("run-1:cover:image:1")
    store.begin(
        run_id="run-1",
        operation_key="run-1:cover:image:1",
        stage_id="cover",
        request_signature=image_signature,
        provider_profile_id="image-provider",
        provider_template_id="image-template",
        model_id="image-model",
        pricing_snapshot_ref=str(image_pricing["snapshot_ref"]),
    )
    store.record_return(
        run_id="run-1",
        operation_key="run-1:cover:image:1",
        request_signature=image_signature,
        raw_provider_payload={"asset_ref": "fixture-image"},
        usage={"total_tokens": 1},
        pricing_snapshot=image_pricing,
    )

    summary = store.usage_summary("run-1")
    by_provider = {item.provider_profile_id: item for item in summary.by_provider}
    assert summary.provider_operations == 2
    assert summary.cost_status == "unknown"
    assert summary.estimated_cost_usd is None
    assert by_provider["text-provider"].cost_status == "unknown"
    assert by_provider["text-provider"].estimated_cost_usd is None
    assert by_provider["image-provider"].cost_status == "known"
    assert by_provider["image-provider"].estimated_cost_usd == 0


def test_same_operation_rejects_pricing_snapshot_drift(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    first = _pricing()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=_signature(),
        provider_profile_id="deepseek",
        provider_template_id="deepseek-text",
        model_id="deepseek-chat",
        pricing_snapshot_ref=str(first["snapshot_ref"]),
    )
    changed = dict(first)
    changed["output_usd_per_million_tokens"] = 0.30
    changed["snapshot_ref"] = _pricing(output_rate=0.30)["snapshot_ref"]
    with pytest.raises(Phase32ProviderOperationReceiptConflict, match="different frozen request"):
        store.begin(
            run_id="run-1",
            operation_key="run-1:brief:1",
            stage_id="brief",
            request_signature=_signature(),
            provider_profile_id="deepseek",
            provider_template_id="deepseek-text",
            model_id="deepseek-chat",
            pricing_snapshot_ref=str(changed["snapshot_ref"]),
        )


def test_return_cannot_replace_the_frozen_pricing_snapshot(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    expensive = _pricing(output_rate=10.0)
    cheap = _pricing(output_rate=0.01)
    signature = _signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
        provider_profile_id="deepseek",
        provider_template_id="deepseek-text",
        model_id="deepseek-chat",
        pricing_snapshot_ref=str(expensive["snapshot_ref"]),
    )

    with pytest.raises(Phase32ProviderOperationReceiptConflict, match="pricing"):
        store.record_return(
            run_id="run-1",
            operation_key="run-1:brief:1",
            request_signature=signature,
            raw_provider_payload={"payload": "must-not-be-costed-at-the-cheap-rate"},
            usage={"prompt_tokens": 1_000, "completion_tokens": 1_000},
            pricing_snapshot=cheap,
        )

    receipt = store.read("run-1", "run-1:brief:1")
    assert receipt.status == "pending"
    assert receipt.estimated_cost_usd is None


def test_insufficient_balance_is_public_state_only(tmp_path: Path) -> None:
    store = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    signature = _signature()
    store.begin(
        run_id="run-1",
        operation_key="run-1:brief:1",
        stage_id="brief",
        request_signature=signature,
    )
    store.release_pending(
        run_id="run-1",
        operation_key="run-1:brief:1",
        request_signature=signature,
        lease_owner="not-leased",
        diagnostic={"code": "insufficient_balance"},
    )
    receipt = store.read("run-1", "run-1:brief:1")
    assert receipt.balance_status == "insufficient"
    assert receipt.diagnostic == {"code": "insufficient_balance"}
    assert "api_key" not in receipt.model_dump(mode="json")


def test_usage_summary_rejects_breakdown_count_drift() -> None:
    with pytest.raises(ValueError, match="operation count"):
        Phase32ProviderUsageSummary(
            provider_operations=2,
            by_provider=(
                Phase32ProviderCostBreakdown(
                    provider_profile_id="deepseek",
                    provider_template_id="deepseek-text",
                    model_id="deepseek-chat",
                    operations=1,
                ),
            ),
        )


def test_usage_summary_rejects_cost_total_drift() -> None:
    with pytest.raises(ValueError, match="breakdown total"):
        Phase32ProviderUsageSummary(
            provider_operations=1,
            estimated_cost_usd=0.3,
            cost_status="known",
            by_provider=(
                Phase32ProviderCostBreakdown(
                    provider_profile_id="deepseek",
                    provider_template_id="deepseek-text",
                    model_id="deepseek-chat",
                    operations=1,
                    estimated_cost_usd=0.2,
                    cost_status="known",
                ),
            ),
        )


def test_receipt_rejects_cost_status_drift() -> None:
    with pytest.raises(ValueError, match="Known Provider cost"):
        Phase32ProviderOperationReceipt(
            receipt_ref="p32-provider-operation-" + "a" * 64,
            run_id="run-1",
            operation_key="run-1:brief:1",
            stage_id="brief",
            request_signature="b" * 64,
            status="returned",
            cost_status="known",
            created_at="2026-08-23T12:00:00+08:00",
            updated_at="2026-08-23T12:00:00+08:00",
        )


class _InsufficientBalanceGateway:
    async def generate(self, request: Phase32ProviderRequest, *, binding):
        raise ProviderResponseError(
            "insufficient_balance",
            "upstream secret body must never be persisted",
            http_status=402,
        )


@pytest.mark.asyncio
async def test_driver_persists_only_public_insufficient_balance_state(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    operations = Phase32ProviderOperationStore(tmp_path / "provider-operations")
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        _InsufficientBalanceGateway(),
        provider_operations=operations,
    )

    with pytest.raises(Phase32DriverError, match="transport failed"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )

    receipt = operations.list(definition.run_id)[0]
    assert receipt.status == "pending"
    assert receipt.balance_status == "insufficient"
    assert receipt.diagnostic == {"code": "insufficient_balance"}
    assert receipt.raw_provider_payload is None
    assert "secret body" not in receipt.model_dump_json()
