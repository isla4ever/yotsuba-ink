from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Optional

from pydantic import BaseModel, Field

ProjectStatus = Literal["active", "archived"]

# Curated hue sequence (degrees): adjacent projects land on clearly distinct hues.
ACCENT_HUE_SEQUENCE: tuple[int, ...] = (212, 262, 172, 32, 338, 118, 288, 58, 196, 8)


def next_accent_hue(existing_hues: Sequence[int]) -> int:
    """Deterministically pick the next accent hue from the palette sequence.

    The first unused hue in the sequence wins; once the palette is exhausted
    the sequence cycles by project count. No randomness so tests can lock it.
    """
    used = set(existing_hues)
    for hue in ACCENT_HUE_SEQUENCE:
        if hue not in used:
            return hue
    return ACCENT_HUE_SEQUENCE[len(existing_hues) % len(ACCENT_HUE_SEQUENCE)]


class ProjectRecord(BaseModel):
    id: str
    title: str
    summary: str = ""
    accent_hue: int = Field(default=ACCENT_HUE_SEQUENCE[0], ge=0, le=360)
    workflow_id: str
    status: ProjectStatus = "active"
    created_at: str = ""
    updated_at: str = ""
    latest_run_id: str = ""


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=2000)
    template_workflow_id: str = Field(default="default-novel-workflow", min_length=1, max_length=160)


class ProjectPatchRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    summary: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[ProjectStatus] = None
    accent_hue: Optional[int] = Field(default=None, ge=0, le=360)

    def changes(self) -> dict[str, object]:
        return {key: value for key, value in self.model_dump().items() if value is not None}
