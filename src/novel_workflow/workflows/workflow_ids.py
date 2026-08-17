OFFICIAL_FAST_WORKFLOW_ID = "official-deepseek-fast"
OFFICIAL_BALANCED_WORKFLOW_ID = "official-deepseek-balanced"
OFFICIAL_DEEP_WORKFLOW_ID = "official-deepseek-deep"
DEFAULT_WORKFLOW_ID = OFFICIAL_BALANCED_WORKFLOW_ID

OFFICIAL_WORKFLOW_IDS = frozenset(
    {
        OFFICIAL_FAST_WORKFLOW_ID,
        OFFICIAL_BALANCED_WORKFLOW_ID,
        OFFICIAL_DEEP_WORKFLOW_ID,
    }
)


def is_official_workflow_id(workflow_id: str) -> bool:
    return workflow_id in OFFICIAL_WORKFLOW_IDS


__all__ = [
    "DEFAULT_WORKFLOW_ID",
    "OFFICIAL_BALANCED_WORKFLOW_ID",
    "OFFICIAL_DEEP_WORKFLOW_ID",
    "OFFICIAL_FAST_WORKFLOW_ID",
    "OFFICIAL_WORKFLOW_IDS",
    "is_official_workflow_id",
]
