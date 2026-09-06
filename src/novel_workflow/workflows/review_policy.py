from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.route_specs import CreationRouteId

CheckpointPolicy = Literal["milestone", "every_stage", "every_unit"]
WarningPolicy = Literal["continue_and_surface", "pause_at_milestone"]


class ReviewPolicy(BaseModel):
    """A frozen review policy selected before a Run is created."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    policy_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,95}$")
    revision: str = Field(pattern=r"^r[1-9][0-9]*$")
    route_id: CreationRouteId
    checkpoint_policy: CheckpointPolicy
    warning_policy: WarningPolicy
    contract_correction_limit: int = Field(default=1, ge=0, le=1)
    directed_redraft_limit_by_stage: dict[str, int] = Field(default_factory=dict)
    auto_continue_stages: tuple[str, ...] = ()
    mandatory_decision_stages: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_stage_controls(self) -> "ReviewPolicy":
        stage_sets = {
            "auto_continue_stages": self.auto_continue_stages,
            "mandatory_decision_stages": self.mandatory_decision_stages,
        }
        for label, stage_ids in stage_sets.items():
            if len(stage_ids) != len(set(stage_ids)):
                raise ValueError(f"{label} must contain unique stage ids")
        overlap = set(self.auto_continue_stages) & set(self.mandatory_decision_stages)
        if overlap:
            raise ValueError(
                "A stage cannot be both automatic and mandatory: "
                + ", ".join(sorted(overlap))
            )
        invalid_limits = {
            stage_id: limit
            for stage_id, limit in self.directed_redraft_limit_by_stage.items()
            if not 0 <= limit <= 2
        }
        if invalid_limits:
            raise ValueError("Directed redraft limits must be between 0 and 2")
        return self


SCREENPLAY_REVIEW_POLICY = ReviewPolicy(
    policy_id="review.screenplay.default",
    revision="r2",
    route_id="screenplay_sample",
    checkpoint_policy="milestone",
    warning_policy="pause_at_milestone",
    directed_redraft_limit_by_stage={
        "cast": 1,
        "beat_board": 1,
        "scene_deck": 1,
        "script": 1,
    },
    auto_continue_stages=("scene_deck",),
    mandatory_decision_stages=("brief", "cast", "beat_board", "script"),
)

SHORT_NOVEL_REVIEW_POLICY = ReviewPolicy(
    policy_id="review.short_novel.default",
    revision="r2",
    route_id="short_novel",
    checkpoint_policy="milestone",
    warning_policy="pause_at_milestone",
    directed_redraft_limit_by_stage={
        "story_map": 1,
        "cast": 1,
        "section_plan": 1,
        "text": 1,
    },
    mandatory_decision_stages=("brief", "story_map", "cast", "text", "cover"),
)

LONG_NOVEL_REVIEW_POLICY = ReviewPolicy(
    policy_id="review.long_novel.default",
    revision="r2",
    route_id="long_novel",
    checkpoint_policy="every_unit",
    warning_policy="pause_at_milestone",
    directed_redraft_limit_by_stage={
        "book_architecture": 1,
        "cast": 1,
        "volumes": 1,
        "rolling_detail": 1,
        "text": 1,
    },
    mandatory_decision_stages=(
        "brief",
        "book_architecture",
        "cast",
        "volumes",
        "rolling_detail",
        "text",
        "cover",
    ),
)

OFFICIAL_REVIEW_POLICIES: Mapping[str, ReviewPolicy] = MappingProxyType(
    {
        policy.policy_id: policy
        for policy in (
            SCREENPLAY_REVIEW_POLICY,
            SHORT_NOVEL_REVIEW_POLICY,
            LONG_NOVEL_REVIEW_POLICY,
        )
    }
)


__all__ = [
    "CheckpointPolicy",
    "LONG_NOVEL_REVIEW_POLICY",
    "OFFICIAL_REVIEW_POLICIES",
    "ReviewPolicy",
    "SCREENPLAY_REVIEW_POLICY",
    "SHORT_NOVEL_REVIEW_POLICY",
    "WarningPolicy",
]
