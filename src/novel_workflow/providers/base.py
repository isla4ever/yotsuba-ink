from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

# Layered-prompt transport contract (Phase 10.0C): the prompt builder joins
# system and user parts with this sentinel; message-based adapters split it
# back into real system/user messages. Plain-string providers can ignore it.
PROMPT_SYSTEM_SPLIT = "\n\n===NW-USER===\n\n"


def split_system_prompt(prompt: str) -> tuple[str, str]:
    """Return (system, user); system is empty when the prompt is not layered."""
    if PROMPT_SYSTEM_SPLIT in prompt:
        system, user = prompt.split(PROMPT_SYSTEM_SPLIT, 1)
        return system.strip(), user.strip()
    return "", prompt


class TextProvider(ABC):
    name: str

    @abstractmethod
    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise NotImplementedError

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        del schema
        return await self.generate_text(prompt, task_name=task_name, context=context)

    async def stream_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> AsyncIterator[str]:
        text = await self.generate_text(prompt, task_name=task_name, context=context)
        yield text


class ImageProvider(ABC):
    name: str

    @abstractmethod
    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> "GeneratedImage":
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    content: bytes
    mime_type: str
    provider_asset_id: str = ""
    revised_prompt: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
