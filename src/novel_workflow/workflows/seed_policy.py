"""Narrative seed governance (Phase 12 M1).

The default workflow template ships with demo narrative defaults (the
"旧港记忆实验" story seeds) so the legacy no-project run path on
``default-novel-workflow`` keeps working out of the box. When a new project
copies a template, those story-specific defaults must be cleared so required
story fields are genuinely blank and the guided setup appears. Structural
defaults — length tiers, mode selects, numeric parameters, craft checklists —
are deliberately not listed here and survive project creation.
"""

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
    workflow. The stored templates themselves (including the seeded
    ``default-novel-workflow``) are never modified, so the legacy path that
    runs the default workflow directly keeps its demo values.
    """
    scrubbed = copy.deepcopy(workflow)
    for field in scrubbed.get("global_inputs") or []:
        if field.get("key") in NARRATIVE_SEED_GLOBAL_INPUT_KEYS:
            field["default"] = cleared_seed_default(field.get("default"))
    for node in scrubbed.get("nodes") or []:
        _scrub_input_schema(node.get("input_schema"))
    for stage_config in (scrubbed.get("stage_configs") or {}).values():
        _scrub_input_schema(stage_config.get("input_schema"))
    return scrubbed


def _scrub_input_schema(input_schema: Any) -> None:
    for field in input_schema or []:
        if field.get("key") in NARRATIVE_SEED_FIELD_KEYS:
            field["default"] = cleared_seed_default(field.get("default"))
