from __future__ import annotations

from typing import Any

from novel_workflow.providers.base import ImageProvider, TextProvider
from novel_workflow.providers.mock import MockImageProvider, MockTextProvider
from novel_workflow.providers.openai_compat import OpenAICompatibleTextProvider
from novel_workflow.workflows.schemas import ProviderProfile


class ProviderRegistry:
    def __init__(self, text_provider: TextProvider, image_provider: ImageProvider) -> None:
        self.text_provider = text_provider
        self.image_provider = image_provider

    @classmethod
    def from_env(cls) -> "ProviderRegistry":
        return cls(
            text_provider=OpenAICompatibleTextProvider.from_env() or MockTextProvider(),
            image_provider=MockImageProvider(),
        )

    @classmethod
    def from_profiles(cls, profiles: list[ProviderProfile]) -> "ProviderRegistry":
        text_provider: TextProvider = MockTextProvider()
        image_provider: ImageProvider = MockImageProvider()
        for profile in profiles:
            if not profile.enabled:
                continue
            if profile.kind == "openai-compatible":
                env_provider = OpenAICompatibleTextProvider.from_env()
                if env_provider is not None:
                    text_provider = env_provider
            elif profile.kind == "mock":
                text_provider = MockTextProvider()
            elif profile.kind == "image-mock":
                image_provider = MockImageProvider()
        return cls(text_provider=text_provider, image_provider=image_provider)

    def describe(self) -> dict[str, Any]:
        return {
            "text": self.text_provider.name,
            "image": self.image_provider.name,
        }
