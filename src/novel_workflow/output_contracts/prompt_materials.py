from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DetailEstablishedChapter(BaseModel):
    """Bounded evidence of what an earlier Detail segment already planned."""

    model_config = ConfigDict(extra="forbid")

    chapter_ref: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    title: str = Field(min_length=2, max_length=12)
    turn_refs: list[str] = Field(min_length=1, max_length=24)
    purpose: str = Field(min_length=1, max_length=1000)
    final_result: str = Field(min_length=1, max_length=700)


class DetailSegmentHandoff(BaseModel):
    """Immutable cumulative continuity sidecar between Detail calls."""

    model_config = ConfigDict(extra="forbid")

    previous_ref: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    completed_turn_refs: list[str] = Field(min_length=1)
    established_chapters: list[DetailEstablishedChapter] = Field(min_length=1)
    unresolved: list[str] = Field(min_length=1)
    next_ref: str = Field(pattern=r"^volume-[1-9][0-9]*\.segment-[1-9][0-9]*$")


class DetailVolumeExecutionContext(BaseModel):
    """Minimum volume projection visible to one Detail segment."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    title: str = Field(min_length=2, max_length=12)
    closing_state: str | None = Field(default=None, min_length=1, max_length=1000)


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
        "volume_spine_turns",
        "character_bible_refs",
        "volume_boundary",
        "scale_plan",
        "closure_policy",
        "previous_volume_handoff",
        "reserved_titles",
        "revision_request",
    ),
    "detail": (
        "volume_contract",
        "volume_spine_turns",
        "scale_projection",
        "selected_dossiers",
        "previous_segment_handoff",
        "reserved_titles",
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
    "volumes": frozenset(
        {
            "scale_plan",
            "previous_volume_handoff",
            "reserved_titles",
            "revision_request",
        }
    ),
    "detail": frozenset(
        {"previous_segment_handoff", "reserved_titles", "revision_request"}
    ),
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
    if stage_id == "detail" and "previous_segment_handoff" in material:
        DetailSegmentHandoff.model_validate(material["previous_segment_handoff"])
    if stage_id == "detail":
        volume_context = DetailVolumeExecutionContext.model_validate(
            material["volume_contract"]
        )
        scale = material["scale_projection"]
        is_final_segment = scale.get("segment_index") == scale.get("segment_count")
        if is_final_segment != bool(volume_context.closing_state):
            raise ValueError(
                "Detail closing_state must be visible only to the volume's final segment"
            )


__all__ = [
    "DetailEstablishedChapter",
    "DetailSegmentHandoff",
    "DetailVolumeExecutionContext",
    "OPTIONAL_PROMPT_MATERIAL_KEYS",
    "PROMPT_MATERIAL_KEYS",
    "PromptStageId",
    "validate_prompt_material",
]
