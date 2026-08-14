from __future__ import annotations

from novel_workflow.providers.frozen_contract import (
    FrozenProviderConfig,
    FrozenProviderTemplate,
    FrozenStructuredTask,
    frozen_provider_config_digest,
    frozen_provider_template_digest,
    prompt_digest,
)
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.structured_schema import structured_format_decision
from novel_workflow.providers.structured_tasks import structured_task_contracts_for_stage
from novel_workflow.providers.templates import require_provider_template
from novel_workflow.storage.narrative_run_repository import CoverAssetBinding, ProviderBinding


def provider_binding(
    stage_id: str,
    *,
    provider_profile_id: str = "fake",
    template_id: str = "openai-compatible-text",
    base_url: str = "https://provider.test/v1",
    model: str = "fake-model",
    max_tokens: int = 12_000,
) -> ProviderBinding:
    source_template = require_provider_template(template_id, "openai-compatible")
    template = FrozenProviderTemplate.from_template(source_template)
    config = FrozenProviderConfig(
        provider_profile_id=provider_profile_id,
        kind="openai-compatible",
        template_id=template_id,
        base_url=base_url,
        secret_ref=provider_profile_id,
    )
    tasks: dict[str, FrozenStructuredTask] = {}
    for contract in structured_task_contracts_for_stage(stage_id):
        policy = resolve_request_policy(
            template,
            model=model,
            task_name=contract.provider_task_name,
        )
        decision = structured_format_decision(
            policy,
            task_name=contract.provider_task_name,
            schema=contract.schema,
        )
        tasks[contract.name] = FrozenStructuredTask(
            schema_digest=_schema_digest(contract.schema),
            effective_mode=decision.effective_mode,
        )
    prompt = f"Phase 27 {stage_id} prompt"
    return ProviderBinding(
        provider_profile_id=provider_profile_id,
        provider_config=config,
        template_id=template_id,
        provider_template=template,
        provider_config_digest=frozen_provider_config_digest(config),
        provider_template_digest=frozen_provider_template_digest(template),
        model=model,
        temperature=0.3,
        max_tokens=max_tokens,
        top_p=0.8,
        timeout_seconds=30,
        prompt_template_id=f"prompt-{stage_id}",
        prompt_template=prompt,
        prompt_digest=prompt_digest(prompt),
        structured_tasks=tasks,
    )


def cover_asset_binding(
    *,
    provider_profile_id: str = "fake-image",
    template_id: str = "openai-compatible-image",
    base_url: str = "https://images.test/v1",
    model: str = "fake-image",
) -> CoverAssetBinding:
    source_template = require_provider_template(template_id, "openai-compatible-image")
    template = FrozenProviderTemplate.from_template(source_template)
    config = FrozenProviderConfig(
        provider_profile_id=provider_profile_id,
        kind="openai-compatible-image",
        template_id=template_id,
        base_url=base_url,
        secret_ref=provider_profile_id,
    )
    return CoverAssetBinding(
        provider_profile_id=provider_profile_id,
        provider_config=config,
        template_id=template_id,
        provider_template=template,
        provider_config_digest=frozen_provider_config_digest(config),
        provider_template_digest=frozen_provider_template_digest(template),
        model=model,
        candidate_count=1,
        size="256x384",
        quality="low",
        timeout_seconds=30,
        failure_policy="fail_run",
    )


def _schema_digest(schema: dict[str, object]) -> str:
    from novel_workflow.providers.frozen_contract import schema_digest

    return schema_digest(schema)
