from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderUsageCapabilities(BaseModel):
    provider_id: str = ""
    model: str = ""
    token_counting: bool = False
    cost_estimation: bool = False
    prompt_caching: bool = False
    reasoning_tokens: bool = False


class UsageSnapshot(BaseModel):
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    candidate_count: int = 1
    revision_count: int = 0
    estimated_cost_usd: float | None = None
    elapsed_ms: int = 0
    cost_available: bool = False


class StageUsageSummary(BaseModel):
    stage_key: str
    node_id: str
    label: str
    stage_type: str
    provider_profile_id: str = ""
    model: str = ""
    usage: UsageSnapshot = Field(default_factory=UsageSnapshot)
    capabilities: ProviderUsageCapabilities = Field(default_factory=ProviderUsageCapabilities)
