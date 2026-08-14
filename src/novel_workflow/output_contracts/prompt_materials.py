from __future__ import annotations

from typing import Any, Literal


PromptStageId = Literal[
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
]


PROMPT_MATERIAL_KEYS: dict[PromptStageId, tuple[str, ...]] = {
    "brief": (
        "project_brief",
        "length_envelope",
        "source_pack",
        "revision_request",
    ),
    "spine": (
        "story_brief",
        "source_observations",
        "scale_plan",
        "revision_request",
    ),
    "cast": (
        "story_brief",
        "story_spine",
        "role_demand_proposals",
        "subject_refs",
        "scale_plan",
        "revision_request",
    ),
    "volumes": (
        "story_brief",
        "story_spine",
        "character_bible_refs",
        "volume_boundaries",
        "scale_plan",
        "closure_policy",
        "revision_request",
    ),
    "detail": (
        "volume_contract",
        "volume_spine_turns",
        "scale_projection",
        "selected_dossiers",
        "active_thread_refs",
        "previous_segment_handoff",
        "revision_request",
    ),
    "text": (
        "chapter_context_manifest",
    ),
    "cover": (
        "accepted_story_metadata",
        "visual_decisions",
        "revision_request",
    ),
}


OPTIONAL_PROMPT_MATERIAL_KEYS: dict[PromptStageId, frozenset[str]] = {
    "brief": frozenset({"source_pack", "revision_request"}),
    "spine": frozenset({"source_observations", "scale_plan", "revision_request"}),
    "cast": frozenset({"scale_plan", "revision_request"}),
    "volumes": frozenset({"scale_plan", "closure_policy", "revision_request"}),
    "detail": frozenset({"previous_segment_handoff", "revision_request"}),
    "text": frozenset(),
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
