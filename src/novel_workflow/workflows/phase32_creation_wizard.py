"""Canonical two-step Phase 32 creation wizard contracts and matching rules."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.phase32_language_contract import (
    CreationLanguage,
    PHASE32_CREATION_LANGUAGE,
)
from novel_workflow.workflows.phase32_scale import ScaleProfile, freeze_scale_profile
from novel_workflow.workflows.route_specs import (
    CreationRouteId,
    official_creation_routes,
)


CreationKind = Literal["screenplay", "novel"]
NovelLengthClass = Literal["short_novel", "long_novel"]
WorkflowSource = Literal["official"]
WorkflowChoiceMode = Literal["existing"]

class CreationIntent(BaseModel):
    """Step 1: the user's deliverable intent before a workflow is selected."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    creative_intent: str = Field(min_length=1, max_length=4_000)
    creation_language: CreationLanguage = PHASE32_CREATION_LANGUAGE
    creation_kind: CreationKind
    novel_length_class: NovelLengthClass | None = None
    requested_target: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_kind_and_scale(self) -> Self:
        if self.creation_kind == "screenplay" and self.novel_length_class is not None:
            raise ValueError("Screenplay intent cannot define a novel length class")
        if self.creation_kind == "novel" and self.novel_length_class is None:
            raise ValueError("Novel intent requires short_novel or long_novel")
        route_id = self.creation_route_id
        if self.requested_target is not None:
            freeze_scale_profile(route_id, target=self.requested_target)
        return self

    @property
    def creation_route_id(self) -> CreationRouteId:
        if self.creation_kind == "screenplay":
            return "screenplay_sample"
        assert self.novel_length_class is not None
        return self.novel_length_class

    def scale_profile(self) -> ScaleProfile:
        return freeze_scale_profile(
            self.creation_route_id,
            target=self.requested_target,
        )


class WorkflowCatalogEntry(BaseModel):
    """A selectable existing workflow returned by the catalog API."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    workflow_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    route_id: CreationRouteId
    label: str = Field(min_length=1, max_length=120)
    source: WorkflowSource
    revision: str = Field(pattern=r"^r[1-9][0-9]*$")
    workflow_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    summary: str = Field(default="", max_length=500)
    available: bool = True


class WorkflowRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    workflow: WorkflowCatalogEntry
    match_reason: str = Field(min_length=1, max_length=240)
    recommended: bool


class WorkflowSelection(BaseModel):
    """Step 2: choose one official workflow for the locked route."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    intent: CreationIntent
    mode: WorkflowChoiceMode
    workflow_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")


def official_workflow_catalog() -> tuple[WorkflowCatalogEntry, ...]:
    """Return the route-matched official templates without UI-specific state."""

    return tuple(
        WorkflowCatalogEntry(
            workflow_id=f"official.{route.route_id}",
            route_id=route.route_id,
            label=route.label,
            source="official",
            revision=route.revision,
            workflow_digest=canonical_digest(route.model_dump(mode="json")),
            summary=f"{route.label}官方流水线",
        )
        for route in official_creation_routes()
    )


def recommend_workflows(
    intent: CreationIntent,
    catalog: tuple[WorkflowCatalogEntry, ...],
) -> tuple[WorkflowRecommendation, ...]:
    """Filter and rank existing workflows for the route inferred in Step 1."""

    route_id = intent.creation_route_id
    matches = [
        entry
        for entry in catalog
        if entry.available and entry.route_id == route_id
    ]
    matches.sort(key=lambda entry: entry.workflow_id)
    return tuple(
        WorkflowRecommendation(
            workflow=entry,
            match_reason=f"与{route_id}路线匹配",
            recommended=index == 0,
        )
        for index, entry in enumerate(matches)
    )


def resolve_workflow_selection(
    selection: WorkflowSelection,
    catalog: tuple[WorkflowCatalogEntry, ...],
) -> WorkflowCatalogEntry:
    """Resolve Step 2 into the matching official catalog entry."""

    route_id = selection.intent.creation_route_id
    match = next(
        (
            entry
            for entry in catalog
            if entry.workflow_id == selection.workflow_id and entry.available
        ),
        None,
    )
    if match is None:
        raise ValueError("Selected workflow is unavailable or missing")
    if match.route_id != route_id:
        raise ValueError("Selected workflow route does not match the creation intent")
    return match


__all__ = [
    "CreationIntent",
    "CreationLanguage",
    "CreationKind",
    "NovelLengthClass",
    "WorkflowCatalogEntry",
    "WorkflowChoiceMode",
    "WorkflowRecommendation",
    "WorkflowSelection",
    "WorkflowSource",
    "official_workflow_catalog",
    "recommend_workflows",
    "resolve_workflow_selection",
]
