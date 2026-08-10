from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider
from novel_workflow.providers.openai_image import OpenAICompatibleImageProvider
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.providers.templates import require_provider_template
from novel_workflow.workflows.schemas import ModelSettings, ProviderProfile


class ProviderUnavailableError(RuntimeError):
    pass


class ProviderRegistry:
    def __init__(
        self,
        text_provider: TextProvider,
        image_provider: ImageProvider,
        *,
        text_providers: dict[str, TextProvider] | None = None,
        image_providers: dict[str, ImageProvider] | None = None,
    ) -> None:
        self.text_provider = text_provider
        self.image_provider = image_provider
        self.text_providers = text_providers or {}
        self.image_providers = image_providers or {}

    @classmethod
    def from_env(cls) -> "ProviderRegistry":
        text_providers: dict[str, TextProvider] = {}
        image_providers: dict[str, ImageProvider] = {}
        env_provider = OpenAICompatibleTextProvider.from_env()
        env_image_provider = OpenAICompatibleImageProvider.from_env()
        if env_provider is not None:
            text_providers["openai-compatible"] = env_provider
        if env_image_provider is not None:
            image_providers["openai-compatible-image"] = env_image_provider
        text_provider = env_provider or _UnavailableTextProvider("openai-compatible")
        image_provider = env_image_provider or _UnavailableImageProvider("openai-compatible-image")
        return cls(
            text_provider=text_provider,
            image_provider=image_provider,
            text_providers=text_providers,
            image_providers=image_providers,
        )

    @classmethod
    def from_profiles(
        cls,
        profiles: list[ProviderProfile],
        *,
        secret_resolver: Callable[[str], str | None] | None = None,
    ) -> "ProviderRegistry":
        text_provider: TextProvider | None = None
        image_provider: ImageProvider = _UnavailableImageProvider("image-provider")
        text_providers: dict[str, TextProvider] = {}
        image_providers: dict[str, ImageProvider] = {}
        for profile in profiles:
            if not profile.enabled:
                continue
            if profile.kind == "openai-compatible":
                try:
                    template = require_provider_template(profile.template_id, profile.kind)
                    if not template.execution_allowed or not template.workflow_execution_allowed:
                        continue
                except ValueError:
                    continue
                provider = _text_provider_from_profile(
                    profile,
                    secret_resolver=secret_resolver,
                )
                if provider is not None:
                    text_providers[profile.id] = provider
                    text_provider = provider
            elif profile.kind == "openai-compatible-image":
                try:
                    template = require_provider_template(profile.template_id, profile.kind)
                    if not template.execution_allowed or not template.workflow_execution_allowed:
                        continue
                except ValueError:
                    continue
                provider = _image_provider_from_profile(
                    profile,
                    secret_resolver=secret_resolver,
                )
                if provider is not None:
                    image_providers[profile.id] = provider
                    image_provider = provider
        if text_provider is None:
            text_provider = _UnavailableTextProvider("openai-compatible")
        return cls(text_provider=text_provider, image_provider=image_provider, text_providers=text_providers, image_providers=image_providers)

    def text_for(self, provider_profile_id: str, settings: ModelSettings | None = None) -> TextProvider:
        provider = self.text_providers.get(provider_profile_id)
        if provider is None:
            raise ProviderUnavailableError(f"Text provider is not configured: {provider_profile_id}")
        return _with_model_settings(provider, settings)

    def image_for(self, provider_profile_id: str) -> ImageProvider:
        provider = self.image_providers.get(provider_profile_id)
        if provider is None:
            raise ProviderUnavailableError(f"Image provider is not configured: {provider_profile_id}")
        return provider

    def describe(self) -> dict[str, Any]:
        return {
            "text": self.text_provider.name,
            "image": self.image_provider.name,
        }


def _text_provider_from_profile(
    profile: ProviderProfile,
    *,
    secret_resolver: Callable[[str], str | None] | None,
) -> OpenAICompatibleTextProvider | None:
    api_key = secret_resolver(profile.id) if secret_resolver else None
    if not api_key and profile.api_key_env:
        api_key = os.environ.get(profile.api_key_env)
    return OpenAICompatibleTextProvider.from_profile(
        base_url=profile.base_url,
        api_key=api_key or "",
        model=profile.default_model,
        max_tokens=512,
        template_id=profile.template_id,
    )


def _image_provider_from_profile(
    profile: ProviderProfile,
    *,
    secret_resolver: Callable[[str], str | None] | None,
) -> OpenAICompatibleImageProvider | None:
    api_key = secret_resolver(profile.id) if secret_resolver else None
    if not api_key and profile.api_key_env:
        api_key = os.environ.get(profile.api_key_env)
    return OpenAICompatibleImageProvider.from_profile(
        base_url=profile.base_url,
        api_key=api_key or "",
        model=profile.default_model,
        template_id=profile.template_id,
    )


def _with_model_settings(provider: TextProvider, settings: ModelSettings | None) -> TextProvider:
    if not isinstance(provider, OpenAICompatibleTextProvider) or settings is None:
        return provider
    return provider.with_options(
        model=settings.model or provider.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        top_p=settings.top_p,
        timeout_seconds=settings.timeout_seconds,
    )


class _UnavailableTextProvider(TextProvider):
    name = "unconfigured-openai-compatible"

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise ProviderUnavailableError(f"Text provider is not configured: {self.provider_id}")


class _UnavailableImageProvider(ImageProvider):
    name = "unconfigured-image-provider"

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        raise ProviderUnavailableError(f"Image provider is not configured: {self.provider_id}")
