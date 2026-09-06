"""Compile explicit Provider bindings for a frozen Phase 32 route."""

from __future__ import annotations

from collections.abc import Mapping

from novel_workflow.providers.frozen_contract import (
    FrozenProviderConfig,
    FrozenProviderTemplate,
    frozen_provider_config_digest,
    frozen_provider_template_digest,
)
from novel_workflow.providers.phase32_contract import (
    Phase32ImageProviderExecutionSnapshot,
    Phase32ModelSettings,
    Phase32ProviderExecutionSnapshot,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.providers.templates import require_provider_template
from novel_workflow.providers.usage import (
    Phase32ProviderPricingSnapshot,
    freeze_phase32_pricing_snapshot,
)
from novel_workflow.workflows.definition_schemas import (
    ModelSettings,
    ProviderProfile,
    WorkflowDefinition,
)
from novel_workflow.workflows.graph_run_definition import (
    FrozenStageProviderBinding,
    freeze_contract_payload,
)
from novel_workflow.workflows.route_compiler import CompiledRouteManifest
from novel_workflow.workflows.phase32_prompt_contract import (
    build_phase32_provider_task_snapshot,
)
from novel_workflow.workflows.route_specs import CreationRouteId
from novel_workflow.workflows.templates import generation_budget_for_stage
from novel_workflow.workflows.workflow_ids import (
    OFFICIAL_LONG_NOVEL_WORKFLOW_ID,
    OFFICIAL_SCREENPLAY_WORKFLOW_ID,
    OFFICIAL_SHORT_NOVEL_WORKFLOW_ID,
    is_image_acceptance_deferred_workflow_id,
)


class ProviderBindingError(ValueError):
    code = "phase32_provider_binding_invalid"


# Phase 27 template nodes are configuration sources only.  They never become
# Phase 32 stage identities.
_SOURCE_NODE_BY_ROUTE_STAGE: dict[CreationRouteId, dict[str, str]] = {
    "screenplay_sample": {
        "brief": "brief",
        "cast": "cast",
        "beat_board": "spine",
        "scene_deck": "detail",
        "script": "text",
    },
    "short_novel": {
        "brief": "brief",
        "story_map": "spine",
        "cast": "cast",
        "section_plan": "detail",
        "text": "text",
        "cover": "cover",
    },
    "long_novel": {
        "brief": "brief",
        "book_architecture": "spine",
        "cast": "cast",
        "volumes": "volumes",
        "rolling_detail": "detail",
        "text": "text",
        "cover": "cover",
    },
}

# Canonical route identities replace the retired Fast/Balanced/Deep templates.
# Keep their proven text-model split explicit while the route-native editor is
# still being built: screenplay is the bounded Flash path, while both novel
# routes reserve Pro for longer planning and prose contexts. Custom drafts
# continue to use the selected profile default below.
_CANONICAL_ROUTE_MODEL: dict[str, str] = {
    OFFICIAL_SCREENPLAY_WORKFLOW_ID: "deepseek-v4-flash",
    OFFICIAL_SHORT_NOVEL_WORKFLOW_ID: "deepseek-v4-pro",
    OFFICIAL_LONG_NOVEL_WORKFLOW_ID: "deepseek-v4-pro",
}

_CANONICAL_STAGE_SOURCE: dict[CreationRouteId, dict[str, str]] = {
    "screenplay_sample": {
        "brief": "brief",
        "cast": "cast",
        "beat_board": "spine",
        "scene_deck": "detail",
        "script": "text",
    },
    "short_novel": {
        "brief": "brief",
        "story_map": "spine",
        "cast": "cast",
        "section_plan": "detail",
        "text": "text",
    },
    "long_novel": {
        "brief": "brief",
        "book_architecture": "spine",
        "cast": "cast",
        "volumes": "volumes",
        "rolling_detail": "detail",
        "text": "text",
    },
}

_CANONICAL_STAGE_TEMPERATURE: dict[str, float] = {
    "spine": 0.45,
    "cast": 0.55,
    "detail": 0.30,
    "text": 0.82,
}


def build_phase32_provider_bindings(
    route_id: CreationRouteId,
    manifest: CompiledRouteManifest,
    source: WorkflowDefinition | None,
    providers: Mapping[str, ProviderProfile],
    *,
    workflow_id: str,
) -> tuple[FrozenStageProviderBinding, ...]:
    """Freeze one explicit Provider binding for every generative route stage.

    Legacy templates may still provide per-stage settings during migration;
    canonical Phase 32 routes use the deterministic executable default profile
    selected above.
    """

    source_nodes = {node.id: node for node in source.nodes} if source else {}
    aliases = _SOURCE_NODE_BY_ROUTE_STAGE[route_id]
    default_text = _select_executable_profile(
        providers,
        kind="openai-compatible",
    )
    default_image = _select_executable_profile(
        providers,
        kind="openai-compatible-image",
    )
    image_acceptance_deferred = is_image_acceptance_deferred_workflow_id(workflow_id)
    if source is None and default_text is None:
        raise ProviderBindingError(
            "No executable default text Provider profile is available"
        )
    bindings: list[FrozenStageProviderBinding] = []
    for stage in manifest.stages:
        if stage.provider_task_kind is None:
            continue
        node = source_nodes.get(aliases.get(stage.stage_id, ""))
        profile_id = node.provider_profile_id if node else (default_text.id if default_text else "")
        profile = providers.get(profile_id)
        if profile is None:
            raise ProviderBindingError(
                f"Stage {stage.stage_id} references unavailable Provider profile: {profile_id}"
            )
        model = node.model_settings.model if node else _default_model(
            workflow_id,
            profile,
        )
        settings = (
            node.model_settings
            if node is not None
            else _canonical_stage_settings(route_id, stage.stage_id, model)
        )
        execution = _text_execution_snapshot(
            profile,
            model=model,
            node=node,
            settings=settings,
        )
        image_profile_id = node.image_provider_profile_id if node else ""
        image_execution = None
        if not image_acceptance_deferred and stage.stage_id == "cover" and image_profile_id:
            image_profile = providers.get(image_profile_id)
            if image_profile is None:
                raise ProviderBindingError(
                    f"Cover stage references unavailable image Provider profile: {image_profile_id}"
                )
            if _image_profile_is_executable(image_profile):
                image_execution = _image_execution_snapshot(image_profile, node=node)
        elif (
            not image_acceptance_deferred
            and stage.stage_id == "cover"
            and default_image is not None
            and _image_profile_is_executable(default_image)
        ):
            image_execution = _image_execution_snapshot(default_image, node=node)
        payload = Phase32StageProviderBindingSnapshot(
            workflow_id=workflow_id,
            creation_route_id=route_id,
            stage_id=stage.stage_id,
            execution=execution,
            image_execution=image_execution,
            task=build_phase32_provider_task_snapshot(route_id, stage),
        ).model_dump(mode="json")
        bindings.append(
            FrozenStageProviderBinding(
                stage_id=stage.stage_id,
                binding=freeze_contract_payload(
                    contract_id=f"provider.binding.{route_id}.{stage.stage_id}.v1",
                    contract_revision="r1",
                    payload=payload,
                ),
            )
        )
    return tuple(bindings)


def _default_model(workflow_id: str, profile: ProviderProfile) -> str:
    """Resolve a route-owned model without weakening profile validation."""

    preferred = _CANONICAL_ROUTE_MODEL.get(workflow_id)
    if not preferred:
        return profile.default_model
    if profile.model_options and preferred not in profile.model_options:
        return profile.default_model
    if preferred not in profile.model_pricing:
        return profile.default_model
    return preferred


def _canonical_stage_settings(
    route_id: CreationRouteId,
    stage_id: str,
    model: str,
) -> ModelSettings:
    """Freeze the proven stage budget when no legacy template is read."""

    source_stage = _CANONICAL_STAGE_SOURCE[route_id].get(stage_id, stage_id)
    budget = generation_budget_for_stage(source_stage)
    return ModelSettings(
        model=model,
        temperature=_CANONICAL_STAGE_TEMPERATURE.get(source_stage, 0.7),
        max_tokens=budget.max_tokens,
        top_p=0.95,
        timeout_seconds=120,
    )


def _select_executable_profile(
    providers: Mapping[str, ProviderProfile],
    *,
    kind: str,
) -> ProviderProfile | None:
    """Pick a deterministic usable default instead of the first DB row.

    Provider profiles are persisted independently from the route contract and
    may contain disabled, incomplete, or historical records.  Selecting by
    insertion/id order can therefore freeze an empty `base_url` even when a
    valid global default exists.  Prefer explicit global defaults and use the
    id only as a stable tie-breaker.
    """

    candidates = sorted(
        (profile for profile in providers.values() if profile.kind == kind),
        key=lambda profile: (not profile.is_global_default, profile.id),
    )
    for profile in candidates:
        if not profile.enabled or not profile.base_url.strip():
            continue
        if not profile.default_model.strip():
            continue
        try:
            template = require_provider_template(profile.template_id, profile.kind)
        except ValueError:
            continue
        if template.execution_allowed and template.workflow_execution_allowed:
            return profile
    return None


def _text_execution_snapshot(
    profile: ProviderProfile,
    *,
    model: str,
    node,
    settings: ModelSettings | None = None,
) -> Phase32ProviderExecutionSnapshot:
    if not profile.enabled:
        raise ProviderBindingError(f"Provider profile is disabled: {profile.id}")
    if profile.kind != "openai-compatible":
        raise ProviderBindingError(f"Text stage requires a text Provider: {profile.id}")
    if not profile.base_url.strip() or not model.strip():
        raise ProviderBindingError(f"Provider profile is incomplete: {profile.id}")
    try:
        source_template = require_provider_template(profile.template_id, profile.kind)
    except ValueError as exc:
        raise ProviderBindingError(f"Provider template is invalid: {profile.template_id}") from exc
    if not source_template.execution_allowed or not source_template.workflow_execution_allowed:
        raise ProviderBindingError(f"Provider is not allowed for workflow execution: {profile.id}")
    config = FrozenProviderConfig.from_profile(profile)
    template = FrozenProviderTemplate.from_template(source_template)
    settings = settings or (node.model_settings if node else None)
    model_settings = Phase32ModelSettings(
        model=model,
        temperature=settings.temperature if settings else 0.7,
        max_tokens=settings.max_tokens if settings else 1_800,
        top_p=settings.top_p if settings else 0.95,
        timeout_seconds=settings.timeout_seconds if settings else 120,
    )
    pricing = _pricing_snapshot(profile, model=model)
    return Phase32ProviderExecutionSnapshot(
        provider_profile_id=profile.id,
        provider_template_id=profile.template_id,
        provider_config=config,
        provider_template=template,
        provider_config_digest=frozen_provider_config_digest(config),
        provider_template_digest=frozen_provider_template_digest(template),
        model_id=model,
        model_settings=model_settings,
        pricing_snapshot=pricing,
    )


def build_phase32_collaboration_execution_snapshot(
    profile: ProviderProfile,
    *,
    model: str,
    base: Phase32ProviderExecutionSnapshot,
) -> Phase32ProviderExecutionSnapshot:
    """Freeze a settings-selected Provider without inheriting mutable config."""

    execution = _text_execution_snapshot(profile, model=model, node=None)
    return execution.model_copy(
        update={
            "model_settings": execution.model_settings.model_copy(
                update={
                    "temperature": base.model_settings.temperature,
                    "max_tokens": base.model_settings.max_tokens,
                    "top_p": base.model_settings.top_p,
                    "timeout_seconds": base.model_settings.timeout_seconds,
                }
            )
        }
    )


def _image_execution_snapshot(
    profile: ProviderProfile,
    *,
    node,
) -> Phase32ImageProviderExecutionSnapshot:
    if not profile.enabled:
        raise ProviderBindingError(f"Image Provider profile is disabled: {profile.id}")
    if profile.kind != "openai-compatible-image":
        raise ProviderBindingError(f"Cover stage requires an image Provider: {profile.id}")
    if not profile.base_url.strip() or not profile.default_model.strip():
        raise ProviderBindingError(f"Image Provider profile is incomplete: {profile.id}")
    try:
        source_template = require_provider_template(profile.template_id, profile.kind)
    except ValueError as exc:
        raise ProviderBindingError(f"Image Provider template is invalid: {profile.template_id}") from exc
    if not source_template.execution_allowed or not source_template.workflow_execution_allowed:
        raise ProviderBindingError(f"Image Provider cannot execute workflows: {profile.id}")
    config = FrozenProviderConfig.from_profile(profile)
    template = FrozenProviderTemplate.from_template(source_template)
    pricing = _pricing_snapshot(profile, model=profile.default_model)
    settings = {field.key: field.default for field in node.input_schema} if node else {}
    return Phase32ImageProviderExecutionSnapshot(
        provider_profile_id=profile.id,
        provider_template_id=profile.template_id,
        provider_config=config,
        provider_template=template,
        provider_config_digest=frozen_provider_config_digest(config),
        provider_template_digest=frozen_provider_template_digest(template),
        model_id=profile.default_model,
        candidate_count=int(settings.get("candidate_count") or 3),
        size=str(settings.get("image_size") or "1024x1536"),
        quality=str(settings.get("image_quality") or "medium"),
        timeout_seconds=max(180, node.model_settings.timeout_seconds if node else 180),
        pricing_snapshot=pricing,
    )


def _image_profile_is_executable(profile: ProviderProfile) -> bool:
    return bool(
        profile.enabled
        and profile.kind == "openai-compatible-image"
        and profile.base_url.strip()
        and profile.default_model.strip()
    )


def _pricing_snapshot(
    profile: ProviderProfile,
    *,
    model: str,
) -> Phase32ProviderPricingSnapshot:
    pricing = profile.model_pricing.get(model)
    payload = freeze_phase32_pricing_snapshot(
        provider_profile_id=profile.id,
        provider_template_id=profile.template_id,
        model_id=model,
        input_usd_per_million_tokens=(
            pricing.input_usd_per_million_tokens if pricing is not None else None
        ),
        output_usd_per_million_tokens=(
            pricing.output_usd_per_million_tokens if pricing is not None else None
        ),
        fixed_output_usd=pricing.fixed_output_usd if pricing is not None else None,
        source_url=pricing.source_url if pricing is not None else "",
        verified_at=pricing.verified_at if pricing is not None else "",
        estimate_basis=pricing.estimate_basis if pricing is not None else "unavailable",
        estimate_basis_note=pricing.estimate_basis_note if pricing is not None else "",
    )
    return Phase32ProviderPricingSnapshot.model_validate(payload)


__all__ = [
    "ProviderBindingError",
    "build_phase32_collaboration_execution_snapshot",
    "build_phase32_provider_bindings",
]
