"""Workflow identity helpers.

Phase 32 routes are the only new product identities.  The old DeepSeek mode
ids remain named here solely so the legacy template/archive adapters can read
historical records while the catalog and creation service migrate to route
ids.  They must not be used as the identity of a newly frozen Phase 32 route.
"""

OFFICIAL_SCREENPLAY_WORKFLOW_ID = "official.screenplay_sample"
OFFICIAL_SHORT_NOVEL_WORKFLOW_ID = "official.short_novel"
OFFICIAL_LONG_NOVEL_WORKFLOW_ID = "official.long_novel"

CANONICAL_OFFICIAL_WORKFLOW_IDS = frozenset(
    {
        OFFICIAL_SCREENPLAY_WORKFLOW_ID,
        OFFICIAL_SHORT_NOVEL_WORKFLOW_ID,
        OFFICIAL_LONG_NOVEL_WORKFLOW_ID,
    }
)
CANONICAL_IMAGE_DEFERRED_WORKFLOW_IDS = frozenset(
    {
        OFFICIAL_SHORT_NOVEL_WORKFLOW_ID,
        OFFICIAL_LONG_NOVEL_WORKFLOW_ID,
    }
)

# Legacy Phase 27 template identities.  Keep these constants for read-only
# migration and archive code; they are not canonical Phase 32 route ids.
OFFICIAL_FAST_WORKFLOW_ID = "official-deepseek-fast"
OFFICIAL_BALANCED_WORKFLOW_ID = "official-deepseek-balanced"
OFFICIAL_DEEP_WORKFLOW_ID = "official-deepseek-deep"
LEGACY_OFFICIAL_WORKFLOW_IDS = frozenset(
    {
        OFFICIAL_FAST_WORKFLOW_ID,
        OFFICIAL_BALANCED_WORKFLOW_ID,
        OFFICIAL_DEEP_WORKFLOW_ID,
    }
)

# Legacy callers still use this default while their API is being retired.  A
# new Phase 32 Run uses the canonical route id instead.
DEFAULT_WORKFLOW_ID = OFFICIAL_BALANCED_WORKFLOW_ID
DEFAULT_CANONICAL_WORKFLOW_ID = OFFICIAL_SHORT_NOVEL_WORKFLOW_ID

OFFICIAL_WORKFLOW_IDS = frozenset(
    CANONICAL_OFFICIAL_WORKFLOW_IDS | LEGACY_OFFICIAL_WORKFLOW_IDS
)


def is_official_workflow_id(workflow_id: str) -> bool:
    """Return whether an id is protected as official or legacy-official."""

    return workflow_id in OFFICIAL_WORKFLOW_IDS


def is_canonical_workflow_id(workflow_id: str) -> bool:
    """Return whether an id is one of the three Phase 32 route identities."""

    return workflow_id in CANONICAL_OFFICIAL_WORKFLOW_IDS


def is_image_acceptance_deferred_workflow_id(workflow_id: str) -> bool:
    """Return whether the current wave stops this route after CoverBrief."""

    return workflow_id in CANONICAL_IMAGE_DEFERRED_WORKFLOW_IDS


def is_legacy_official_workflow_id(workflow_id: str) -> bool:
    """Return whether an id belongs to the retired Phase 27 templates."""

    return workflow_id in LEGACY_OFFICIAL_WORKFLOW_IDS


__all__ = [
    "CANONICAL_OFFICIAL_WORKFLOW_IDS",
    "CANONICAL_IMAGE_DEFERRED_WORKFLOW_IDS",
    "DEFAULT_CANONICAL_WORKFLOW_ID",
    "DEFAULT_WORKFLOW_ID",
    "LEGACY_OFFICIAL_WORKFLOW_IDS",
    "OFFICIAL_LONG_NOVEL_WORKFLOW_ID",
    "OFFICIAL_BALANCED_WORKFLOW_ID",
    "OFFICIAL_DEEP_WORKFLOW_ID",
    "OFFICIAL_FAST_WORKFLOW_ID",
    "OFFICIAL_SCREENPLAY_WORKFLOW_ID",
    "OFFICIAL_SHORT_NOVEL_WORKFLOW_ID",
    "OFFICIAL_WORKFLOW_IDS",
    "is_canonical_workflow_id",
    "is_image_acceptance_deferred_workflow_id",
    "is_legacy_official_workflow_id",
    "is_official_workflow_id",
]
