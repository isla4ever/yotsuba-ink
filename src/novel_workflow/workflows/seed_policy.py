"""Clear story-specific demo seeds when a template becomes a project workflow."""

from __future__ import annotations

import copy
from typing import Any

# Stage input_schema keys whose template defaults are concrete story content.
# Brief intake owns audience / core_concept / keywords / taboos and reference
# intent; ending_direction is a legacy template field retained only for seed cleanup.
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

def cleared_seed_default(default: Any) -> Any:
    """Empty value preserving the field's shape: tag lists stay lists, text goes blank."""
    return [] if isinstance(default, list) else ""


def scrub_narrative_seeds(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied workflow dict with demo narrative defaults cleared.

    Used by ProjectStore.create when copying a template into a per-project
    workflow. Stored templates themselves are never modified.
    """
    scrubbed = copy.deepcopy(workflow)
    for node in scrubbed.get("nodes") or []:
        _scrub_input_schema(node.get("input_schema"))
    return scrubbed


def materialize_project_workflow(workflow: dict[str, Any], idea: str) -> dict[str, Any]:
    materialized = scrub_narrative_seeds(workflow)
    brief = next(
        (node for node in materialized.get("nodes") or [] if node.get("type") == "brief"),
        None,
    )
    if brief is None:
        raise ValueError("Workflow is missing the Brief stage")
    concept = next(
        (field for field in brief.get("input_schema") or [] if field.get("key") == "core_concept"),
        None,
    )
    if concept is None:
        raise ValueError("Brief stage is missing the project idea field")
    concept["default"] = idea.strip()
    return materialized


def _scrub_input_schema(input_schema: Any) -> None:
    for field in input_schema or []:
        if field.get("key") in NARRATIVE_SEED_FIELD_KEYS:
            field["default"] = cleared_seed_default(field.get("default"))
