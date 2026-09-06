from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.output_contracts.artifacts_vnext import DetailSegmentArtifact


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


class DetailPreflightFeedbackItem(BaseModel):
    """One deterministic defect from the immediately preceding Detail candidate."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    chapter_refs: list[str] = Field(default_factory=list, max_length=24)
    evidence: str = Field(min_length=1, max_length=800)
    required_fix: str = Field(min_length=1, max_length=800)


class DetailPreflightFeedback(BaseModel):
    """Bounded feedback sidecar for one source-bound Detail repair unit."""

    model_config = ConfigDict(extra="forbid")

    source_candidate_ref: str = Field(min_length=1, max_length=240)
    source_attempt: int = Field(ge=1)
    unique_blocker_count: int = Field(ge=1)
    omitted_blocker_count: int = Field(ge=0)
    blockers: list[DetailPreflightFeedbackItem] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_bounded_count(self) -> "DetailPreflightFeedback":
        if self.unique_blocker_count != len(self.blockers) + self.omitted_blocker_count:
            raise ValueError("Detail preflight feedback counts do not match")
        return self


class DetailCustodyRecoveryContract(BaseModel):
    """Deterministic state projection for one invalid custody handoff."""

    model_config = ConfigDict(extra="forbid")

    previous_chapter_ref: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    previous_state: Literal["free"] = "free"
    target_state: Literal["detained", "free_or_detained"]
    transition_timing: Literal["on_page_before_custody"] = "on_page_before_custody"
    allowed_institution: Literal["警方"] = "警方"
    preserved_dramatic_task: str = Field(min_length=1, max_length=1000)


class DetailRecoverySource(BaseModel):
    """Immutable rejected segment plus the exact chapter-level edit boundary."""

    model_config = ConfigDict(extra="forbid")

    source_candidate_ref: str = Field(min_length=1, max_length=240)
    source_attempt: int = Field(ge=1)
    segment_ref: str = Field(
        pattern=r"^volume-[1-9][0-9]*\.segment-[1-9][0-9]*$"
    )
    chapter_refs: list[str] = Field(min_length=1, max_length=200)
    editable_chapter_refs: list[str] = Field(min_length=1, max_length=200)
    preserved_chapter_refs: list[str] = Field(default_factory=list, max_length=200)
    required_removed_endpoints: dict[str, list[str]] = Field(max_length=200)
    custody_repair_contracts: dict[str, DetailCustodyRecoveryContract] = Field(
        default_factory=dict,
        max_length=200,
    )
    source_segment: DetailSegmentArtifact

    @model_validator(mode="after")
    def validate_partition(self) -> "DetailRecoverySource":
        if not all(
            re.fullmatch(r"chapter-[1-9][0-9]*", chapter_ref)
            for chapter_ref in self.chapter_refs
        ):
            raise ValueError("Detail recovery chapter refs must use chapter-N format")
        expected = [
            f"chapter-{index}"
            for index in range(
                int(self.chapter_refs[0].removeprefix("chapter-")),
                int(self.chapter_refs[0].removeprefix("chapter-"))
                + len(self.chapter_refs),
            )
        ]
        if self.chapter_refs != expected:
            raise ValueError("Detail recovery chapter refs must be contiguous")
        if len(self.source_segment.chapters) != len(self.chapter_refs):
            raise ValueError("Detail recovery source segment does not match its chapter refs")
        editable = set(self.editable_chapter_refs)
        preserved = set(self.preserved_chapter_refs)
        if editable & preserved or editable | preserved != set(self.chapter_refs):
            raise ValueError("Detail recovery edit and preserve refs must partition the segment")
        if not set(self.required_removed_endpoints) <= editable:
            raise ValueError(
                "Detail recovery endpoint removals must target editable chapters"
            )
        if not set(self.custody_repair_contracts) <= editable:
            raise ValueError(
                "Detail custody repair contracts must target editable chapters"
            )
        if any(
            int(contract.previous_chapter_ref.removeprefix("chapter-")) + 1
            != int(chapter_ref.removeprefix("chapter-"))
            for chapter_ref, contract in self.custody_repair_contracts.items()
        ):
            raise ValueError(
                "Detail custody repair contracts must bind adjacent chapter handoffs"
            )
        if any(
            not endpoints or len(endpoints) != len(set(endpoints))
            for endpoints in self.required_removed_endpoints.values()
        ):
            raise ValueError(
                "Detail recovery endpoint removals must be non-empty and unique"
            )
        return self


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
        "debut_requirements",
        "historical_record_ids",
        "present_actor_ids",
        "world_rule_projection",
        "previous_segment_handoff",
        "reserved_titles",
        "preflight_feedback",
        "recovery_source",
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
        {
            "debut_requirements",
            "previous_segment_handoff",
            "reserved_titles",
            "preflight_feedback",
            "recovery_source",
            "revision_request",
        }
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
        feedback = (
            DetailPreflightFeedback.model_validate(material["preflight_feedback"])
            if "preflight_feedback" in material
            else None
        )
        recovery = (
            DetailRecoverySource.model_validate(material["recovery_source"])
            if "recovery_source" in material
            else None
        )
        if (feedback is None) != (recovery is None):
            raise ValueError("Detail preflight feedback and recovery source must travel together")
        if feedback is not None and recovery is not None and (
            feedback.source_candidate_ref != recovery.source_candidate_ref
            or feedback.source_attempt != recovery.source_attempt
        ):
            raise ValueError("Detail recovery source does not match its preflight feedback")
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
    "DetailPreflightFeedback",
    "DetailPreflightFeedbackItem",
    "DetailRecoverySource",
    "DetailSegmentHandoff",
    "DetailVolumeExecutionContext",
    "OPTIONAL_PROMPT_MATERIAL_KEYS",
    "PROMPT_MATERIAL_KEYS",
    "PromptStageId",
    "validate_prompt_material",
]
