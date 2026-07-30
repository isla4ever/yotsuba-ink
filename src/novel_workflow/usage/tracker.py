from __future__ import annotations

from typing import Any

from novel_workflow.usage.models import ProviderUsageCapabilities, StageUsageSummary, UsageSnapshot

try:  # pragma: no cover - optional dependency in local dev.
    import tiktoken
except Exception:  # pragma: no cover - graceful fallback when dependency is absent.
    tiktoken = None


def estimate_text_tokens(text: str, model: str = "") -> int:
    clean = str(text or "")
    if not clean:
        return 0
    if tiktoken is not None:
        try:
            encoding = tiktoken.encoding_for_model(model or "gpt-4.1-mini")
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(clean))
    return max(1, len(clean) // 4)


def provider_usage_capabilities(provider_profile_id: str, model: str) -> ProviderUsageCapabilities:
    provider = provider_profile_id or ""
    return ProviderUsageCapabilities(
        provider_id=provider,
        model=model,
        token_counting=provider == "openai-compatible",
        cost_estimation=False,
        prompt_caching=provider in {"openai-compatible"},
        reasoning_tokens=False,
    )


def record_stage_usage(
    state: Any,
    *,
    stage_key: str,
    node: Any,
    prompt_text: str = "",
    output_text: str = "",
    candidate_count: int = 1,
    revision_count: int = 0,
    elapsed_ms: int = 0,
) -> StageUsageSummary:
    usage = UsageSnapshot(
        estimated_input_tokens=estimate_text_tokens(prompt_text, node.model_settings.model) * max(candidate_count, 1),
        estimated_output_tokens=estimate_text_tokens(output_text, node.model_settings.model),
        candidate_count=max(candidate_count, 1),
        revision_count=max(revision_count, 0),
        elapsed_ms=max(elapsed_ms, 0),
        cost_available=False,
    )
    summary = StageUsageSummary(
        stage_key=stage_key,
        node_id=node.id,
        label=node.label,
        stage_type=node.type,
        provider_profile_id=node.provider_profile_id,
        model=node.model_settings.model,
        usage=usage,
        capabilities=provider_usage_capabilities(node.provider_profile_id, node.model_settings.model),
    )
    state.token_estimates[stage_key] = summary.model_dump()
    state.token_estimates["total_estimated_tokens"] = sum(
        item.get("usage", {}).get("estimated_input_tokens", 0) + item.get("usage", {}).get("estimated_output_tokens", 0)
        for item in state.token_estimates.values()
        if isinstance(item, dict) and "usage" in item
    )
    return summary


def record_image_stage_usage(
    state: Any,
    *,
    node: Any,
    provider_profile_id: str,
    model: str,
    image_count: int,
    failed_image_count: int,
    estimated_cost_usd: float | None,
) -> StageUsageSummary:
    usage = UsageSnapshot(
        candidate_count=max(1, image_count + failed_image_count),
        image_count=max(0, image_count),
        failed_image_count=max(0, failed_image_count),
        estimated_cost_usd=estimated_cost_usd,
        cost_available=estimated_cost_usd is not None,
    )
    summary = StageUsageSummary(
        stage_key=node.id,
        node_id=node.id,
        label=node.label,
        stage_type=node.type,
        provider_profile_id=provider_profile_id,
        model=model,
        usage=usage,
        capabilities=ProviderUsageCapabilities(
            provider_id=provider_profile_id,
            model=model,
            cost_estimation=estimated_cost_usd is not None,
            image_generation=True,
        ),
    )
    state.stage_usage_summaries[node.id] = summary.model_dump()
    return summary
