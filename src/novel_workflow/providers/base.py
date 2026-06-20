from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TextProvider(ABC):
    name: str

    @abstractmethod
    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        raise NotImplementedError


class ImageProvider(ABC):
    name: str

    @abstractmethod
    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
