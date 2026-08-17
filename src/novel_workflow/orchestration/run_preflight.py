from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from novel_workflow.output_contracts.artifacts_vnext import StageId
from novel_workflow.providers.errors import ProviderResponseError
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
from novel_workflow.workflows.executable_contract import require_executable_workflow
from novel_workflow.workflows.schemas import PromptTemplate, ProviderProfile, WorkflowDefinition


PROVIDER_STAGES: tuple[StageId, ...] = (
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
)


class RunPreflightError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FrozenRunBindings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_bindings: dict[StageId, ProviderBinding]
    cover_asset_binding: CoverAssetBinding


class FrozenStageBindings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_bindings: dict[StageId, ProviderBinding]
    cover_asset_binding: CoverAssetBinding | None = None


class RunPreflightService:
    """Freeze every execution input before a new production Run can exist."""

    def __init__(self, *, provider_store, prompt_store, secret_store) -> None:
        self.provider_store = provider_store
        self.prompt_store = prompt_store
        self.secret_store = secret_store

    def freeze_workflow(self, workflow: WorkflowDefinition) -> FrozenRunBindings:
        frozen = self.freeze_stages(workflow, PROVIDER_STAGES)
        if frozen.cover_asset_binding is None:
            raise RunPreflightError(
                "cover_configuration_invalid",
                "A complete Run requires a frozen cover asset binding",
            )
        return FrozenRunBindings(
            provider_bindings=frozen.provider_bindings,
            cover_asset_binding=frozen.cover_asset_binding,
        )

    def freeze_stages(
        self,
        workflow: WorkflowDefinition,
        stage_ids: tuple[StageId, ...] | list[StageId],
    ) -> FrozenStageBindings:
        workflow = require_executable_workflow(workflow)
        requested = tuple(stage_ids)
        invalid = [stage_id for stage_id in requested if stage_id not in PROVIDER_STAGES]
        if invalid:
            raise RunPreflightError(
                "stage_binding_override_invalid",
                f"Stages do not own Provider bindings: {', '.join(invalid)}",
            )
        if len(requested) != len(set(requested)):
            raise RunPreflightError(
                "stage_binding_override_invalid",
                "Provider binding override stages must be unique",
            )
        nodes = {node.id: node for node in workflow.nodes}
        frozen = {
            stage_id: self._freeze_text_binding(stage_id, nodes[stage_id])
            for stage_id in requested
        }
        cover = self._freeze_cover_binding(nodes["cover"]) if "cover" in requested else None
        return FrozenStageBindings(
            provider_bindings=frozen,
            cover_asset_binding=cover,
        )

    def _freeze_text_binding(
        self,
        stage_id: StageId,
        node,
    ) -> ProviderBinding:
        profile, config, template = self._freeze_provider(
            node.provider_profile_id,
            expected_kind="openai-compatible",
        )
        prompt = self._prompt(node.prompt_template_id, stage_id)
        tasks: dict[str, FrozenStructuredTask] = {}
        for contract in structured_task_contracts_for_stage(stage_id):
            policy = resolve_request_policy(
                template,
                model=node.model_settings.model,
                task_name=contract.provider_task_name,
            )
            try:
                decision = (
                    structured_format_decision(
                        policy,
                        task_name=contract.provider_task_name,
                        schema=contract.schema,
                    )
                    if template.supports_response_format
                    else None
                )
            except ProviderResponseError as exc:
                raise RunPreflightError(exc.code, str(exc)) from exc
            effective_mode = decision.effective_mode if decision is not None else "prompt_only"
            if effective_mode == "prompt_only":
                raise RunPreflightError(
                    "strict_structured_output_required",
                    f"Provider {profile.id} cannot execute strict task {contract.name}",
                )
            tasks[contract.name] = FrozenStructuredTask(
                schema_digest=_schema_digest(contract.schema),
                effective_mode=effective_mode,
            )
        return ProviderBinding(
            provider_profile_id=profile.id,
            provider_config=config,
            template_id=template.id,
            provider_template=template,
            provider_config_digest=frozen_provider_config_digest(config),
            provider_template_digest=frozen_provider_template_digest(template),
            model=node.model_settings.model,
            temperature=node.model_settings.temperature,
            max_tokens=node.model_settings.max_tokens,
            top_p=node.model_settings.top_p,
            # Long-form chapter prose regularly exceeds the structured-stage
            # default; a run must not die because one slow completion crossed
            # a 120s line, so the text stage gets the same floor idea as cover.
            timeout_seconds=(
                max(300, node.model_settings.timeout_seconds)
                if stage_id == "text"
                else node.model_settings.timeout_seconds
            ),
            prompt_template_id=prompt.id,
            prompt_template=prompt.content,
            prompt_digest=prompt_digest(prompt.content),
            structured_tasks=tasks,
        )

    def _freeze_cover_binding(
        self,
        node,
    ) -> CoverAssetBinding:
        settings = {field.key: field.default for field in node.input_schema}
        profile, config, template = self._freeze_provider(
            node.image_provider_profile_id,
            expected_kind="openai-compatible-image",
        )
        try:
            return CoverAssetBinding(
                provider_profile_id=profile.id,
                provider_config=config,
                template_id=template.id,
                provider_template=template,
                provider_config_digest=frozen_provider_config_digest(config),
                provider_template_digest=frozen_provider_template_digest(template),
                model=profile.default_model,
                candidate_count=settings.get("candidate_count"),
                size=settings.get("image_size"),
                quality=settings.get("image_quality"),
                timeout_seconds=max(180, node.model_settings.timeout_seconds),
                failure_policy="fail_run",
            )
        except ValueError as exc:
            raise RunPreflightError(
                "cover_configuration_invalid",
                "Cover stage settings do not satisfy the Phase 27 image contract",
            ) from exc

    def _freeze_provider(
        self,
        provider_id: str,
        *,
        expected_kind: Literal["openai-compatible", "openai-compatible-image"],
    ) -> tuple[ProviderProfile, FrozenProviderConfig, FrozenProviderTemplate]:
        try:
            profile = ProviderProfile.model_validate(self.provider_store.read(provider_id))
        except FileNotFoundError as exc:
            raise RunPreflightError("provider_not_found", f"Unknown Provider: {provider_id}") from exc
        if not profile.enabled:
            raise RunPreflightError("provider_disabled", f"Provider is disabled: {provider_id}")
        if profile.kind != expected_kind:
            raise RunPreflightError(
                "provider_kind_mismatch",
                f"Provider {provider_id} is {profile.kind}, expected {expected_kind}",
            )
        if not profile.base_url.strip():
            raise RunPreflightError("base_url_missing", f"Provider Base URL is missing: {provider_id}")
        try:
            source_template = require_provider_template(profile.template_id, profile.kind)
        except ValueError as exc:
            raise RunPreflightError("provider_template_invalid", str(exc)) from exc
        if not source_template.execution_allowed:
            raise RunPreflightError(
                "provider_policy_blocked",
                source_template.execution_policy_note or f"Provider is blocked: {provider_id}",
            )
        if not source_template.workflow_execution_allowed:
            raise RunPreflightError(
                "provider_workflow_blocked",
                source_template.workflow_execution_policy_note or f"Provider cannot run workflows: {provider_id}",
            )
        if not self.secret_store.has_api_key(profile.id):
            raise RunPreflightError(
                "secret_missing",
                f"Provider requires a saved secret before Run creation: {provider_id}",
            )
        return (
            profile,
            FrozenProviderConfig.from_profile(profile),
            FrozenProviderTemplate.from_template(source_template),
        )

    def _prompt(self, prompt_id: str, stage_id: StageId) -> PromptTemplate:
        try:
            prompt = PromptTemplate.model_validate(self.prompt_store.read(prompt_id))
        except FileNotFoundError as exc:
            raise RunPreflightError("prompt_not_found", f"Unknown Prompt template: {prompt_id}") from exc
        if prompt.stage_type != stage_id:
            raise RunPreflightError(
                "prompt_stage_mismatch",
                f"Prompt {prompt_id} belongs to {prompt.stage_type}, not {stage_id}",
            )
        if not prompt.content.strip():
            raise RunPreflightError("prompt_empty", f"Prompt template is empty: {prompt_id}")
        return prompt


def _schema_digest(schema: dict[str, object]) -> str:
    from novel_workflow.providers.frozen_contract import schema_digest

    return schema_digest(schema)


__all__ = [
    "FrozenRunBindings",
    "FrozenStageBindings",
    "PROVIDER_STAGES",
    "RunPreflightError",
    "RunPreflightService",
]
