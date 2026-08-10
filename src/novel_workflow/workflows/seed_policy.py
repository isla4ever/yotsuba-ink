"""Clear story-specific demo seeds when a template becomes a project workflow."""

from __future__ import annotations

import copy
from typing import Any

# Stage input_schema keys whose template defaults are concrete story content.
# info stage: audience / core_concept / keywords / taboos plus the demo-flavored
# reference intent; summary stage: ending_direction presumes the demo mystery plot.
NARRATIVE_SEED_FIELD_KEYS: frozenset[str] = frozenset(
    {
        "audience",
        "core_concept",
        "keywords",
        "taboos",
        "reference_keywords",
        "reference_query_intent",
        "ending_direction",
    }
)

# global_inputs keys whose template defaults are concrete story content.
NARRATIVE_SEED_GLOBAL_INPUT_KEYS: frozenset[str] = frozenset({"title"})


def cleared_seed_default(default: Any) -> Any:
    """Empty value preserving the field's shape: tag lists stay lists, text goes blank."""
    return [] if isinstance(default, list) else ""


def scrub_narrative_seeds(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied workflow dict with demo narrative defaults cleared.

    Used by ProjectStore.create when copying a template into a per-project
    workflow. Stored templates themselves are never modified.
    """
    scrubbed = copy.deepcopy(workflow)
    for field in scrubbed.get("global_inputs") or []:
        if field.get("key") in NARRATIVE_SEED_GLOBAL_INPUT_KEYS:
            field["default"] = cleared_seed_default(field.get("default"))
    for node in scrubbed.get("nodes") or []:
        _scrub_input_schema(node.get("input_schema"))
    return scrubbed


def _scrub_input_schema(input_schema: Any) -> None:
    for field in input_schema or []:
        if field.get("key") in NARRATIVE_SEED_FIELD_KEYS:
            field["default"] = cleared_seed_default(field.get("default"))
