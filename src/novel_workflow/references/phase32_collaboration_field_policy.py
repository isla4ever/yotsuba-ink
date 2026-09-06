"""Field-level safety policy for Phase 32 collaboration patch proposals."""

from __future__ import annotations


_COLLABORATION_STAGES = frozenset(
    {
        "cast",
        "beat_board",
        "scene_deck",
        "script",
        "story_map",
        "section_plan",
        "text",
        "book_architecture",
        "volumes",
        "rolling_detail",
    }
)
_IDENTITY_FIELDS = frozenset(
    {
        "architecture_version",
        "artifact_kind",
        "author_status",
        "status",
        "kind",
        "type",
        "ordinal",
        "index",
        "version",
        "version_id",
        "unit_kind",
    }
)


def phase32_collaboration_field_is_editable(stage_id: str, field_path: str) -> bool:
    if stage_id not in _COLLABORATION_STAGES or not field_path.strip():
        return False
    parts = tuple(part for part in field_path.split(".") if part)
    if not parts or any(part.startswith("_") for part in parts):
        return False
    field = parts[-1]
    if field in _IDENTITY_FIELDS or field.endswith("_ref") or field.endswith("_refs"):
        return False
    return True


__all__ = ["phase32_collaboration_field_is_editable"]
