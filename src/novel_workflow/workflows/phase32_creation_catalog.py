"""Authoritative route metadata for the Phase 32 creation wizard."""

from __future__ import annotations

from typing import Any

from novel_workflow.workflows.phase32_scale import OFFICIAL_SCALE_POLICIES
from novel_workflow.workflows.review_policy import OFFICIAL_REVIEW_POLICIES
from novel_workflow.workflows.route_specs import official_creation_routes


def route_catalog() -> tuple[dict[str, Any], ...]:
    """Return serializable route, scale, and review metadata for the UI."""

    return tuple(
        {
            "route": route.model_dump(mode="json"),
            "scale_policy": OFFICIAL_SCALE_POLICIES[route.route_id].model_dump(
                mode="json"
            ),
            "review_policy": OFFICIAL_REVIEW_POLICIES[
                route.default_review_policy_ref
            ].model_dump(mode="json"),
        }
        for route in official_creation_routes()
    )


__all__ = ["route_catalog"]
