from __future__ import annotations

from typing import Any, Literal


PromptStageId = Literal[
    "info",
    "characters",
    "summary",
    "outline",
    "detail",
    "text",
    "cover",
]


PROMPT_MATERIAL_KEYS: dict[PromptStageId, tuple[str, ...]] = {
    "info": (
        "project_brief",
        "book_scale_plan",
        "source_pack",
        "revision_request",
    ),
    "characters": (
        "book_scale_plan",
        "story_brief",
        "revision_request",
    ),
    "summary": (
        "book_scale_plan",
        "story_brief",
        "character_bible",
        "revision_request",
    ),
    "outline": (
        "book_scale_plan",
        "story_brief",
        "character_bible",
        "summary",
        "target_volume",
        "revision_request",
    ),
    "detail": (
        "book_scale_plan",
        "story_brief",
        "character_bible",
        "summary",
        "outline",
        "obligation_registry",
        "target_chapters",
        "revision_request",
    ),
    "text": (
        "book_scale",
        "story_constraints",
        "character_bible",
        "summary_commitments",
        "volume_plan",
        "chapter_plan",
        "previous_handoff",
        "previous_accepted_chapter",
        "revision_request",
    ),
    "cover": (
        "story",
        "cast",
        "narrative_arc",
        "volume_objectives",
        "chapter_motifs",
        "revision_request",
    ),
}


OPTIONAL_PROMPT_MATERIAL_KEYS: dict[PromptStageId, frozenset[str]] = {
    "info": frozenset({"source_pack", "revision_request"}),
    "characters": frozenset({"revision_request"}),
    "summary": frozenset({"revision_request"}),
    "outline": frozenset({"target_volume", "revision_request"}),
    "detail": frozenset({"target_chapters", "revision_request"}),
    "text": frozenset({"revision_request"}),
    "cover": frozenset({"revision_request"}),
}


def validate_prompt_material(stage_id: PromptStageId, material: dict[str, Any]) -> None:
    allowed = set(PROMPT_MATERIAL_KEYS[stage_id])
    actual = set(material)
    unknown = actual - allowed
    if unknown:
        raise ValueError(
            f"{stage_id} context contains undeclared Prompt material: {sorted(unknown)}"
        )
    required = allowed - OPTIONAL_PROMPT_MATERIAL_KEYS[stage_id]
    missing = required - actual
    if missing:
        raise ValueError(
            f"{stage_id} context is missing required Prompt material: {sorted(missing)}"
        )


__all__ = [
    "OPTIONAL_PROMPT_MATERIAL_KEYS",
    "PROMPT_MATERIAL_KEYS",
    "PromptStageId",
    "validate_prompt_material",
]
