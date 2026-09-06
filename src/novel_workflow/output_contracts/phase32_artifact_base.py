"""Shared primitives for dormant Phase 32 core Artifacts."""

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


Ref = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")]
NonEmptyText = Annotated[str, Field(min_length=1, max_length=4000)]
ShortText = Annotated[str, Field(min_length=1, max_length=500)]
PromiseRef = Ref


class Phase32Artifact(BaseModel):
    """Strict, immutable base for a core Phase 32 creative Artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


ScreenplayBlockKind = Literal[
    "scene_heading",
    "action",
    "dialogue",
    "parenthetical",
    "transition",
]

DeliveryFormat: TypeAlias = Literal[
    "fountain",
    "pdf",
    "markdown",
    "epub",
    "docx",
]


__all__ = [
    "DeliveryFormat",
    "NonEmptyText",
    "Phase32Artifact",
    "PromiseRef",
    "Ref",
    "ScreenplayBlockKind",
    "ShortText",
]
