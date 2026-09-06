from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationProviderCapability,
    CollaborationSettings,
    CollaborationSettingsEnvelope,
)
from novel_workflow.providers.frozen_contract import (
    FrozenProviderConfig,
    FrozenProviderTemplate,
    frozen_provider_config_digest,
    frozen_provider_template_digest,
    prompt_digest,
)
from novel_workflow.providers.readiness import provider_connection_ready
from novel_workflow.providers.templates import require_provider_template
from novel_workflow.storage.collaboration_settings_store import CollaborationSettingsStore
from novel_workflow.storage.narrative_run_repository import ProviderBinding
from novel_workflow.providers.phase32_contract import Phase32ProviderExecutionSnapshot
from novel_workflow.workflows.phase32_provider_binding import (
    build_phase32_collaboration_execution_snapshot,
)
from novel_workflow.workflows.schemas import ProviderProfile


class CollaborationSettingsError(ValueError):
    code = "collaboration_settings_invalid"


class CollaborationSettingsService:
    def __init__(
        self,
        store: CollaborationSettingsStore,
        *,
        providers: Callable[[], list[ProviderProfile]],
        secret_resolver: Callable[[str], str | None],
    ) -> None:
        self.store = store
        self.providers = providers
        self.secret_resolver = secret_resolver

    def read(self) -> CollaborationSettingsEnvelope:
        settings = self._with_default_provider(self.store.read())
        return CollaborationSettingsEnvelope(
            settings=settings,
            capabilities=self.capabilities(),
        )

    def save(self, settings: CollaborationSettings) -> CollaborationSettingsEnvelope:
        capabilities = self.capabilities()
        if settings.default_provider_profile_id:
            selected = next(
                (
                    item
                    for item in capabilities
                    if item.provider_profile_id == settings.default_provider_profile_id
                    and item.model == settings.default_model
                ),
                None,
            )
            if selected is None:
                raise CollaborationSettingsError(
                    "The selected collaboration Provider/model is not configured"
                )
            if not selected.ready:
                raise CollaborationSettingsError(
                    "The selected collaboration Provider/model is not ready"
                )
        saved = self.store.write(settings)
        return CollaborationSettingsEnvelope(settings=saved, capabilities=capabilities)

    def capabilities(self) -> list[CollaborationProviderCapability]:
        checked_at = datetime.now(timezone.utc).isoformat()
        return [
            self._capability(profile, checked_at)
            for profile in self.providers()
            if profile.kind == "openai-compatible"
        ]

    def freeze_new_thread_binding(
        self,
        run_stage_binding: ProviderBinding,
    ) -> ProviderBinding:
        """Freeze the saved collaboration default for one new thread.

        An absent settings file means the book keeps its Run-frozen stage
        binding. Once the author explicitly saves a collaboration default, a
        stale or unavailable profile is an error rather than a silent fallback.
        """

        if not self.store.exists():
            return run_stage_binding
        settings = self.store.read()
        if not settings.default_provider_profile_id:
            return run_stage_binding
        profile = next(
            (
                item
                for item in self.providers()
                if item.id == settings.default_provider_profile_id
            ),
            None,
        )
        if profile is None or profile.kind != "openai-compatible":
            raise CollaborationSettingsError(
                "The saved collaboration Provider is no longer configured"
            )
        capability = self._capability(
            profile,
            datetime.now(timezone.utc).isoformat(),
        )
        if profile.default_model != settings.default_model or not capability.ready:
            raise CollaborationSettingsError(
                "The saved collaboration Provider/model is no longer ready"
            )
        source_template = require_provider_template(profile.template_id, profile.kind)
        config = FrozenProviderConfig.from_profile(profile)
        template = FrozenProviderTemplate.from_template(source_template)
        prompt = "Yotsuba Ink author collaboration prompt v1"
        return ProviderBinding(
            provider_profile_id=profile.id,
            provider_config=config,
            template_id=template.id,
            provider_template=template,
            provider_config_digest=frozen_provider_config_digest(config),
            provider_template_digest=frozen_provider_template_digest(template),
            model=settings.default_model,
            temperature=run_stage_binding.temperature,
            max_tokens=run_stage_binding.max_tokens,
            top_p=run_stage_binding.top_p,
            timeout_seconds=run_stage_binding.timeout_seconds,
            prompt_template_id="author-collaboration-v1",
            prompt_template=prompt,
            prompt_digest=prompt_digest(prompt),
            structured_tasks={},
        )

    def freeze_phase32_new_thread_execution(
        self,
        run_stage_execution: Phase32ProviderExecutionSnapshot,
    ) -> Phase32ProviderExecutionSnapshot:
        """Freeze the selected text Provider into a new Phase 32 thread."""

        if not self.store.exists():
            return run_stage_execution
        settings = self.store.read()
        if not settings.default_provider_profile_id:
            return run_stage_execution
        profile = next(
            (
                item
                for item in self.providers()
                if item.id == settings.default_provider_profile_id
            ),
            None,
        )
        if profile is None or profile.kind != "openai-compatible":
            raise CollaborationSettingsError(
                "The saved collaboration Provider is no longer configured"
            )
        capability = self._capability(
            profile,
            datetime.now(timezone.utc).isoformat(),
        )
        if profile.default_model != settings.default_model or not capability.ready:
            raise CollaborationSettingsError(
                "The saved collaboration Provider/model is no longer ready"
            )
        return build_phase32_collaboration_execution_snapshot(
            profile,
            model=settings.default_model,
            base=run_stage_execution,
        )

    def _capability(
        self,
        profile: ProviderProfile,
        checked_at: str,
    ) -> CollaborationProviderCapability:
        issue_codes: list[str] = []
        ready = provider_connection_ready(
            profile,
            expected_kind="openai-compatible",
            secret_resolver=self.secret_resolver,
        )
        if not ready:
            issue_codes.append("connection_not_ready")
        structured_patch = False
        try:
            template = require_provider_template(profile.template_id, profile.kind)
            structured_patch = bool(template.workflow_execution_allowed)
        except ValueError:
            issue_codes.append("provider_template_invalid")
        model_discovered = bool(
            profile.default_model
            and profile.default_model in profile.model_options
        )
        if profile.model_options and not model_discovered:
            issue_codes.append("model_not_discovered")
            ready = False
        return CollaborationProviderCapability(
            provider_profile_id=profile.id,
            provider_name=profile.name,
            model=profile.default_model,
            supports_multi_turn=ready,
            # Phase 31 streams lifecycle/read-model updates. Token deltas are
            # deliberately not presented as a Provider capability yet.
            supports_streaming=False,
            supports_structured_patch=ready and structured_patch,
            capability_checked_at=checked_at,
            capability_source="discovered" if model_discovered else "manual",
            ready=ready,
            issue_codes=list(dict.fromkeys(issue_codes)),
        )

    def _with_default_provider(self, settings: CollaborationSettings) -> CollaborationSettings:
        if settings.default_provider_profile_id:
            return settings
        profile = next(
            (
                item
                for item in self.providers()
                if item.kind == "openai-compatible" and item.is_global_default
            ),
            None,
        )
        if profile is None:
            return settings
        return settings.model_copy(
            update={
                "default_provider_profile_id": profile.id,
                "default_model": profile.default_model,
            }
        )


__all__ = [
    "CollaborationSettingsError",
    "CollaborationSettingsService",
]
