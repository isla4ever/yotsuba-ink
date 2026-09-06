"""Deterministic projections for Phase 32 short-prose units."""

from __future__ import annotations

from typing import Literal

from novel_workflow.workflows.phase32_scale import scale_policy


ShortProseUnitKind = Literal["section", "chapter"]


def short_prose_unit_kind(scale_profile_payload: dict[str, object]) -> ShortProseUnitKind:
    """Project the author-facing unit kind from the frozen short-novel scale."""

    target = scale_profile_payload.get("target")
    if (
        isinstance(target, bool)
        or not isinstance(target, int)
        or target < 1
        or scale_profile_payload.get("unit") != "characters"
    ):
        raise ValueError("Short prose unit kind requires a character ScaleProfile target")
    recommended_ceiling = scale_profile_payload.get("recommended_ceiling")
    if isinstance(recommended_ceiling, bool) or not isinstance(
        recommended_ceiling, int
    ):
        recommended_ceiling = scale_policy("short_novel").recommended_ceiling
    return "section" if target <= recommended_ceiling else "chapter"


__all__ = ["ShortProseUnitKind", "short_prose_unit_kind"]
