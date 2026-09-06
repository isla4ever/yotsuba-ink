from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

CreationRouteId = Literal["screenplay_sample", "short_novel", "long_novel"]
DeliverableKind = Literal["screenplay", "short_novel", "long_novel"]
Unitization = Literal[
    "aggregate",
    "bounded_units",
    "sequential_units",
    "deterministic",
]
ArtifactKind = Literal[
    "screenplay_brief",
    "novel_brief",
    "character_bible",
    "beat_board",
    "scene_deck",
    "screenplay_draft",
    "story_map",
    "section_plan",
    "short_prose_unit",
    "book_architecture",
    "volume_architecture",
    "detail_plan_index",
    "chapter",
    "cover",
    "script_delivery",
    "book_delivery",
]
WorkbenchKind = Literal[
    "screenplay_brief",
    "novel_brief",
    "cast",
    "beat_board",
    "scene_deck",
    "screenplay_editor",
    "story_map",
    "section_plan",
    "short_prose_editor",
    "book_architecture",
    "volumes",
    "rolling_detail",
    "chapter_editor",
    "cover_studio",
    "script_delivery",
    "book_delivery",
]
ProviderTaskKind = Literal[
    "author_collaboration",
    "screenplay_brief",
    "novel_brief",
    "character_bible",
    "beat_board",
    "scene_deck",
    "screenplay_draft",
    "story_map",
    "section_plan",
    "short_prose_unit",
    "book_architecture",
    "volume_architecture",
    "rolling_detail",
    "chapter",
    "cover",
]


class RouteStageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    label: str = Field(min_length=1, max_length=80)
    artifact_kind: ArtifactKind
    workbench_kind: WorkbenchKind
    provider_task_kind: ProviderTaskKind | None = None
    upstream_stage_ids: tuple[str, ...] = ()
    unitization: Unitization
    decision_policy_ref: str = Field(pattern=r"^decision\.[a-z0-9_.-]+$")
    context_policy_ref: str = Field(pattern=r"^context\.[a-z0-9_.-]+$")
    collaboration_enabled: bool = False


class CreationRouteSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    route_id: CreationRouteId
    revision: str = Field(pattern=r"^r[1-9][0-9]*$")
    label: str = Field(min_length=1, max_length=80)
    deliverable_kind: DeliverableKind
    length_policy_ref: str = Field(pattern=r"^length\.[a-z0-9_.-]+$")
    default_review_policy_ref: str = Field(pattern=r"^review\.[a-z0-9_.-]+$")
    stages: tuple[RouteStageSpec, ...] = Field(min_length=2, max_length=32)
    capabilities: tuple[str, ...] = Field(min_length=1)
    export_profiles: tuple[str, ...] = Field(min_length=1)


def _stage(
    stage_id: str,
    label: str,
    artifact_kind: ArtifactKind,
    workbench_kind: WorkbenchKind,
    provider_task_kind: ProviderTaskKind | None,
    upstream_stage_ids: tuple[str, ...],
    unitization: Unitization,
    route_namespace: str,
    *,
    collaboration_enabled: bool = False,
    context_policy_revision: int = 1,
) -> RouteStageSpec:
    return RouteStageSpec(
        stage_id=stage_id,
        label=label,
        artifact_kind=artifact_kind,
        workbench_kind=workbench_kind,
        provider_task_kind=provider_task_kind,
        upstream_stage_ids=upstream_stage_ids,
        unitization=unitization,
        decision_policy_ref=f"decision.{route_namespace}.{stage_id}.v1",
        context_policy_ref=(
            f"context.{route_namespace}.{stage_id}.v{context_policy_revision}"
        ),
        collaboration_enabled=collaboration_enabled,
    )


SCREENPLAY_SAMPLE_ROUTE = CreationRouteSpec(
    route_id="screenplay_sample",
    revision="r3",
    label="剧本样片",
    deliverable_kind="screenplay",
    length_policy_ref="length.screenplay_sample.v1",
    default_review_policy_ref="review.screenplay.default",
    stages=(
        _stage(
            "brief",
            "样片立项",
            "screenplay_brief",
            "screenplay_brief",
            "screenplay_brief",
            (),
            "aggregate",
            "screenplay",
        ),
        _stage(
            "cast",
            "人物圣经",
            "character_bible",
            "cast",
            "character_bible",
            ("brief",),
            "aggregate",
            "screenplay",
            collaboration_enabled=True,
            context_policy_revision=2,
        ),
        _stage(
            "beat_board",
            "决策节拍",
            "beat_board",
            "beat_board",
            "beat_board",
            ("cast",),
            "aggregate",
            "screenplay",
            collaboration_enabled=True,
        ),
        _stage(
            "scene_deck",
            "场景牌组",
            "scene_deck",
            "scene_deck",
            "scene_deck",
            ("beat_board",),
            "bounded_units",
            "screenplay",
            collaboration_enabled=True,
        ),
        _stage(
            "script",
            "剧本正文",
            "screenplay_draft",
            "screenplay_editor",
            "screenplay_draft",
            ("scene_deck",),
            "sequential_units",
            "screenplay",
            collaboration_enabled=True,
        ),
        _stage(
            "export",
            "剧本交付",
            "script_delivery",
            "script_delivery",
            None,
            ("script",),
            "deterministic",
            "screenplay",
        ),
    ),
    capabilities=("adaptation_package", "author_collaboration", "runtime_monitoring"),
    export_profiles=("fountain", "pdf", "markdown"),
)


SHORT_NOVEL_ROUTE = CreationRouteSpec(
    route_id="short_novel",
    revision="r3",
    label="短中篇小说",
    deliverable_kind="short_novel",
    length_policy_ref="length.short_novel.v1",
    default_review_policy_ref="review.short_novel.default",
    stages=(
        _stage(
            "brief",
            "小说立项",
            "novel_brief",
            "novel_brief",
            "novel_brief",
            (),
            "aggregate",
            "short_novel",
        ),
        _stage(
            "story_map",
            "故事地图",
            "story_map",
            "story_map",
            "story_map",
            ("brief",),
            "aggregate",
            "short_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "cast",
            "人物圣经",
            "character_bible",
            "cast",
            "character_bible",
            ("story_map",),
            "aggregate",
            "short_novel",
            collaboration_enabled=True,
            context_policy_revision=2,
        ),
        _stage(
            "section_plan",
            "章节与段落计划",
            "section_plan",
            "section_plan",
            "section_plan",
            ("cast",),
            "bounded_units",
            "short_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "text",
            "小说正文",
            "short_prose_unit",
            "short_prose_editor",
            "short_prose_unit",
            ("section_plan",),
            "sequential_units",
            "short_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "cover",
            "封面",
            "cover",
            "cover_studio",
            "cover",
            ("text",),
            "aggregate",
            "short_novel",
        ),
        _stage(
            "export",
            "成书交付",
            "book_delivery",
            "book_delivery",
            None,
            ("cover",),
            "deterministic",
            "short_novel",
        ),
    ),
    capabilities=("author_collaboration", "cover_generation", "runtime_monitoring"),
    export_profiles=("epub", "docx", "markdown"),
)


LONG_NOVEL_ROUTE = CreationRouteSpec(
    route_id="long_novel",
    revision="r3",
    label="长篇小说",
    deliverable_kind="long_novel",
    length_policy_ref="length.long_novel.v1",
    default_review_policy_ref="review.long_novel.default",
    stages=(
        _stage(
            "brief",
            "长篇立项",
            "novel_brief",
            "novel_brief",
            "novel_brief",
            (),
            "aggregate",
            "long_novel",
        ),
        _stage(
            "book_architecture",
            "全书架构",
            "book_architecture",
            "book_architecture",
            "book_architecture",
            ("brief",),
            "bounded_units",
            "long_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "cast",
            "人物圣经",
            "character_bible",
            "cast",
            "character_bible",
            ("book_architecture",),
            "bounded_units",
            "long_novel",
            collaboration_enabled=True,
            context_policy_revision=2,
        ),
        _stage(
            "volumes",
            "卷册架构",
            "volume_architecture",
            "volumes",
            "volume_architecture",
            ("cast",),
            "bounded_units",
            "long_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "rolling_detail",
            "滚动细纲",
            "detail_plan_index",
            "rolling_detail",
            "rolling_detail",
            ("volumes",),
            "bounded_units",
            "long_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "text",
            "章节正文",
            "chapter",
            "chapter_editor",
            "chapter",
            ("rolling_detail",),
            "sequential_units",
            "long_novel",
            collaboration_enabled=True,
        ),
        _stage(
            "cover",
            "封面",
            "cover",
            "cover_studio",
            "cover",
            ("text",),
            "aggregate",
            "long_novel",
        ),
        _stage(
            "export",
            "成书交付",
            "book_delivery",
            "book_delivery",
            None,
            ("cover",),
            "deterministic",
            "long_novel",
        ),
    ),
    capabilities=(
        "amendments",
        "author_collaboration",
        "hierarchical_planning",
        "runtime_monitoring",
    ),
    export_profiles=("epub", "docx", "markdown"),
)

OFFICIAL_CREATION_ROUTES: Mapping[CreationRouteId, CreationRouteSpec] = MappingProxyType(
    {
        route.route_id: route
        for route in (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE)
    }
)


def official_creation_routes() -> tuple[CreationRouteSpec, ...]:
    return tuple(OFFICIAL_CREATION_ROUTES.values())


__all__ = [
    "ArtifactKind",
    "CreationRouteId",
    "CreationRouteSpec",
    "DeliverableKind",
    "LONG_NOVEL_ROUTE",
    "OFFICIAL_CREATION_ROUTES",
    "ProviderTaskKind",
    "RouteStageSpec",
    "SCREENPLAY_SAMPLE_ROUTE",
    "SHORT_NOVEL_ROUTE",
    "Unitization",
    "WorkbenchKind",
    "official_creation_routes",
]
